"""Selección de persistencia: SQLite local y PostgreSQL en Vercel/Supabase.

El backend se elige de forma explícita para no alterar las instalaciones locales:
- local/Docker: sin variables cloud -> ``persist`` (SQLite y archivos locales);
- Vercel: ``SCOREUP_DB_BACKEND=postgres`` y ``DATABASE_URL`` -> ``pg_store``.

Todas las funciones expuestas conservan la firma usada por ``app.py``.
"""

import os

import persist
import pg_store


CLOUD_BACKEND = "postgres"


def is_cloud():
    return os.environ.get("SCOREUP_DB_BACKEND", "").strip().lower() == CLOUD_BACKEND


def _backend():
    return pg_store if is_cloud() else persist


def connect():
    return _backend().connect()


def begin(connection, write=False):
    backend = _backend()
    if backend is pg_store:
        backend.begin(connection, write=write)
    else:
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")


def initialize():
    return _backend().initialize()


def load(connection=None):
    return _backend().load(connection)


def save(db, connection=None):
    return _backend().save(db, connection)


def save_evidence(nombre, contenido, tipo=None, connection=None):
    """Guarda una evidencia. En cloud se usa la misma transacción de la petición."""
    if is_cloud():
        return pg_store.save_evidence(nombre, contenido, tipo, connection)
    return persist.save_evidence(nombre, contenido, connection)


def read_evidence(nombre, connection=None):
    """Devuelve ``(bytes, mimetype)`` o ``None`` si no existe."""
    if is_cloud():
        return pg_store.read_evidence(nombre, connection)
    return persist.read_evidence(nombre)
