"""Backend PostgreSQL para el despliegue serverless de ScoreUp.

Se usa solo cuando ``SCOREUP_DB_BACKEND=postgres``. Mantiene el mismo contrato
que ``persist.py`` para que ``app.py`` no tenga lógica específica por motor.

Supabase en serverless exige el transaction pooler, ``sslmode=require`` y
desactivar prepared statements; por eso la conexión usa ``prepare_threshold=None``.
Las escrituras se serializan con un advisory lock de transacción para reproducir
el ``BEGIN IMMEDIATE`` de SQLite entre varias instancias de Vercel.
"""

import json
import os
import threading
from dataclasses import asdict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from werkzeug.security import generate_password_hash

import data
from persist import JSON_FIELDS, MODELS, TABLES


LOCK_KEY = 2026111701
BOOL_FIELDS = {"cerrado", "oficial", "activo"}
_init_lock = threading.Lock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS organizaciones (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha_creacion TEXT
);
CREATE TABLE IF NOT EXISTS clubs (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    organizacion_id TEXT NOT NULL,
    miembros TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    organizacion_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    rol TEXT NOT NULL,
    evento_id TEXT,
    club_id TEXT
);
CREATE TABLE IF NOT EXISTS eventos (
    id TEXT PRIMARY KEY,
    organizacion_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    fecha TEXT,
    lugar TEXT,
    tipo TEXT,
    temporada TEXT,
    puntaje_maximo INTEGER NOT NULL,
    cerrado BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS criterios (
    id TEXT PRIMARY KEY,
    evento_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    peso DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS evento_club (
    id TEXT PRIMARY KEY,
    evento_id TEXT NOT NULL,
    club_id TEXT NOT NULL,
    staff_principal_id TEXT
);
CREATE TABLE IF NOT EXISTS evaluaciones (
    id TEXT PRIMARY KEY,
    evento_id TEXT NOT NULL,
    club_id TEXT NOT NULL,
    evaluador_id TEXT NOT NULL,
    comentario TEXT,
    fecha TEXT,
    valores TEXT NOT NULL,
    oficial BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS motivos (
    id TEXT PRIMARY KEY,
    organizacion_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    puntos_descuento DOUBLE PRECISION NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS penalizaciones (
    id TEXT PRIMARY KEY,
    club_id TEXT NOT NULL,
    evento_id TEXT NOT NULL,
    usuario_id TEXT NOT NULL,
    motivo_id TEXT NOT NULL,
    comentario TEXT,
    fecha TEXT,
    puntos DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS incidentes (
    id TEXT PRIMARY KEY,
    evento_id TEXT NOT NULL,
    usuario_id TEXT NOT NULL,
    tipo TEXT,
    gravedad TEXT,
    descripcion TEXT,
    estado TEXT,
    club_id TEXT,
    foto_url TEXT,
    fecha_hora TEXT
);
CREATE TABLE IF NOT EXISTS correcciones (
    id TEXT PRIMARY KEY,
    evento_id TEXT NOT NULL,
    club_id TEXT NOT NULL,
    evaluador_id TEXT NOT NULL,
    fecha TEXT NOT NULL,
    anterior TEXT NOT NULL,
    actual TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'pendiente'
);
CREATE TABLE IF NOT EXISTS evidencias (
    nombre TEXT PRIMARY KEY,
    contenido BYTEA NOT NULL,
    tipo TEXT NOT NULL,
    creado TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS evaluacion_oficial_unica
    ON evaluaciones(evento_id, club_id) WHERE oficial;
CREATE UNIQUE INDEX IF NOT EXISTS participante_unico
    ON evento_club(evento_id, club_id);
"""


def _dsn():
    raw = os.environ.get("SCOREUP_DB_URL") or os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("Falta DATABASE_URL para usar el backend PostgreSQL.")
    parts = urlsplit(raw)
    scheme = "postgresql" if parts.scheme == "postgres" else parts.scheme
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["sslmode"] = "require"
    query.pop("connect_timeout", None)
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def connect():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(
        _dsn(),
        autocommit=False,
        row_factory=dict_row,
        prepare_threshold=None,
        connect_timeout=10,
    )


def begin(connection, write=False):
    """Inicia la transacción lógica; bloquea escrituras entre instancias.

    Las escrituras usan READ COMMITTED para que, después de esperar el lock,
    la lectura vea los cambios confirmados por la transacción anterior. Las
    lecturas fijan un snapshot consistente con REPEATABLE READ.
    """
    if write:
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
    else:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        connection.execute("SELECT 1")


def _hash_pw(password):
    if password and password.startswith(("scrypt:", "pbkdf2:")):
        return password
    return generate_password_hash(password or "")


def _safe_name(nombre):
    name = os.path.basename(str(nombre or ""))
    if not name or name in {".", ".."}:
        raise ValueError("Nombre de evidencia inválido.")
    return name


def initialize(connection=None):
    global _initialized
    own = connection is None
    conn = connection or connect()
    try:
        for statement in SCHEMA.split(";"):
            if statement.strip():
                conn.execute(statement)
        if own:
            conn.commit()
            _initialized = True
    finally:
        if own:
            conn.rollback()
            conn.close()


def ensure_initialized():
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if not _initialized:
            initialize()


def _decode_json(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def load(connection=None):
    own = connection is None
    ensure_initialized()
    conn = connection or connect()
    try:
        db = {}
        for table in TABLES:
            items = []
            for record in conn.execute(f"SELECT * FROM {table}"):
                row = dict(record)
                for key in JSON_FIELDS:
                    if key in row:
                        row[key] = _decode_json(row[key])
                if table == "clubs":
                    row["miembros"] = [data.Miembro(**m) for m in (row["miembros"] or [])]
                if table == "users":
                    row["password"] = _hash_pw(row["password"])
                items.append(MODELS[table](**row) if table in MODELS else row)
            db[table] = items
        db["organizacion"] = db["organizaciones"][0] if db["organizaciones"] else {}
        return db
    finally:
        if own:
            conn.rollback()
            conn.close()


def save(db, connection=None):
    own = connection is None
    if own:
        ensure_initialized()
    conn = connection or connect()
    try:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
            for item in db.get(table, []):
                row = dict(item) if isinstance(item, dict) else asdict(item)
                if table == "users":
                    row["password"] = _hash_pw(row["password"])
                for key in JSON_FIELDS:
                    if key in row and not isinstance(row[key], str):
                        row[key] = json.dumps(row[key], ensure_ascii=False)
                for key in BOOL_FIELDS:
                    if key in row:
                        row[key] = bool(row[key])
                names = ",".join(row)
                placeholders = ",".join("%s" for _ in row)
                conn.execute(
                    f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
                    list(row.values()),
                )
        if own:
            conn.commit()
    finally:
        if own:
            conn.rollback()
            conn.close()


def save_evidence(nombre, contenido, tipo=None, connection=None):
    own = connection is None
    if own:
        ensure_initialized()
    conn = connection or connect()
    try:
        conn.execute(
            """INSERT INTO evidencias (nombre, contenido, tipo)
               VALUES (%s, %s, %s)
               ON CONFLICT (nombre) DO UPDATE
               SET contenido = EXCLUDED.contenido,
                   tipo = EXCLUDED.tipo,
                   creado = now()""",
            (_safe_name(nombre), bytes(contenido), tipo or "application/octet-stream"),
        )
        if own:
            conn.commit()
    finally:
        if own:
            conn.rollback()
            conn.close()
    return _safe_name(nombre)


def read_evidence(nombre, connection=None):
    own = connection is None
    if own:
        ensure_initialized()
    conn = connection or connect()
    try:
        row = conn.execute(
            "SELECT contenido, tipo FROM evidencias WHERE nombre = %s",
            (_safe_name(nombre),),
        ).fetchone()
        if row is None:
            return None
        return bytes(row["contenido"]), row["tipo"]
    finally:
        if own:
            conn.rollback()
            conn.close()
