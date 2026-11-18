"""Contrato incremental PostgreSQL sin conexión ni secretos de producción."""

from contextlib import contextmanager
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import data
import pg_store
from persist import TABLES


class Result:
    def __init__(self, state):
        self.state = state

    def fetchone(self):
        return {"state": deepcopy(self.state)}


class Connection:
    def __init__(self, state):
        self.state = state
        self.calls = []
        self.pipelines = 0
        self.commits = self.rollbacks = self.closed = 0

    def execute(self, sql, params=None, **options):
        self.calls.append((sql, params))
        return Result(self.state)

    @contextmanager
    def pipeline(self):
        self.pipelines += 1
        yield

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


def state():
    seed = data.seed()
    # Solo muestras ficticias; evita generar nuevos hashes en cada caso.
    for user in seed["users"]:
        user.password = "scrypt:test-only"
    return {table: [pg_store._row(table, item) for item in seed[table]] for table in TABLES}


class PostgreSQLIncrementalTests(unittest.TestCase):
    def setUp(self):
        self.connection = Connection(state())
        self.patch = patch.object(pg_store, "ensure_initialized")
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.db = pg_store.load(self.connection)
        self.connection.calls.clear()

    def test_snapshot_uses_one_select_and_restores_models(self):
        loaded = pg_store.load(self.connection)
        self.assertEqual(len(self.connection.calls), 1)
        self.assertIn("json_build_object", self.connection.calls[0][0])
        self.assertIsInstance(loaded["clubs"][0].miembros[0], data.Miembro)
        self.assertIsInstance(loaded["eventos"][0].cerrado, bool)
        self.assertEqual(set(loaded), {*TABLES, "organizacion"})
        before = deepcopy(loaded.original_rows)
        loaded["clubs"][0].miembros[0].nombre = "Nombre ficticio actualizado"
        loaded["evaluaciones"][0].valores["cr-1"] = 44
        self.assertEqual(loaded.original_rows, before)

    def test_no_change_has_no_database_writes_or_pipeline(self):
        pg_store.save(self.db, self.connection)
        self.assertEqual(self.connection.calls, [])
        self.assertEqual(self.connection.pipelines, 0)

    def test_only_modified_event_is_upserted(self):
        self.db["eventos"][0].nombre = "Evento actualizado"
        pg_store.save(self.db, self.connection)
        self.assertEqual(len(self.connection.calls), 1)
        sql, params = self.connection.calls[0]
        self.assertIn("INSERT INTO eventos", sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", sql)
        self.assertEqual([r["id"] for r in json.loads(params[0])], ["ev-1"])
        self.assertEqual(self.connection.pipelines, 1)
        self.assertEqual(self.connection.commits, 0)

    def test_nested_json_change_does_not_touch_other_rows(self):
        self.db["clubs"][0].miembros[0].nombre = "Miembro ficticio"
        pg_store.save(self.db, self.connection)
        sql, params = self.connection.calls[0]
        self.assertIn("INSERT INTO clubs", sql)
        rows = json.loads(params[0])
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0]["miembros"])[0]["nombre"], "Miembro ficticio")

    def test_delete_is_restricted_to_removed_ids(self):
        self.db["incidentes"].pop(0)
        pg_store.save(self.db, self.connection)
        self.assertEqual(self.connection.calls, [("DELETE FROM incidentes WHERE id = ANY(%s)", (["inc-1"],))])

    def test_bulk_insert_is_one_statement_not_one_per_row(self):
        self.db["eventos"].extend(data.Evento(f"new-{i}", "org-1", "Nuevo", "", "", "", "2026", 100)
                                  for i in range(100))
        pg_store.save(self.db, self.connection)
        self.assertEqual(len(self.connection.calls), 1)
        self.assertEqual(len(json.loads(self.connection.calls[0][1][0])), 100)

    def test_read_baseline_is_not_advanced_before_commit(self):
        original = deepcopy(self.db.original_rows)
        self.db["eventos"][0].nombre = "Cambio que puede revertirse"
        pg_store.save(self.db, self.connection)
        self.assertEqual(self.db.original_rows, original)
        self.assertEqual(self.connection.commits, 0)

    def test_official_replacement_releases_only_affected_key_first(self):
        old = self.db["evaluaciones"][0]
        old.oficial = False
        self.db["evaluaciones"].append(data.Evaluacion("replacement", old.evento_id, old.club_id,
                                                       old.evaluador_id, valores=old.valores))
        pg_store.save(self.db, self.connection)
        self.assertEqual(len(self.connection.calls), 2)
        self.assertEqual(self.connection.calls[0], ("DELETE FROM evaluaciones WHERE id = ANY(%s)", ([old.id],)))
        self.assertIn("INSERT INTO evaluaciones", self.connection.calls[1][0])

    def test_plain_dict_migration_compares_destination_and_keeps_replace_semantics(self):
        replacement = {table: [] for table in TABLES}
        replacement["organizaciones"] = [{"id": "new-org", "nombre": "Nueva", "fecha_creacion": "2026-11-17"}]
        pg_store.save(replacement, self.connection)
        self.assertIn("SELECT json_build_object", self.connection.calls[0][0])
        deletes = [sql for sql, _ in self.connection.calls if sql.startswith("DELETE")]
        self.assertTrue(deletes)
        self.assertTrue(all("WHERE id = ANY(%s)" in sql for sql in deletes))
        self.assertIn("INSERT INTO organizaciones", self.connection.calls[-1][0])

    def test_duplicate_ids_fail_before_any_write(self):
        self.db["clubs"].append(self.db["clubs"][0])
        with self.assertRaises(ValueError):
            pg_store.save(self.db, self.connection)
        self.assertEqual(self.connection.calls, [])

    def test_owned_connection_is_locked_committed_and_closed(self):
        self.db["eventos"][0].nombre = "Otro nombre"
        with patch.object(pg_store, "connect", return_value=self.connection):
            pg_store.save(self.db)
        self.assertIn("pg_advisory_xact_lock", self.connection.calls[0][0])
        self.assertEqual(self.connection.commits, 1)
        self.assertEqual(self.connection.closed, 1)

    def test_owned_connection_rolls_back_on_error(self):
        self.db["clubs"].append(self.db["clubs"][0])
        with patch.object(pg_store, "connect", return_value=self.connection):
            with self.assertRaises(ValueError):
                pg_store.save(self.db)
        self.assertEqual(self.connection.commits, 0)
        self.assertEqual(self.connection.rollbacks, 1)
        self.assertEqual(self.connection.closed, 1)

    def test_read_transaction_needs_no_extra_select(self):
        pg_store.begin(self.connection)
        self.assertEqual(len(self.connection.calls), 1)
        self.assertEqual(self.connection.calls[0][0], "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

    def test_database_url_has_documented_precedence_and_requires_tls(self):
        with patch.dict("os.environ", {"DATABASE_URL": "postgres://user:example@localhost/primary?sslmode=disable",
                                       "SCOREUP_DB_URL": "postgresql://user:example@localhost/secondary"}):
            dsn = pg_store._dsn()
        self.assertIn("/primary?", dsn)
        self.assertIn("sslmode=require", dsn)
        self.assertTrue(dsn.startswith("postgresql://"))


if __name__ == "__main__":
    unittest.main()
