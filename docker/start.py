"""Inicialización privada y persistente para la instalación Docker de ScoreUp."""

import os
from pathlib import Path
import secrets
import sys

# Permite importar persist desde /app al ejecutar python docker/start.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def prepare_storage():
    os.umask(0o077)
    directory = Path(os.environ.get("SCOREUP_DATA_DIR", "/data"))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "uploads").mkdir(exist_ok=True)
    key_file = directory / ".secret_key"
    try:
        with key_file.open("x", encoding="utf-8") as file:
            file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    key = key_file.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError("La clave persistente está vacía. No se reemplazó para proteger los QR existentes.")
    os.environ["SECRET_KEY"] = key
    os.environ["SCOREUP_DB"] = os.environ.get("SCOREUP_DB", str(directory / "scoreup.db"))

    import persist

    # Inicializar sin seed: la instalación nueva no crea usuarios ni claves públicas.
    # Una base ya existente conserva los datos y usa las migraciones de la aplicación.
    persist.initialize()


def main():
    prepare_storage()
    # Un solo proceso: app.py conserva estado compartido y RLock por proceso.
    # No aumentar workers ni réplicas sin refactorizar esa arquitectura.
    os.execvp("gunicorn", [
        "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4",
        "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "app:app",
    ])


if __name__ == "__main__":
    main()
