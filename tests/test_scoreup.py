"""Pruebas contra SQLite temporal: nunca modifican scoreup.db del usuario."""

import io
import os
import re
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

_startup = tempfile.TemporaryDirectory(prefix="scoreup-tests-")
os.environ["SCOREUP_DB"] = str(Path(_startup.name) / "startup.db")
os.environ["SECRET_KEY"] = "test-only-not-for-deployment"

import app as web
import calc
import data
import persist
from PIL import Image


class ScoreUpTests(unittest.TestCase):
    def test_anonymous_public_pages_and_static_assets_do_not_connect_database(self):
        with patch.object(web.store, "connect", side_effect=AssertionError("Unexpected DB access")):
            for path in ["/", "/login", "/registro", "/static/app-utilities.css"]:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                response.close()

    def test_login_is_read_only_and_does_not_save_all_data(self):
        token = self.token()
        with patch.object(web.store, "begin", wraps=web.store.begin) as begin, patch.object(web.store, "save") as save:
            response = self.client.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(begin.call_args.kwargs["write"])
        save.assert_not_called()

    def test_shared_demo_preparation_and_preserved_results(self):
        from scripts.preparar_demo import preparar, SOURCE
        from werkzeug.security import check_password_hash
        destination = Path(self.directory.name) / 'friend.db'
        passwords = {'admin': 'admin-test-only-2026', 'staff': 'staff-test-only-2026', 'director': 'director-test-only-2026'}
        source_bytes = SOURCE.read_bytes()
        preparar(destination, passwords)
        self.assertEqual(SOURCE.read_bytes(), source_bytes)
        with closing(sqlite3.connect(destination)) as connection:
            for username, role, password in connection.execute('SELECT username,rol,password FROM users'):
                self.assertTrue(check_password_hash(password, passwords[role]), username)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM eventos WHERE id LIKE 'ev-camp-%' AND cerrado=1").fetchone()[0], 4)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM evaluaciones WHERE evento_id LIKE 'ev-demo-20261117-%'").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM penalizaciones WHERE id LIKE 'pen-demo-20261117-%'").fetchone()[0], 5)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM incidentes WHERE foto_url IS NOT NULL AND foto_url != ''").fetchone()[0], 0)
        before = destination.read_bytes()
        with self.assertRaises(FileExistsError):
            preparar(destination, passwords)
        self.assertEqual(destination.read_bytes(), before)
        persist.DB_PATH = str(destination)
        for username, role, path in [('admin.campamento', 'admin', '/admin'), ('staff.campamento', 'staff', '/staff'), ('director.campamento', 'director', '/director')]:
            self.client.get('/logout')
            response = self.post('/login', {'username': username, 'password': passwords[role]})
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith(path))
            panel = self.client.get(path)
            self.assertEqual(panel.status_code, 200)
            if role == 'director':
                self.assertIn(b'333.36', panel.data)

    def test_shared_demo_rejects_short_or_missing_passwords(self):
        from scripts.preparar_demo import preparar
        destination = Path(self.directory.name) / 'invalid.db'
        with self.assertRaises(ValueError):
            preparar(destination, {'admin': 'short'})
        self.assertFalse(destination.exists())

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="scoreup-test-")
        self.addCleanup(self.directory.cleanup)
        persist.DB_PATH = str(Path(self.directory.name) / "test.db")
        web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True, PUBLIC_BASE_URL="http://192.168.1.10:5000")
        persist.load()
        self.client = web.app.test_client()

    def token(self, client=None, path="/login"):
        response = (client or self.client).get(path)
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match, response.data[:400])
        return match.group(1).decode()

    def as_user(self, user_id, client=None):
        client = client or self.client
        with client.session_transaction() as session:
            session.clear()
            session["user_id"] = user_id
        return client

    def post(self, path, values=None, client=None):
        client = client or self.client
        values = dict(values or {})
        values["csrf_token"] = self.token(client)
        return client.post(path, data=values)

    def values(self, value=80, version=0):
        return {"val_cr-7": str(value), "val_cr-8": str(value), "val_cr-9": str(value), "version": str(version)}

    def add_second_staff(self):
        db = persist.load()
        db["users"].append(data.Usuario("other-staff", "org-1", "Otro", "otro", "testing", "staff", evento_id="ev-3"))
        persist.save(db)

    def test_anonymous_and_role_permissions(self):
        for path in ["/admin", "/staff", "/director", "/admin/clubes/club-1/qr"]:
            self.assertEqual(self.client.get(path).status_code, 302)
        self.as_user("user-dir1")
        self.assertEqual(self.client.get("/admin").status_code, 403)

    def test_csrf_is_required(self):
        self.assertEqual(self.client.post("/login", data={"username": "admin", "password": "admin"}).status_code, 400)

    def test_complete_new_organization_workflow(self):
        response = self.post("/registro", {"nombre": "Nuevo Admin", "username": "nuevo", "password": "solo-testing-123", "organizacion": "Organización de prueba"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.post("/admin/clubes", {"nombre": "Club nuevo"}).status_code, 302)
        self.assertEqual(self.post("/admin/eventos", {"nombre": "Evento nuevo", "fecha": "2026-10-21", "temporada": "2026", "puntaje_maximo": "100"}).status_code, 302)
        db = persist.load()
        club = next(c for c in db["clubs"] if c.nombre == "Club nuevo")
        event = next(e for e in db["eventos"] if e.nombre == "Evento nuevo")
        self.assertEqual(self.post(f"/admin/eventos/{event.id}/criterio", {"nombre": "Criterio único", "peso": "100"}).status_code, 302)
        self.assertEqual(self.post(f"/admin/eventos/{event.id}/asignar", {"club_id": club.id}).status_code, 302)
        self.assertEqual(self.post(f"/admin/eventos/{event.id}/staff/nuevo", {"nombre": "Evaluador nuevo", "username": "evaluador-nuevo", "password": "solo-testing-456"}).status_code, 302)
        self.client.get("/logout")
        qr = "/qr/" + web._token_club(club)
        response = self.post("/login", {"username": "evaluador-nuevo", "password": "solo-testing-456", "next": qr})
        self.assertEqual(response.location, qr)
        self.assertEqual(self.client.get(qr, follow_redirects=True).status_code, 200)
        db = persist.load()
        criterion = next(c for c in db["criterios"] if c.evento_id == event.id)
        self.assertEqual(self.post(f"/staff/evaluar/{club.id}", {f"val_{criterion.id}": "95", "version": "0"}).status_code, 302)
        self.client.get("/logout")
        self.post("/login", {"username": "nuevo", "password": "solo-testing-123"})
        self.assertEqual(self.post(f"/admin/eventos/{event.id}/cerrar").status_code, 302)
        response = self.client.get(f"/admin/exportar?formato=pdf&vista=evento&evento_id={event.id}")
        self.assertEqual(response.status_code, 200)

    def test_criteria_and_participation_freeze_after_evaluation(self):
        self.as_user("user-admin")
        self.assertEqual(self.post("/admin/eventos/ev-3/criterio", {"nombre": "Extra", "peso": "5"}).status_code, 409)
        self.assertEqual(self.post("/admin/eventos/ev-3/desasignar/club-2").status_code, 409)

    def test_director_only_sees_published_events_and_zero_score(self):
        self.as_user("user-staff4")
        self.post("/staff/evaluar/club-1", self.values(0))
        self.as_user("user-dir1")
        response = self.client.get("/director")
        self.assertNotIn(b"Campamento Regional", response.data)
        db = persist.load()
        calc.find(db, "eventos", "id", "ev-3").cerrado = True
        persist.save(db)
        response = self.client.get("/director")
        self.assertIn(b"Campamento Regional", response.data)
        self.assertIn(b"0 pts", response.data)

    def test_director_dashboard_displays_own_club_qr(self):
        self.as_user("user-dir1")
        response = self.client.get("/director")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="qr-de-mi-club"', response.data)
        self.assertIn(b'src="/director/qr.png"', response.data)
        self.assertIn(b'Descargar QR en PNG', response.data)
        self.assertNotIn(b"/admin/clubes/club-2/qr", response.data)

    def test_director_qr_matches_admin_card_and_does_not_write(self):
        self.as_user("user-admin")
        admin = self.client.get("/admin/clubes/club-1/qr?formato=png")
        self.as_user("user-dir1")
        before = Path(persist.DB_PATH).read_bytes()
        response = self.client.get("/director/qr.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.data, admin.data)
        self.assertTrue(response.headers["Content-Disposition"].startswith("inline"))
        self.assertEqual(Path(persist.DB_PATH).read_bytes(), before)
        image = Image.open(io.BytesIO(response.data))
        self.assertEqual(image.format, "PNG")
        download = self.client.get("/director/qr.png?descargar=1")
        self.assertTrue(download.headers["Content-Disposition"].startswith("attachment"))
        self.assertEqual(download.data, response.data)

    def test_director_qr_cannot_select_other_club_or_server(self):
        self.as_user("user-dir1")
        expected = self.client.get("/director/qr.png").data
        attempted = self.client.get("/director/qr.png?club_id=club-2&base_url=https://example.com").data
        self.assertEqual(attempted, expected)
        self.as_user("user-dir2")
        self.assertNotEqual(self.client.get("/director/qr.png").data, expected)

    def test_director_qr_requires_role_and_valid_own_club(self):
        self.assertEqual(self.client.get("/director/qr.png").status_code, 302)
        for user_id in ("user-admin", "user-staff4"):
            self.as_user(user_id)
            self.assertEqual(self.client.get("/director/qr.png").status_code, 403)
        db = persist.load()
        db["clubs"].append(data.Club("foreign-director-qr", "Ajeno", "org-foreign"))
        for club_id in (None, "missing-club", "foreign-director-qr"):
            calc.find(db, "users", "id", "user-dir1").club_id = club_id
            persist.save(db)
            self.as_user("user-dir1")
            self.assertEqual(self.client.get("/director/qr.png").status_code, 404)

    def test_qr_login_return_and_focus(self):
        db = persist.load()
        club = db["clubs"][0]
        path = "/qr/" + web._token_club(club)
        response = self.client.get(path)
        self.assertIn("next=", response.location)
        response = self.post("/login", {"username": "tomas", "password": "staff", "next": path})
        self.assertEqual(response.location, path)
        response = self.client.get(path, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Tigres del Valle', response.data)
        self.assertNotIn(b'id="club-club-2"', response.data)

    def test_login_rejects_external_next(self):
        response = self.post("/login", {"username": "tomas", "password": "staff", "next": "//evil.example"})
        self.assertEqual(response.location, "/staff")

    def test_staff_dashboard_sections_and_focused_evaluation(self):
        self.as_user("user-staff4")
        for vista in ["inicio", "clubes", "evaluar", "penalizaciones", "incidentes"]:
            response = self.client.get("/staff", query_string={"vista": vista})
            self.assertEqual(response.status_code, 200, vista)
            self.assertIn(b"staff.css", response.data)
            self.assertIn(b'aria-current="page"', response.data)
        home = self.client.get("/staff").data
        self.assertIn(b"Google Lens", home)
        self.assertNotIn(b'name="val_cr-7"', home)
        focus = self.client.get("/staff?club=club-1").data
        self.assertIn(b'name="val_cr-7"', focus)
        self.assertIn(b'data-score-output', focus)
        self.assertNotIn(b'id="club-club-2"', focus)
        self.assertEqual(self.client.get("/staff?vista=unknown").status_code, 404)

    def test_admin_dashboard_real_metrics_and_official_pending_count(self):
        self.as_user("user-admin")
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'admin.css', response.data)
        self.assertIn(b'Ranking de temporada', response.data)
        match = re.search(rb'data-metric="clock".*?<strong>(\d+)</strong>', response.data, re.S)
        self.assertEqual(int(match.group(1)), 3)
        db = persist.load()
        db["evaluaciones"].append(data.Evaluacion("backup-only", "ev-3", "club-1", "user-staff4", oficial=False))
        persist.save(db)
        response = self.client.get("/admin")
        match = re.search(rb'data-metric="clock".*?<strong>(\d+)</strong>', response.data, re.S)
        self.assertEqual(int(match.group(1)), 3)
        self.assertEqual(self.client.get("/admin?temporada=no-existe").status_code, 404)
        self.assertIn(b'id="crear-evento" open', self.client.get("/admin/eventos?nuevo=1").data)

    def test_admin_dashboard_empty_organization_and_search_isolation(self):
        self.post("/registro", {"nombre": "Admin propio", "username": "dashboard-propio", "password": "solo-testing-123", "organizacion": "Organizacion aislada"})
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Organizacion aislada', response.data)
        self.assertIn(b'admin-search-data', response.data)
        self.assertNotIn(b'Tigres del Valle', response.data)
        self.assertNotIn(b'Campamento Regional', response.data)
        self.assertIn('Todavía no hay evaluaciones oficiales'.encode(), response.data)

    def test_admin_dashboard_renders_real_ties(self):
        db = persist.load()
        for evaluation in db["evaluaciones"]:
            evaluation.valores = {key: 0 for key in evaluation.valores}
        db["penalizaciones"] = []
        persist.save(db)
        self.as_user("user-admin")
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'5 clubes en el puesto 1', response.data)
        self.assertIn(b'Hay posiciones compartidas', response.data)

    def test_projection_local_dashboard_scopes_and_ties(self):
        db = persist.load()
        db['evaluaciones'] = [e for e in db['evaluaciones'] if e.evento_id != 'ev-3']
        persist.save(db)
        self.as_user('user-admin')
        response = self.client.get('/admin/mostrar-resultado')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'projection.css', response.data)
        self.assertIn(b'admin-sidebar', response.data)
        self.assertNotIn(b'cdn.tailwindcss.com', response.data)
        response = self.client.get('/admin/mostrar-resultado?scope=evento')
        self.assertIn(b'Selecciona un evento', response.data)
        self.assertNotIn(b'class="projection-podium"', response.data)
        response = self.client.get('/admin/mostrar-resultado?scope=evento&evento_id=ev-3')
        self.assertIn('Todavía no hay resultados'.encode(), response.data)
        db = persist.load()
        for evaluation in db['evaluaciones']:
            evaluation.valores = {key: 0 for key in evaluation.valores}
        db['penalizaciones'] = []
        persist.save(db)
        response = self.client.get('/admin/mostrar-resultado')
        positions = re.findall(rb'class="projection-position">([^<]+)', response.data)
        self.assertEqual(positions, ['1°'.encode()] * 3)

    def test_projection_empty_tenant_and_roles(self):
        self.assertEqual(self.client.get('/admin/mostrar-resultado').status_code, 302)
        self.as_user('user-staff4')
        self.assertEqual(self.client.get('/admin/mostrar-resultado').status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.post('/registro', {'nombre': 'Admin aislado', 'username': 'projection-propio', 'password': 'solo-testing-123', 'organizacion': 'Proyeccion aislada'})
        response = self.client.get('/admin/mostrar-resultado')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Todavía no hay resultados'.encode(), response.data)
        self.assertNotIn(b'Tigres del Valle', response.data)

    def test_landing_is_public_local_and_illustrative(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'landing.css', response.data)
        self.assertIn(b'landing.js', response.data)
        self.assertIn(b'Google Lens', response.data)
        self.assertIn(b'Vista ilustrativa', response.data)
        self.assertIn(b'Desarrollado por Juan Fernando Nina Cachi.', response.data)
        self.assertIn(b'href="https://github.com/JuanFernandoNina" target="_blank" rel="noopener noreferrer"', response.data)
        self.assertIn(b'GitHub \xc2\xb7 @JuanFernandoNina', response.data)
        self.assertNotIn(b'cdn.tailwindcss.com', response.data)
        self.assertNotIn(b'newsletter', response.data)
        self.as_user("user-staff4")
        self.assertEqual(self.client.get("/").location, "/staff")

    def test_members_directory_is_admin_only_and_organization_scoped(self):
        self.assertEqual(self.client.get('/admin/miembros').status_code, 302)
        self.as_user('user-staff4')
        self.assertEqual(self.client.get('/admin/miembros').status_code, 403)
        self.as_user('user-admin')
        response = self.client.get('/admin/miembros')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Andrés Cáceres'.encode(), response.data)
        self.assertIn(b'admin-management.js', response.data)
        self.assertNotIn(b'cdn.tailwindcss.com', response.data)
        self.client.get('/logout')
        self.post('/registro', {'nombre':'Admin aislado','username':'miembros-aislado','password':'solo-testing-123','organizacion':'Otra organizacion'})
        response = self.client.get('/admin/miembros')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Andrés Cáceres'.encode(), response.data)
        self.assertIn(b'No hay miembros registrados', response.data)

    def test_auth_pages_local_style_and_errors_do_not_reflect_password(self):
        for path in ['/login', '/registro']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'landing.css', response.data)
            self.assertIn(b'auth.css', response.data)
            self.assertIn(b'auth.js', response.data)
            self.assertNotIn(b'cdn.tailwindcss.com', response.data)
        response = self.post('/login', {'username':'no-existe','password':'must-not-reflect-secret','next':'/qr/testing'})
        self.assertIn(b'value="no-existe"', response.data)
        self.assertIn(b'value="/qr/testing"', response.data)
        self.assertNotIn(b'must-not-reflect-secret', response.data)
        response = self.post('/registro', {'nombre':'Persona de prueba','organizacion':'Org prueba','username':'admin','password':'must-not-reflect-secret'})
        self.assertIn(b'value="Persona de prueba"', response.data)
        self.assertNotIn(b'must-not-reflect-secret', response.data)

    def test_role_dashboards_share_local_landing_theme(self):
        for user_id, path in [('user-admin','/admin'),('user-staff4','/staff'),('user-dir1','/director')]:
            self.as_user(user_id)
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'panel-theme.css', response.data)
            self.assertIn(b'mobile-panels.css', response.data)
            self.assertIn(b'panel-effects.js', response.data)
            self.assertIn(b'data-panel-theme', response.data)
            self.assertNotIn(b'cdn.tailwindcss.com', response.data)
        director = self.client.get('/director').data
        self.assertIn(b'Resultados por evento', director)
        self.assertNotIn(b'Campamento Regional', director)
        self.assertNotIn(b'<form method="post"', director)

    def test_staff_history_is_limited_to_current_user_and_event(self):
        self.as_user("user-staff4")
        self.assertEqual(self.post("/staff/incidente", {"tipo": "otro", "gravedad": "leve", "descripcion": "Mi incidente privado del evento"}).status_code, 302)
        self.assertEqual(self.post("/staff/penalizar", {"club_id": "club-1", "motivo_id": "mp-1", "comentario": "Mi penalizacion registrada"}).status_code, 302)
        self.assertIn(b"Mi incidente privado del evento", self.client.get("/staff?vista=incidentes").data)
        self.assertIn(b"Mi penalizacion registrada", self.client.get("/staff?vista=penalizaciones").data)
        self.add_second_staff()
        self.as_user("other-staff")
        self.assertNotIn(b"Mi incidente privado del evento", self.client.get("/staff?vista=incidentes").data)
        self.assertNotIn(b"Mi penalizacion registrada", self.client.get("/staff?vista=penalizaciones").data)
        self.as_user("user-staff1")
        for vista in ["incidentes", "penalizaciones"]:
            response = self.client.get("/staff?vista=" + vista)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(b'<form method="post"', response.data)

    def test_staff_dashboard_empty_event_and_missing_criteria(self):
        db = persist.load()
        db["evento_club"] = [ec for ec in db["evento_club"] if ec.evento_id != "ev-3"]
        db["criterios"] = [c for c in db["criterios"] if c.evento_id != "ev-3"]
        persist.save(db)
        self.as_user("user-staff4")
        for vista in ["inicio", "clubes", "evaluar", "penalizaciones", "incidentes"]:
            response = self.client.get("/staff?vista=" + vista)
            self.assertEqual(response.status_code, 200, vista)
            self.assertIn("criterios que sumen 100".encode(), response.data)

    def test_invalid_qr(self):
        self.assertEqual(self.client.get("/qr/invalid-signature").status_code, 404)

    def test_compact_qr_and_legacy_cards_remain_valid(self):
        from itsdangerous import URLSafeSerializer
        club = calc.find(persist.load(), "clubs", "id", "club-1")
        old = URLSafeSerializer(web.app.secret_key, salt="scoreup-club-qr-v1").dumps({"org": club.organizacion_id, "club": club.id})
        new = web._token_club(club)
        self.assertLess(len(new), len(old))
        self.assertEqual(new, web._token_club(club))
        self.as_user("user-staff4")
        for token in [old, new]:
            response = self.client.get("/qr/" + token, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="club-club-1"', response.data)
        wrong_org = URLSafeSerializer(web.app.secret_key, salt="scoreup-club-qr-v1").dumps({"org": "other", "club": club.id})
        self.assertEqual(self.client.get("/qr/" + wrong_org).status_code, 404)
        wrong_type = URLSafeSerializer(web.app.secret_key, salt="scoreup-club-qr-v2").dumps({"club": club.id})
        self.assertEqual(self.client.get("/qr/" + wrong_type).status_code, 404)

    def test_qr_png_and_print_card(self):
        self.as_user("user-admin")
        response = self.client.get("/admin/clubes/club-1/qr")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"192.168.1.10:5000/qr/", response.data)
        self.assertIn(b'class="admin-panel club-qr-card"', response.data)
        self.assertIn(b'club-qr.css', response.data)
        self.assertIn(b'aria-current="page"', response.data)
        self.assertNotIn(b'cdn.tailwindcss.com', response.data)
        response = self.client.get("/admin/clubes/club-1/qr?formato=png")
        self.assertEqual(response.mimetype, "image/png")
        image = Image.open(io.BytesIO(response.data))
        self.assertEqual(image.format, "PNG")

    def test_first_evaluation_persisted_and_second_staff_blocked(self):
        self.add_second_staff()
        self.as_user("user-staff4")
        self.assertEqual(self.post("/staff/evaluar/club-1", self.values()).status_code, 302)
        self.as_user("other-staff")
        self.assertEqual(self.post("/staff/evaluar/club-1", self.values(10)).status_code, 409)
        notes = [e for e in persist.load()["evaluaciones"] if e.evento_id == "ev-3" and e.club_id == "club-1" and e.oficial]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].valores["cr-7"], 80)

    def test_qr_uses_staff_event_not_event_from_another_account(self):
        club = calc.find(persist.load(), "clubs", "id", "club-1")
        path = "/qr/" + web._token_club(club)
        for uid in ["user-staff1", "user-staff4"]:
            self.as_user(uid)
            response = self.client.get(path, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # La vista enfocada corresponde siempre al evento asignado al usuario.
            event = calc.find(persist.load(), "eventos", "id", calc.find(persist.load(), "users", "id", uid).evento_id)
            self.assertIn(event.nombre.encode(), response.data)
            self.assertIn(b'id="club-club-1"', response.data)

    def test_scanner_permissions_and_local_assets(self):
        self.assertEqual(self.client.get("/staff/escanear").status_code, 302)
        self.as_user("user-admin")
        self.assertEqual(self.client.get("/staff/escanear").status_code, 403)
        self.as_user("user-staff4")
        response = self.client.get("/staff/escanear")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Campamento Regional", response.data)
        self.assertIn(b'data-panel-theme', response.data)
        self.assertIn(b'class="staff-sidebar"', response.data)
        self.assertNotIn(b'<label for="qr-camera">', response.data)
        self.assertIn(b'capture="environment" hidden', response.data)
        self.assertNotIn(b'cdn.tailwindcss.com', response.data)
        for control in ['preview', 'scan-canvas', 'scan-status', 'start-camera', 'start-live-camera', 'stop-camera', 'qr-photo', 'qr-camera']:
            self.assertEqual(response.data.count(f'id="{control}"'.encode()), 1)
        for path in ["/static/scanner.js", "/static/vendor/jsQR.js", "/static/scanner.css", "/static/staff.css", "/static/panel-theme.css", "/static/mobile-panels.css"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_qr_address_override_and_invalid_addresses(self):
        self.as_user("user-admin")
        path = "/admin/clubes/club-1/qr"
        response = self.client.get(path, query_string={"base_url": "http://192.168.50.2:5000/"})
        self.assertIn(b"http://192.168.50.2:5000/qr/", response.data)
        self.assertIn(b"base_url=http://192.168.50.2:5000", response.data)
        response = self.client.get(path, query_string={"base_url": "http://192.168.50.2:5000", "formato": "png"})
        self.assertEqual(response.mimetype, "image/png")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        for value in ["javascript:alert(1)", "http://user:pass@host", "http://host/path", "http://host?x=1", "http://host#x", "http://host:bad", "http://host\\evil", "http://bad host"]:
            self.assertEqual(self.client.get(path, query_string={"base_url": value}).status_code, 400, value)

    def test_qr_cannot_access_nonparticipant(self):
        db = persist.load()
        db["clubs"].append(data.Club("not-enrolled", "No inscrito", "org-1"))
        persist.save(db)
        self.as_user("user-staff4")
        self.assertEqual(self.client.get("/qr/" + web._token_club(db["clubs"][-1])).status_code, 404)

    def test_concurrent_evaluators_only_one_wins(self):
        self.add_second_staff()
        clients = [self.as_user(uid, web.app.test_client()) for uid in ["user-staff4", "other-staff"]]
        tokens = [self.token(client) for client in clients]
        def submit(index):
            return clients[index].post("/staff/evaluar/club-1", data=dict(self.values(70 + index), csrf_token=tokens[index])).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(submit, [0, 1]))
        self.assertEqual(sorted(codes), [302, 409])

    def test_correction_notifies_and_review_does_not_revert(self):
        self.as_user("user-staff4")
        self.post("/staff/evaluar/club-1", self.values())
        values = dict(self.values(90, 1), comentario="Corregido")
        self.assertEqual(self.post("/staff/evaluar/club-1", values).status_code, 302)
        db = persist.load()
        self.assertEqual(len(db["correcciones"]), 1)
        report = db["correcciones"][0]
        self.assertEqual(report["anterior"]["valores"]["cr-7"], 80)
        self.assertEqual(report["actual"]["valores"]["cr-7"], 90)
        self.as_user("user-admin")
        self.assertEqual(self.client.get("/admin/reportes?tipo=correcciones").status_code, 200)
        self.assertEqual(self.post(f"/admin/reportes/{report['id']}/estado", {"estado": "descartado"}).status_code, 302)
        db = persist.load()
        event = calc.find(db, "eventos", "id", "ev-3")
        self.assertEqual(calc.evaluacion_principal(db, event, "club-1").valores["cr-7"], 90)
        self.assertEqual(db["correcciones"][0]["estado"], "descartado")

    def test_stale_edit_and_duplicate_submit_blocked(self):
        self.as_user("user-staff4")
        self.post("/staff/evaluar/club-1", self.values())
        self.assertEqual(self.post("/staff/evaluar/club-1", self.values()).status_code, 409)
        self.post("/staff/evaluar/club-1", self.values(85, 1))
        self.assertEqual(self.post("/staff/evaluar/club-1", self.values(90, 1)).status_code, 409)

    def test_nonparticipant_and_invalid_values_rejected(self):
        self.as_user("user-staff4")
        self.assertEqual(self.post("/staff/evaluar/no-existe", self.values()).status_code, 404)
        for value in ["nan", "inf", "-1", "101", "texto"]:
            self.assertEqual(self.post("/staff/evaluar/club-1", self.values(value)).status_code, 400)

    def test_closed_event_is_immutable(self):
        self.as_user("user-admin")
        self.assertEqual(self.post("/admin/eventos/ev-1/criterio/cr-1/peso", {"peso": "10"}).status_code, 409)
        self.assertEqual(self.post("/admin/eventos/ev-1/desasignar/club-1").status_code, 409)
        self.assertEqual(self.post("/admin/penalizaciones/pa-2/anular").status_code, 409)
        self.as_user("user-staff1")
        self.assertEqual(self.post("/staff/evaluar/club-1", self.values()).status_code, 409)

    def test_close_requires_all_evaluations(self):
        self.as_user("user-admin")
        self.assertEqual(self.post("/admin/eventos/ev-3/cerrar").status_code, 409)
        self.as_user("user-staff4")
        for club in ["club-1", "club-3", "club-5"]:
            self.assertEqual(self.post("/staff/evaluar/" + club, self.values()).status_code, 302)
        self.as_user("user-admin")
        self.assertEqual(self.post("/admin/eventos/ev-3/cerrar").status_code, 302)
        self.assertTrue(calc.find(persist.load(), "eventos", "id", "ev-3").cerrado)

    def test_tenant_isolation(self):
        db = persist.load()
        db["organizaciones"].append({"id": "org-2", "nombre": "Otra", "fecha_creacion": "2026-01-01"})
        db["clubs"].append(data.Club("foreign", "Privado", "org-2"))
        db["motivos"].append(data.MotivoPenalizacion("foreign-m", "org-2", "Motivo privado", "", 5))
        persist.save(db)
        self.as_user("user-staff4")
        self.assertEqual(self.post("/staff/evaluar/foreign", self.values()).status_code, 404)
        self.assertEqual(self.post("/staff/penalizar", {"club_id": "club-1", "motivo_id": "foreign-m"}).status_code, 404)
        self.assertNotIn(b"Motivo privado", self.client.get("/staff").data)
        foreign = calc.find(db, "clubs", "id", "foreign")
        self.assertEqual(self.client.get("/qr/" + web._token_club(foreign)).status_code, 404)

    def test_penalties_season_and_historical_amount(self):
        db = persist.load()
        original = calc.ranking_temporada(db, "2026")
        db["eventos"].append(data.Evento("past", "org-1", "Pasado", "", "", "", "2025", 100))
        db["penalizaciones"].append(data.PenalizacionAplicada("past-p", "club-1", "past", "user-staff4", "mp-1", puntos=500))
        self.assertEqual(original, calc.ranking_temporada(db, "2026"))
        db["motivos"][0].puntos_descuento = 1000
        self.assertEqual(original, calc.ranking_temporada(db, "2026"))

    def test_database_unique_constraint(self):
        db = persist.load()
        db["evaluaciones"].append(data.Evaluacion("duplicate", "ev-1", "club-1", "user-staff2"))
        with self.assertRaises(sqlite3.IntegrityError):
            persist.save(db)
        self.assertEqual(len(persist.load()["evaluaciones"]), 13)

    def test_routes_exports_and_all_post_forms_have_csrf(self):
        from html.parser import HTMLParser
        class Forms(HTMLParser):
            def __init__(self):
                super().__init__()
                self.current = None
                self.forms = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "form":
                    self.current = {"post": attrs.get("method", "get").lower() == "post", "csrf": False}
                if tag == "input" and self.current is not None and attrs.get("name") == "csrf_token":
                    self.current["csrf"] = True
            def handle_endtag(self, tag):
                if tag == "form" and self.current is not None:
                    self.forms.append(self.current)
                    self.current = None
        self.as_user("user-admin")
        paths = ["/admin", "/admin/clubes", "/admin/clubes/club-1/miembros", "/admin/eventos", "/admin/eventos/ev-3", "/admin/usuarios", "/admin/incidentes", "/admin/penalizaciones", "/admin/penalizaciones/motivos", "/admin/resultados", "/admin/reportes?tipo=staff", "/admin/reportes?tipo=penalizaciones", "/registro", "/login"]
        for path in paths:
            response = self.client.get(path)
            self.assertIn(response.status_code, [200, 302], path)
            parser = Forms()
            parser.feed(response.data.decode())
            self.assertTrue(all(not f["post"] or f["csrf"] for f in parser.forms), path)
        for fmt, mime in [("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), ("pdf", "application/pdf")]:
            response = self.client.get("/admin/exportar?formato=" + fmt)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, mime)

    def test_qreader_permissions_csrf_and_missing_image(self):
        route = "/staff/escanear/imagen"
        self.assertEqual(self.post(route).status_code, 302)
        self.as_user("user-admin")
        self.assertEqual(self.post(route).status_code, 403)
        self.as_user("user-staff4")
        self.assertEqual(self.client.post(route).status_code, 400)
        self.assertEqual(self.post(route).status_code, 400)

    def test_qreader_opens_only_signed_participating_club_without_writes(self):
        self.as_user("user-staff4")
        club = calc.find(persist.load(), "clubs", "id", "club-1")
        path = "/qr/" + web._token_club(club)
        before = Path(persist.DB_PATH).read_bytes()
        with patch("qr_reader.decode_image", return_value=("http://old-ip.invalid:5000" + path,)):
            response = self.post("/staff/escanear/imagen", {"imagen": (io.BytesIO(b"mocked-image"), "qr.jpg")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"path": path, "reader": "qreader"})
        self.assertEqual(Path(persist.DB_PATH).read_bytes(), before)
        self.assertEqual(self.client.get(path).status_code, 302)

    def test_qreader_rejects_foreign_tampered_and_non_scoreup_codes(self):
        db = persist.load()
        foreign = data.Club("foreign-qr", "Privado", "other-org")
        db["clubs"].append(foreign)
        persist.save(db)
        self.as_user("user-staff4")
        for value in ["https://example.com", "/qr/invalid", "/qr/" + web._token_club(foreign), "javascript:alert(1)"]:
            with patch("qr_reader.decode_image", return_value=(value,)):
                response = self.post("/staff/escanear/imagen", {"imagen": (io.BytesIO(b"mocked"), "qr.jpg")})
            self.assertEqual(response.status_code, 422, value)
            self.assertNotIn("path", response.json)

    def test_qreader_multiple_cards_and_legacy_signature(self):
        from itsdangerous import URLSafeSerializer
        self.as_user("user-staff4")
        clubs = persist.load()["clubs"][:2]
        paths = ["/qr/" + web._token_club(club) for club in clubs]
        with patch("qr_reader.decode_image", return_value=paths):
            response = self.post("/staff/escanear/imagen", {"imagen": (io.BytesIO(b"mocked"), "qr.jpg")})
            self.assertEqual(response.status_code, 422)
        legacy = URLSafeSerializer(web.app.secret_key, salt="scoreup-club-qr-v1").dumps({"org": "org-1", "club": clubs[0].id})
        with patch("qr_reader.decode_image", return_value=("/qr/" + legacy,)):
            response = self.post("/staff/escanear/imagen", {"imagen": (io.BytesIO(b"mocked"), "qr.jpg")})
            self.assertEqual(response.status_code, 200)

    def test_qreader_invalid_image_and_unavailable_service(self):
        from qr_reader import QRReaderUnavailable, QRReaderBusy
        self.as_user("user-staff4")
        self.assertEqual(self.post("/staff/escanear/imagen", {"imagen": (io.BytesIO(b"not-image"), "qr.jpg")}).status_code, 400)
        for error in [QRReaderUnavailable("private-details"), QRReaderBusy("Lector ocupado")]:
            with patch("qr_reader.decode_image", side_effect=error):
                response = self.post("/staff/escanear/imagen", {"imagen": (io.BytesIO(b"mocked"), "qr.jpg")})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b"private-details", response.data)

    def test_projection_clean_screen_preserves_positions_without_admin_controls(self):
        self.as_user("user-admin")
        response = self.client.get("/admin/mostrar-resultado?pantalla=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"scoreboard.css", response.data)
        for forbidden in [b"admin-sidebar", b"<form", b"<button", b"<select", b"cdn."]:
            self.assertNotIn(forbidden, response.data)
        ranking = calc.ranking_temporada(persist.load(), "2026")["filas"]
        self.assertEqual(response.data.count(b'<article class="scoreboard-row'), len(ranking))
        self.assertIn(b'class="scoreboard-podium"', response.data)
        self.assertIn(b'class="scoreboard-rest"', response.data)
        podio, resto = response.data.split(b'<section class="scoreboard-rest"', 1)
        self.assertEqual(podio.count(b'<article class="scoreboard-row is-top"'), 3)
        anteriores = [blob.index(row["club"].nombre.encode()) for blob, row in
                      ((podio, row) for row in ranking[:3])]
        self.assertEqual(anteriores, sorted(anteriores))
        self.assertNotIn(ranking[0]["club"].nombre.encode(), resto)
        posteriores = [resto.index(row["club"].nombre.encode()) for row in ranking[3:]]
        self.assertEqual(posteriores, sorted(posteriores))
        self.as_user("user-staff4")
        self.assertEqual(self.client.get("/admin/mostrar-resultado?pantalla=1").status_code, 403)

    def test_projection_clean_screen_event_and_missing_selection(self):
        self.as_user("user-admin")
        response = self.client.get("/admin/mostrar-resultado?pantalla=1&scope=evento")
        self.assertIn(b"Selecciona un evento", response.data)
        self.assertNotIn(b"scoreboard-row ", response.data)
        response = self.client.get("/admin/mostrar-resultado?pantalla=1&scope=evento&evento_id=ev-1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'<article class="scoreboard-row'), 5)

    def test_valid_and_invalid_evidence(self):
        self.as_user("user-staff4")
        fields = {"club_id": "club-1", "tipo": "disciplina", "gravedad": "leve", "descripcion": "Prueba"}
        bad = dict(fields, foto=(io.BytesIO(b"not an image"), "foto.png"))
        self.assertEqual(self.post("/staff/incidente", bad).status_code, 400)
        image = io.BytesIO()
        Image.new("RGB", (10, 10)).save(image, format="PNG")
        image.seek(0)
        # Las fotos de prueba quedan en la carpeta temporal, no en uploads reales.
        old_root = web.app.root_path
        web.app.root_path = self.directory.name
        try:
            self.assertEqual(self.post("/staff/incidente", dict(fields, foto=(image, "foto.png"))).status_code, 302)
            incident = persist.load()["incidentes"][-1]
            response = self.client.get(incident.foto_url)
            self.assertEqual(response.status_code, 200)
            response.close()
            self.as_user("user-dir1")
            self.assertEqual(self.client.get(incident.foto_url).status_code, 403)
        finally:
            web.app.root_path = old_root


class MigrationTests(unittest.TestCase):
    def test_legacy_migration_preserves_official_and_backups(self):
        with tempfile.TemporaryDirectory(prefix="scoreup-migration-") as directory:
            previous = persist.DB_PATH
            persist.DB_PATH = str(Path(directory) / "legacy.db")
            try:
                with closing(sqlite3.connect(persist.DB_PATH)) as conn:
                    conn.executescript(persist.SCHEMA)
                    conn.execute("INSERT INTO organizaciones VALUES ('org-1','Prueba','2026-01-01')")
                    conn.execute("INSERT INTO evento_club VALUES ('ec','ev','club','principal')")
                    for id, staff in [("original", "principal"), ("backup", "otro")]:
                        conn.execute("INSERT INTO evaluaciones VALUES (?,?,?,?,?,?,?)", (id, "ev", "club", staff, "", "", '{}'))
                    conn.commit()
                db = persist.load()
                self.assertEqual(len(db["evaluaciones"]), 2)
                self.assertEqual([e.id for e in db["evaluaciones"] if e.oficial], ["original"])
                self.assertEqual(len(list(Path(directory).glob("legacy.db.backup-*"))), 1)
                persist.load()
                self.assertEqual(len(list(Path(directory).glob("legacy.db.backup-*"))), 1)
            finally:
                persist.DB_PATH = previous


if __name__ == "__main__":
    unittest.main()
