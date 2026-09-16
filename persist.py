"""Persistencia SQLite para la demo de ScoreUp.

El modelo se mantiene en memoria (dataclasses de data.py) y cada request
guarda el estado completo en un archivo .db. Suficiente para la escala de
la demo y no obliga a reescribir toda la lógica de app.py/calc.py.
"""

import json
import os
import sqlite3

import data as seed_data
from data import (
    Club, Criterio, Evaluacion, Evento, EventoClub, Incidente, Miembro,
    MotivoPenalizacion, PenalizacionAplicada, Usuario,
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scoreup.db")

TABLES = [
    "organizaciones", "clubs", "users", "eventos", "criterios",
    "evento_club", "evaluaciones", "motivos", "penalizaciones", "incidentes",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS organizaciones (
    id TEXT PRIMARY KEY, nombre TEXT NOT NULL, fecha_creacion TEXT
);
CREATE TABLE IF NOT EXISTS clubs (
    id TEXT PRIMARY KEY, nombre TEXT NOT NULL, organizacion_id TEXT NOT NULL,
    miembros TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, organizacion_id TEXT NOT NULL, nombre TEXT NOT NULL,
    username TEXT NOT NULL, password TEXT NOT NULL, rol TEXT NOT NULL,
    evento_id TEXT, club_id TEXT
);
CREATE TABLE IF NOT EXISTS eventos (
    id TEXT PRIMARY KEY, organizacion_id TEXT NOT NULL, nombre TEXT NOT NULL,
    fecha TEXT, lugar TEXT, tipo TEXT, temporada TEXT,
    puntaje_maximo INTEGER NOT NULL, cerrado INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS criterios (
    id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, nombre TEXT NOT NULL, peso REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS evento_club (
    id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, club_id TEXT NOT NULL,
    staff_principal_id TEXT
);
CREATE TABLE IF NOT EXISTS evaluaciones (
    id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, club_id TEXT NOT NULL,
    evaluador_id TEXT NOT NULL, comentario TEXT, fecha TEXT, valores TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS motivos (
    id TEXT PRIMARY KEY, organizacion_id TEXT NOT NULL, nombre TEXT NOT NULL,
    descripcion TEXT, puntos_descuento REAL NOT NULL, activo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS penalizaciones (
    id TEXT PRIMARY KEY, club_id TEXT NOT NULL, evento_id TEXT NOT NULL,
    usuario_id TEXT NOT NULL, motivo_id TEXT NOT NULL,
    comentario TEXT, fecha TEXT
);
CREATE TABLE IF NOT EXISTS incidentes (
    id TEXT PRIMARY KEY, evento_id TEXT NOT NULL, usuario_id TEXT NOT NULL,
    tipo TEXT, gravedad TEXT, descripcion TEXT, estado TEXT,
    club_id TEXT, foto_url TEXT, fecha_hora TEXT
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema():
    conn = _conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _hash_pw(pw):
    """Migra contraseñas en texto plano a hash (werkzeug)."""
    if pw and pw.startswith(("scrypt:", "pbkdf2:")):
        return pw
    from werkzeug.security import generate_password_hash
    return generate_password_hash(pw or "")


# --------------------------------------------------------------------------
# Guardar
# --------------------------------------------------------------------------

def save(db):
    conn = _conn()
    try:
        cur = conn.cursor()
        for t in TABLES:
            cur.execute(f"DELETE FROM {t}")

        cur.executemany(
            "INSERT INTO organizaciones (id, nombre, fecha_creacion) VALUES (?,?,?)",
            [(o["id"], o["nombre"], o["fecha_creacion"]) for o in db["organizaciones"]],
        )
        cur.executemany(
            "INSERT INTO clubs (id, nombre, organizacion_id, miembros) VALUES (?,?,?,?)",
            [(c.id, c.nombre, c.organizacion_id,
              json.dumps([vars(m) for m in c.miembros])) for c in db["clubs"]],
        )
        cur.executemany(
            "INSERT INTO users (id, organizacion_id, nombre, username, password, rol, evento_id, club_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [(u.id, u.organizacion_id, u.nombre, u.username, _hash_pw(u.password),
              u.rol, u.evento_id, u.club_id) for u in db["users"]],
        )
        cur.executemany(
            "INSERT INTO eventos (id, organizacion_id, nombre, fecha, lugar, tipo, temporada, "
            "puntaje_maximo, cerrado) VALUES (?,?,?,?,?,?,?,?,?)",
            [(e.id, e.organizacion_id, e.nombre, e.fecha, e.lugar, e.tipo, e.temporada,
              e.puntaje_maximo, int(bool(e.cerrado))) for e in db["eventos"]],
        )
        cur.executemany(
            "INSERT INTO criterios (id, evento_id, nombre, peso) VALUES (?,?,?,?)",
            [(c.id, c.evento_id, c.nombre, c.peso) for c in db["criterios"]],
        )
        cur.executemany(
            "INSERT INTO evento_club (id, evento_id, club_id, staff_principal_id) VALUES (?,?,?,?)",
            [(x.id, x.evento_id, x.club_id, x.staff_principal_id) for x in db["evento_club"]],
        )
        cur.executemany(
            "INSERT INTO evaluaciones (id, evento_id, club_id, evaluador_id, comentario, fecha, valores) "
            "VALUES (?,?,?,?,?,?,?)",
            [(e.id, e.evento_id, e.club_id, e.evaluador_id, e.comentario, e.fecha,
              json.dumps(e.valores or {})) for e in db["evaluaciones"]],
        )
        cur.executemany(
            "INSERT INTO motivos (id, organizacion_id, nombre, descripcion, puntos_descuento, activo) "
            "VALUES (?,?,?,?,?,?)",
            [(m.id, m.organizacion_id, m.nombre, m.descripcion, m.puntos_descuento,
              int(bool(m.activo))) for m in db["motivos"]],
        )
        cur.executemany(
            "INSERT INTO penalizaciones (id, club_id, evento_id, usuario_id, motivo_id, comentario, fecha) "
            "VALUES (?,?,?,?,?,?,?)",
            [(p.id, p.club_id, p.evento_id, p.usuario_id, p.motivo_id, p.comentario, p.fecha)
             for p in db["penalizaciones"]],
        )
        cur.executemany(
            "INSERT INTO incidentes (id, evento_id, usuario_id, tipo, gravedad, descripcion, estado, "
            "club_id, foto_url, fecha_hora) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(i.id, i.evento_id, i.usuario_id, i.tipo, i.gravedad, i.descripcion, i.estado,
              i.club_id, i.foto_url, i.fecha_hora) for i in db["incidentes"]],
        )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Cargar
# --------------------------------------------------------------------------

def load():
    if not os.path.exists(DB_PATH):
        _init_schema()
        db = seed_data.seed()
        save(db)
        return db

    _init_schema()
    conn = _conn()
    try:
        cur = conn.cursor()
        organizaciones = [
            {"id": r["id"], "nombre": r["nombre"], "fecha_creacion": r["fecha_creacion"]}
            for r in cur.execute("SELECT * FROM organizaciones").fetchall()
        ]
        clubs = [
            Club(r["id"], r["nombre"], r["organizacion_id"],
                 [Miembro(**m) for m in json.loads(r["miembros"])])
            for r in cur.execute("SELECT * FROM clubs").fetchall()
        ]
        users = [
            Usuario(r["id"], r["organizacion_id"], r["nombre"], r["username"],
                    _hash_pw(r["password"]), r["rol"], r["evento_id"], r["club_id"])
            for r in cur.execute("SELECT * FROM users").fetchall()
        ]
        eventos = [
            Evento(r["id"], r["organizacion_id"], r["nombre"], r["fecha"], r["lugar"],
                   r["tipo"], r["temporada"], r["puntaje_maximo"], bool(r["cerrado"]))
            for r in cur.execute("SELECT * FROM eventos").fetchall()
        ]
        criterios = [
            Criterio(r["id"], r["evento_id"], r["nombre"], r["peso"])
            for r in cur.execute("SELECT * FROM criterios").fetchall()
        ]
        evento_club = [
            EventoClub(r["id"], r["evento_id"], r["club_id"], r["staff_principal_id"])
            for r in cur.execute("SELECT * FROM evento_club").fetchall()
        ]
        evaluaciones = [
            Evaluacion(r["id"], r["evento_id"], r["club_id"], r["evaluador_id"],
                       r["comentario"], r["fecha"], json.loads(r["valores"]))
            for r in cur.execute("SELECT * FROM evaluaciones").fetchall()
        ]
        motivos = [
            MotivoPenalizacion(r["id"], r["organizacion_id"], r["nombre"], r["descripcion"],
                               r["puntos_descuento"], bool(r["activo"]))
            for r in cur.execute("SELECT * FROM motivos").fetchall()
        ]
        penalizaciones = [
            PenalizacionAplicada(r["id"], r["club_id"], r["evento_id"], r["usuario_id"],
                                 r["motivo_id"], r["comentario"], r["fecha"])
            for r in cur.execute("SELECT * FROM penalizaciones").fetchall()
        ]
        incidentes = [
            Incidente(r["id"], r["evento_id"], r["usuario_id"], r["tipo"], r["gravedad"],
                      r["descripcion"], r["estado"], r["club_id"], r["foto_url"], r["fecha_hora"])
            for r in cur.execute("SELECT * FROM incidentes").fetchall()
        ]
    finally:
        conn.close()

    return {
        "organizacion": organizaciones[0] if organizaciones else {"id": "", "nombre": "", "fecha_creacion": ""},
        "organizaciones": organizaciones,
        "clubs": clubs,
        "users": users,
        "eventos": eventos,
        "criterios": criterios,
        "evento_club": evento_club,
        "evaluaciones": evaluaciones,
        "motivos": motivos,
        "penalizaciones": penalizaciones,
        "incidentes": incidentes,
    }
