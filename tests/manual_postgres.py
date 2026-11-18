"""Integración opt-in, solo contra una base PostgreSQL local descartable *_test.

Define SCOREUP_TEST_DATABASE_URL y ejecuta este archivo; nunca acepta la URI
de producción de Supabase. Cada prueba reemplaza datos de ESA BASE TEMPORAL.
Requiere psycopg[binary] y TLS en el clúster local de pruebas.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
URL = os.environ.get("SCOREUP_TEST_DATABASE_URL", "")


def validate_test_url():
    parts = urlsplit(URL)
    if parts.hostname not in {"localhost", "127.0.0.1"} or not parts.path.endswith("_test"):
        raise RuntimeError("Usa únicamente una base local descartable cuyo nombre termine en _test.")


@unittest.skipUnless(URL, "Define SCOREUP_TEST_DATABASE_URL para la integración local PostgreSQL.")
class PostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        validate_test_url()
        os.environ.update(DATABASE_URL=URL, SCOREUP_DB_BACKEND="postgres",
                          SECRET_KEY="integration-test-only-not-for-production")
        import pg_store
        import data
        import app
        cls.pg, cls.data, cls.web = pg_store, data, app
        cls.pg.initialize()
        cls.web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True,
                                  PUBLIC_BASE_URL="https://scoreup.example.invalid")

    def setUp(self):
        self.pg.save(self.data.seed())
        with closing(self.pg.connect()) as conn:
            conn.execute("DELETE FROM evidencias")
            conn.commit()
        self.client = self.web.app.test_client()

    def tuples(self, table):
        with closing(self.pg.connect()) as conn:
            return {r["id"]: (r["xmin"], r["ctid"]) for r in conn.execute(
                f"SELECT id, xmin::text AS xmin, ctid::text AS ctid FROM {table}")}

    def user(self, user_id, client=None):
        client = client or self.client
        with client.session_transaction() as session:
            session["user_id"] = user_id
        return client

    def post(self, url, values, client=None):
        client = client or self.client
        page = client.get("/login")
        token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        return client.post(url, data={**values, "csrf_token": token})

    def test_one_event_change_preserves_other_physical_rows(self):
        users, events = self.tuples("users"), self.tuples("eventos")
        with closing(self.pg.connect()) as conn:
            self.pg.begin(conn, write=True)
            db = self.pg.load(conn)
            db["eventos"][0].nombre = "Nombre actualizado"
            self.pg.save(db, conn)
            conn.commit()
        self.assertEqual(users, self.tuples("users"))
        after = self.tuples("eventos")
        self.assertEqual(sum(after[key] != row for key, row in events.items()), 1)

    def test_no_change_preserves_every_operational_tuple(self):
        from persist import TABLES
        before = {table: self.tuples(table) for table in TABLES}
        with closing(self.pg.connect()) as conn:
            self.pg.begin(conn, write=True)
            self.pg.save(self.pg.load(conn), conn)
            conn.commit()
        self.assertEqual(before, {table: self.tuples(table) for table in TABLES})

    def test_nested_json_roundtrip(self):
        db = self.pg.load()
        club = db["clubs"][0]
        club.miembros[0].nombre = "Miembro de prueba modificado"
        self.pg.save(db)
        loaded = next(c for c in self.pg.load()["clubs"] if c.id == club.id)
        self.assertEqual(loaded.miembros[0].nombre, "Miembro de prueba modificado")

    def test_evidence_and_failed_evaluation_roll_back_together(self):
        import psycopg
        with closing(self.pg.connect()) as conn:
            self.pg.begin(conn, write=True)
            db = self.pg.load(conn)
            old = next(e for e in db["evaluaciones"] if e.oficial)
            db["evaluaciones"].append(self.data.Evaluacion("duplicate-official", old.evento_id,
                old.club_id, old.evaluador_id, valores=old.valores))
            self.pg.save_evidence("rollback.png", b"test", "image/png", conn)
            with self.assertRaises(psycopg.errors.UniqueViolation):
                self.pg.save(db, conn)
            conn.rollback()
        self.assertIsNone(self.pg.read_evidence("rollback.png"))
        self.assertFalse(any(e.id == "duplicate-official" for e in self.pg.load()["evaluaciones"]))

    def test_only_explicitly_removed_row_is_deleted(self):
        before = self.tuples("incidentes")
        db = self.pg.load()
        removed = db["incidentes"].pop(0).id
        self.pg.save(db)
        before.pop(removed)
        self.assertEqual(before, self.tuples("incidentes"))

    def test_official_replacement_does_not_violate_partial_index(self):
        db = self.pg.load()
        old = next(e for e in db["evaluaciones"] if e.oficial)
        old.oficial = False
        db["evaluaciones"].insert(0, self.data.Evaluacion("replacement", old.evento_id,
            old.club_id, old.evaluador_id, valores=old.valores))
        self.pg.save(db)
        official = [e for e in self.pg.load()["evaluaciones"]
                    if e.oficial and e.evento_id == old.evento_id and e.club_id == old.club_id]
        self.assertEqual([e.id for e in official], ["replacement"])

    def test_concurrent_writes_reload_after_advisory_lock(self):
        barrier = threading.Barrier(2)

        def evaluate(index):
            with closing(self.pg.connect()) as conn:
                barrier.wait(timeout=15)
                self.pg.begin(conn, write=True)
                db = self.pg.load(conn)
                if any(e.oficial and e.evento_id == "ev-3" and e.club_id == "club-1" for e in db["evaluaciones"]):
                    conn.rollback()
                    return "conflict"
                db["evaluaciones"].append(self.data.Evaluacion(f"concurrent-{index}", "ev-3", "club-1",
                    "user-staff4", valores={"cr-7": 80, "cr-8": 80, "cr-9": 80}))
                self.pg.save(db, conn)
                conn.commit()
                return "saved"

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(evaluate, range(2))), ["conflict", "saved"])

    def test_cloud_login_does_not_rewrite_rows_and_roles_remain_enforced(self):
        users = self.tuples("users")
        response = self.post("/login", {"username": "admin", "password": "admin"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/admin").status_code, 200)
        self.assertEqual(self.tuples("users"), users)
        self.user("user-dir1")
        self.assertEqual(self.client.get("/admin").status_code, 403)
        self.assertEqual(self.client.get("/director/qr.png").status_code, 200)

    def test_cloud_form_insert_evaluation_and_stale_edit(self):
        self.user("user-admin")
        users = self.tuples("users")
        response = self.post("/admin/eventos", {"nombre": "Evento HTTP", "fecha": "2026-11-17",
                                               "temporada": "2026", "puntaje_maximo": "100"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(e.nombre == "Evento HTTP" for e in self.pg.load()["eventos"]))
        self.assertEqual(self.tuples("users"), users)
        self.user("user-staff4")
        values = {"val_cr-7": "80", "val_cr-8": "80", "val_cr-9": "80", "version": "0"}
        self.assertEqual(self.post("/staff/evaluar/club-1", values).status_code, 302)
        self.assertEqual(self.post("/staff/evaluar/club-1", values).status_code, 409)
        values.update(version="1", **{"val_cr-7": "90"})
        self.assertEqual(self.post("/staff/evaluar/club-1", values).status_code, 302)
        db = self.pg.load()
        self.assertEqual(len(db["correcciones"]), 1)
        self.assertEqual(next(e.version for e in db["evaluaciones"] if e.evento_id == "ev-3" and e.club_id == "club-1"), 2)

    def test_other_organization_is_not_modified_by_admin_request(self):
        db = self.pg.load()
        db["organizaciones"].append({"id": "foreign-org", "nombre": "Otra organización", "fecha_creacion": "2026-11-17"})
        db["clubs"].append(self.data.Club("foreign-club", "Club privado de otra organización", "foreign-org", []))
        self.pg.save(db)
        before = self.tuples("clubs")["foreign-club"]
        self.user("user-admin")
        self.assertNotIn(b"Club privado de otra", self.client.get("/admin/clubes").data)
        self.assertEqual(self.post("/admin/clubes/foreign-club/editar", {"nombre": "No autorizado"}).status_code, 302)
        self.assertEqual(before, self.tuples("clubs")["foreign-club"])
        self.assertEqual(next(c.nombre for c in self.pg.load()["clubs"] if c.id == "foreign-club"), "Club privado de otra organización")

    def test_cloud_evidence_and_projection(self):
        self.pg.save_evidence("evidence.png", b"test-bytes", "image/png")
        self.assertEqual(self.pg.read_evidence("evidence.png"), (b"test-bytes", "image/png"))
        db = self.pg.load()
        incident = next(i for i in db["incidentes"] if i.evento_id == "ev-3")
        incident.foto_url = "/evidencias/evidence.png"
        self.pg.save(db)
        self.user("user-admin")
        self.assertEqual(self.client.get("/admin/mostrar-resultado?temporada=2026&pantalla=1").status_code, 200)
        for path in ["/evidencias/evidence.png", "/static/uploads/evidence.png"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"test-bytes")
            response.close()
        self.user("user-dir1")
        self.assertEqual(self.client.get("/static/uploads/evidence.png").status_code, 403)

    def test_plain_dict_replace_preserves_migration_contract(self):
        self.pg.save({table: [] for table in self.pg.TABLES})
        self.assertFalse(self.pg.load()["users"])
        self.pg.save(self.data.seed())
        self.assertEqual(len(self.pg.load()["users"]), 10)

    def test_migration_cli_dry_run_protection_and_explicit_replace(self):
        import persist
        with tempfile.TemporaryDirectory(prefix="scoreup-pg-migration-") as directory:
            source = Path(directory) / "source.db"
            uploads = Path(directory) / "uploads"
            uploads.mkdir()
            (uploads / "migration.png").write_bytes(b"migration-test")
            previous_path = persist.DB_PATH
            try:
                persist.DB_PATH = str(source)
                persist.initialize()
                persist.save(self.data.seed())
            finally:
                persist.DB_PATH = previous_path
            command = [sys.executable, str(ROOT / "scripts" / "migrate_supabase.py"),
                       "--sqlite", str(source), "--uploads", str(uploads)]
            before = self.tuples("users")
            dry = subprocess.run([*command, "--replace"], capture_output=True, cwd=ROOT)
            self.assertEqual(dry.returncode, 0, dry.stderr.decode(errors="replace"))
            self.assertEqual(before, self.tuples("users"))
            protected = subprocess.run([*command, "--apply"], capture_output=True, cwd=ROOT)
            self.assertNotEqual(protected.returncode, 0)
            applied = subprocess.run([*command, "--replace", "--apply"], capture_output=True, cwd=ROOT)
            self.assertEqual(applied.returncode, 0, applied.stderr.decode(errors="replace"))
            self.assertEqual(self.pg.read_evidence("migration.png"), (b"migration-test", "image/png"))
            self.assertEqual(len(self.pg.load()["users"]), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
