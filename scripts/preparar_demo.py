"""Instala la base de demostración sin reemplazar una base existente."""
import argparse
import getpass
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'demo' / 'scoreup-demo.db'
ROLES = ('admin', 'staff', 'director')


def preparar(destino, passwords, source=SOURCE):
    destino = Path(destino)
    if set(passwords) != set(ROLES) or any(len(p) < 8 for p in passwords.values()):
        raise ValueError('Define una contraseña de al menos 8 caracteres para cada rol.')
    # Modo exclusivo: nunca reemplazar datos del usuario, ni siquiera con --destino.
    with Path(source).open('rb') as original, destino.open('xb') as target:
        shutil.copyfileobj(original, target)
    try:
        with closing(sqlite3.connect(destino)) as db:
            with db:
                for rol, password in passwords.items():
                    db.execute('UPDATE users SET password=? WHERE rol=?', (generate_password_hash(password), rol))
                if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                    raise ValueError('La base no superó la comprobación de integridad.')
    except BaseException:
        destino.unlink()  # Solo el archivo que acaba de crear esta función.
        raise
    return destino


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destino', type=Path, default=ROOT / 'scoreup.db')
    args = parser.parse_args()
    if args.destino.exists():
        parser.exit(1, 'La base destino ya existe. Se conservó intacta. Usa --destino con un archivo nuevo.\n')
    print('Base de demostración. Elige contraseñas PRIVADAS para tu copia local.')
    print('Todas las cuentas de un mismo rol usarán la contraseña que elijas para ese rol.')
    passwords = {}
    for rol in ROLES:
        while True:
            first = getpass.getpass(f'Contraseña para {rol} (mínimo 8 caracteres): ')
            second = getpass.getpass('Repite la contraseña: ')
            if len(first) >= 8 and first == second:
                passwords[rol] = first
                break
            print('No coinciden o tienen menos de 8 caracteres. Intenta de nuevo.')
    try:
        path = preparar(args.destino, passwords)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f'No se pudo preparar la base: {error}\n')
    print(f'Base preparada: {path}')
    print('Usuarios principales: admin.campamento, staff.campamento, director.campamento.')
    print('Inicia con INICIAR.bat o con python app.py. No compartas tus contraseñas ni .secret_key.')


if __name__ == '__main__':
    main()
