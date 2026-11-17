"""Migra la base SQLite local y las evidencias a Supabase PostgreSQL.

Uso:
    DATABASE_URL='postgresql://...' .venv/Scripts/python.exe scripts/migrate_supabase.py --apply

Sin ``--apply`` solo muestra el plan. La cadena de conexión se lee del entorno,
nunca se guarda ni se imprime. ``--replace`` autoriza borrar datos previos en la
tabla destino; sin él la migración se detiene si la base de destino no está vacía.
"""

import argparse
import mimetypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persist
import pg_store


def _safe_name(nombre):
    name = os.path.basename(str(nombre or ""))
    if not name or name in {".", ".."}:
        raise ValueError("Nombre de evidencia inválido.")
    return name


def main():
    parser = argparse.ArgumentParser(description="Migra ScoreUp de SQLite a Supabase PostgreSQL.")
    parser.add_argument("--sqlite", default=os.environ.get("SCOREUP_DB", str(ROOT / "scoreup.db")),
                        help="Ruta de la base SQLite de origen.")
    parser.add_argument("--uploads", default=str(ROOT / "static" / "uploads"),
                        help="Carpeta con las fotos de evidencia.")
    parser.add_argument("--replace", action="store_true", help="Permite reemplazar datos previos en PostgreSQL.")
    parser.add_argument("--apply", action="store_true", help="Ejecuta la migración; sin esta opción es un simulacro.")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL") and not os.environ.get("SCOREUP_DB_URL"):
        raise SystemExit("Define DATABASE_URL (transaction pooler de Supabase) antes de migrar.")
    if not Path(args.sqlite).is_file():
        raise SystemExit(f"No existe la base SQLite de origen: {args.sqlite}")

    original = persist.DB_PATH
    persist.DB_PATH = args.sqlite
    try:
        db = persist.load()
    finally:
        persist.DB_PATH = original

    uploads = Path(args.uploads)
    evidencias = []
    if uploads.is_dir():
        for path in sorted(uploads.iterdir()):
            if not path.is_file():
                continue
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            evidencias.append((path.name, path.read_bytes(), mime))

    conn = pg_store.connect()
    try:
        pg_store.begin(conn, write=True)
        pg_store.initialize(conn)
        destino = conn.execute("SELECT COUNT(*) AS total FROM organizaciones").fetchone()["total"]
        if destino and not args.replace:
            raise SystemExit("La base de destino ya tiene datos. Usa --replace si deseas reemplazarlos.")
        print(f"SQLite: {len(db['organizaciones'])} organización(es), "
              f"{sum(len(v) for v in db.values() if isinstance(v, list))} registros, "
              f"{len(evidencias)} evidencia(s).")
        if not args.apply:
            print("Simulacro: no se escribió nada. Agrega --apply para ejecutar.")
            conn.rollback()
            return
        pg_store.save(db, conn)
        for nombre, contenido, mime in evidencias:
            pg_store.save_evidence(nombre, contenido, mime, conn)
        conn.commit()
        print("Migración completada.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
