"""Pruebas de inicialización Docker sin tocar bases ni claves personales."""

import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "scoreup_docker_start", Path(__file__).resolve().parents[1] / "docker" / "start.py"
)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class DockerStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="scoreup-docker-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "scoreup.db"
        self.enterContext(patch.dict(os.environ, {
            "SCOREUP_DATA_DIR": str(self.root), "SCOREUP_DB": str(self.database),
        }))
        # Importar después del entorno aislado, nunca fijar la ruta personal
        # de persist al descubrir este módulo antes de test_scoreup.py.
        import persist

        self.enterContext(patch.object(persist, "DB_PATH", str(self.database)))
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)

    def test_new_installation_has_schema_without_default_accounts(self):
        bootstrap.prepare_storage()
        with closing(sqlite3.connect(self.database)) as connection:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            self.assertEqual(len(tables), 11)
            for table in ("organizaciones", "users", "clubs", "eventos"):
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
        key = (self.root / ".secret_key").read_text().strip()
        self.assertEqual(len(key), 64)
        self.assertEqual(os.environ["SECRET_KEY"], key)
        self.assertTrue((self.root / "uploads").is_dir())

    def test_reinitialization_preserves_key_database_and_uploads(self):
        bootstrap.prepare_storage()
        key = (self.root / ".secret_key").read_bytes()
        photo = self.root / "uploads" / "test.txt"
        photo.write_text("isolated-test")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("INSERT INTO organizaciones VALUES ('test-org','Prueba','2026-11-17')")
        bootstrap.prepare_storage()
        self.assertEqual((self.root / ".secret_key").read_bytes(), key)
        self.assertEqual(photo.read_text(), "isolated-test")
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT nombre FROM organizaciones").fetchone(), ("Prueba",))

    def test_empty_key_fails_without_rotating_it_or_creating_database(self):
        key = self.root / ".secret_key"
        key.write_text("")
        with self.assertRaisesRegex(RuntimeError, "clave persistente"):
            bootstrap.prepare_storage()
        self.assertEqual(key.read_text(), "")
        self.assertFalse(self.database.exists())

    def test_persistent_key_is_used_instead_of_a_transient_environment_value(self):
        (self.root / ".secret_key").write_text("test-only-persistent-signing-key")
        os.environ["SECRET_KEY"] = "test-only-transient-key"
        bootstrap.prepare_storage()
        self.assertEqual(os.environ["SECRET_KEY"], "test-only-persistent-signing-key")


if __name__ == "__main__":
    unittest.main()
