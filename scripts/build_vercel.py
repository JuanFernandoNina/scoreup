"""Prepara los archivos estáticos que Vercel sirve desde ``public/**``.

El proyecto mantiene ``static/`` para Flask local/Docker. Este build copia solo
los recursos públicos (excluye ``uploads``) a ``public/static``; las evidencias
se sirven desde PostgreSQL mediante ``/evidencias/<nombre>``.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static"
DESTINATION = ROOT / "public" / "static"


def main():
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for item in SOURCE.iterdir():
        if item.name == "uploads":
            continue
        if item.is_dir():
            shutil.copytree(item, DESTINATION / item.name)
        elif item.is_file():
            shutil.copy2(item, DESTINATION / item.name)
    print(f"Estáticos copiados a {DESTINATION.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
