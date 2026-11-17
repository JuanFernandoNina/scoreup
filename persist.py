"""SQLite: migración conservadora y transacciones serializadas por petición.

Los respaldos antiguos se conservan como no oficiales. La restricción parcial
impide dos notas oficiales para el mismo club/evento también entre procesos.
"""

import json
import mimetypes
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime
from contextlib import closing

import data
from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get("SCOREUP_DB", os.path.join(os.path.dirname(__file__), "scoreup.db"))
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
MODELS = {
    "clubs": data.Club, "users": data.Usuario, "eventos": data.Evento,
    "criterios": data.Criterio, "evento_club": data.EventoClub,
    "evaluaciones": data.Evaluacion, "motivos": data.MotivoPenalizacion,
    "penalizaciones": data.PenalizacionAplicada, "incidentes": data.Incidente,
}
TABLES = ["organizaciones", *MODELS, "correcciones"]
JSON_FIELDS = {"miembros", "valores", "anterior", "actual"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS organizaciones (id TEXT PRIMARY KEY, nombre TEXT NOT NULL, fecha_creacion TEXT);
CREATE TABLE IF NOT EXISTS clubs (id TEXT PRIMARY KEY, nombre TEXT NOT NULL, organizacion_id TEXT NOT NULL, miembros TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, organizacion_id TEXT NOT NULL, nombre TEXT NOT NULL, username TEXT NOT NULL, password TEXT NOT NULL, rol TEXT NOT NULL, evento_id TEXT, club_id TEXT);
CREATE TABLE IF NOT EXISTS eventos (id TEXT PRIMARY KEY, organizacion_id TEXT NOT NULL, nombre TEXT NOT NULL, fecha TEXT, lugar TEXT, tipo TEXT, temporada TEXT, puntaje_maximo INTEGER NOT NULL, cerrado INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS criterios (id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, nombre TEXT NOT NULL, peso REAL NOT NULL);
CREATE TABLE IF NOT EXISTS evento_club (id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, club_id TEXT NOT NULL, staff_principal_id TEXT);
CREATE TABLE IF NOT EXISTS evaluaciones (id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, club_id TEXT NOT NULL, evaluador_id TEXT NOT NULL, comentario TEXT, fecha TEXT, valores TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS motivos (id TEXT PRIMARY KEY, organizacion_id TEXT NOT NULL, nombre TEXT NOT NULL, descripcion TEXT, puntos_descuento REAL NOT NULL, activo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS penalizaciones (id TEXT PRIMARY KEY, club_id TEXT NOT NULL, evento_id TEXT NOT NULL, usuario_id TEXT NOT NULL, motivo_id TEXT NOT NULL, comentario TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS incidentes (id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, usuario_id TEXT NOT NULL, tipo TEXT, gravedad TEXT, descripcion TEXT, estado TEXT, club_id TEXT, foto_url TEXT, fecha_hora TEXT);
CREATE TABLE IF NOT EXISTS correcciones (id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, club_id TEXT NOT NULL, evaluador_id TEXT NOT NULL, fecha TEXT NOT NULL, anterior TEXT NOT NULL, actual TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'pendiente');
"""


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_pw(password):
    if password and password.startswith(("scrypt:", "pbkdf2:")):
        return password
    return generate_password_hash(password or "")


def initialize():
    """Migrar una sola vez al arrancar; copia de seguridad antes de migrar datos."""
    with closing(connect()) as conn:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(evaluaciones)")}
        if columns and "oficial" not in columns:
            backup = sqlite3.connect(f"{DB_PATH}.backup-{datetime.now():%Y%m%d%H%M%S%f}")
            try:
                conn.backup(backup)
            finally:
                backup.close()
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        columns = {r[1] for r in conn.execute("PRAGMA table_info(evaluaciones)")}
        if "oficial" not in columns:
            conn.execute("ALTER TABLE evaluaciones ADD COLUMN oficial INTEGER NOT NULL DEFAULT 0")
            conn.execute("""UPDATE evaluaciones SET oficial=1 WHERE rowid IN (
                SELECT MIN(e.rowid) FROM evaluaciones e JOIN evento_club ec
                ON ec.evento_id=e.evento_id AND ec.club_id=e.club_id
                AND ec.staff_principal_id=e.evaluador_id GROUP BY e.evento_id,e.club_id)""")
        if "version" not in columns:
            conn.execute("ALTER TABLE evaluaciones ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        columns = {r[1] for r in conn.execute("PRAGMA table_info(penalizaciones)")}
        if "puntos" not in columns:
            conn.execute("ALTER TABLE penalizaciones ADD COLUMN puntos REAL")
            conn.execute("UPDATE penalizaciones SET puntos=(SELECT puntos_descuento FROM motivos WHERE motivos.id=penalizaciones.motivo_id)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS evaluacion_oficial_unica ON evaluaciones(evento_id,club_id) WHERE oficial=1")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS participante_unico ON evento_club(evento_id,club_id)")
        conn.commit()


def save(db, connection=None):
    conn = connection or connect()
    try:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
            for item in db.get(table, []):
                row = dict(item) if isinstance(item, dict) else asdict(item)
                if table == "users":
                    row["password"] = _hash_pw(row["password"])
                for key in row:
                    if key in JSON_FIELDS:
                        row[key] = json.dumps(row[key], ensure_ascii=False)
                names = ",".join(row)
                placeholders = ",".join("?" for _ in row)
                conn.execute(f"INSERT INTO {table} ({names}) VALUES ({placeholders})", list(row.values()))
        if connection is None:
            conn.commit()
    finally:
        if connection is None:
            conn.close()


def load(connection=None):
    if connection is None:
        fresh = not os.path.exists(DB_PATH)
        initialize()
        if fresh:
            save(data.seed())
    conn = connection or connect()
    try:
        db = {}
        for table in TABLES:
            items = []
            for record in conn.execute(f"SELECT * FROM {table}"):
                row = dict(record)
                for key in row:
                    if key in JSON_FIELDS:
                        row[key] = json.loads(row[key])
                if table == "clubs":
                    row["miembros"] = [data.Miembro(**m) for m in row["miembros"]]
                if table == "users":
                    row["password"] = _hash_pw(row["password"])
                items.append(MODELS[table](**row) if table in MODELS else row)
            db[table] = items
        db["organizacion"] = db["organizaciones"][0] if db["organizaciones"] else {}
        return db
    finally:
        if connection is None:
            conn.close()


def _safe_name(nombre):
    name = os.path.basename(str(nombre or ""))
    if not name or name in {".", ".."}:
        raise ValueError("Nombre de evidencia inválido.")
    return name


def save_evidence(nombre, contenido, connection=None):
    """Guarda la foto en ``static/uploads``; ``connection`` se ignora en SQLite."""
    name = _safe_name(nombre)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(UPLOAD_DIR, name), "wb") as file:
        file.write(bytes(contenido))
    return name


def read_evidence(nombre):
    path = os.path.join(UPLOAD_DIR, _safe_name(nombre))
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as file:
        contenido = file.read()
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return contenido, mime
