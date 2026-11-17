"""Prueba HTTP y persistencia en contenedor/volumen temporales, sin datos reales.

Ejecutar después de docker compose build: python tests/manual_docker.py
Solo elimina el contenedor y volumen exclusivos creados por esta prueba.
"""

import http.cookiejar
import json
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, encoding="utf-8").strip()


def main():
    name = "scoreup-test-" + uuid.uuid4().hex[:12]
    volume = name + "-data"
    password = secrets.token_urlsafe(24)
    docker("volume", "create", volume)

    def start():
        docker("run", "-d", "--name", name, "--read-only", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges:true", "--tmpfs", "/tmp:mode=1777",
               "--mount", f"type=volume,source={volume},target=/data",
               "-p", "127.0.0.1::5000", "scoreup:local")
        details = json.loads(docker("inspect", name))[0]
        port = details["NetworkSettings"]["Ports"]["5000/tcp"][0]["HostPort"]
        base = "http://127.0.0.1:" + port
        for _ in range(60):
            try:
                with urllib.request.urlopen(base + "/login", timeout=2) as response:
                    if response.status == 200:
                        return base
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(0.5)
        raise RuntimeError("El contenedor de prueba no respondió.")

    try:
        base = start()
        jar = http.cookiejar.CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        def get(path):
            with client.open(base + path, timeout=20) as response:
                return response.read()

        def post(path, fields):
            html = get("/login")
            token = re.search(rb'name="csrf_token" value="([^"]+)"', html).group(1).decode()
            body = urllib.parse.urlencode(dict(fields, csrf_token=token)).encode()
            with client.open(base + path, data=body, timeout=20) as response:
                return response.read()

        html = post("/registro", {"nombre": "Prueba Docker", "username": "docker.test",
                                  "password": password, "organizacion": "Organización temporal"})
        assert b"Organizaci" in html
        post("/admin/clubes", {"nombre": "Club temporal Docker"})
        html = get("/admin/clubes")
        club = re.search(rb'/admin/clubes/([^/"?]+)/qr', html).group(1).decode()
        qr_page = get(f"/admin/clubes/{club}/qr")
        token = re.search(rb'/qr/([^"<\s]+)', qr_page).group(1).decode()
        png = get(f"/admin/clubes/{club}/qr?formato=png")
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        post("/admin/eventos", {"nombre": "Evento temporal Docker", "temporada": "2026", "puntaje_maximo": "100"})
        event_id = re.search(rb'/admin/eventos/([^/"?]+)"', get("/admin/eventos")).group(1).decode()
        post(f"/admin/eventos/{event_id}/asignar", {"club_id": club})
        post("/admin/usuarios/nuevo", {"nombre": "Staff temporal", "username": "docker.staff",
                                       "password": password, "rol": "staff", "evento_id": event_id})
        screen = get("/admin/mostrar-resultado?pantalla=1")
        assert b'class="scoreboard"' in screen and b"admin-sidebar" not in screen

        # La lectura/escritura de esta evidencia es solo en el volumen temporal.
        docker("exec", name, "python", "-c",
               "from pathlib import Path; Path('/data/uploads/persistencia.txt').write_text('prueba-aislada')")
        state_code = (
            "import sqlite3,json,hashlib; from pathlib import Path; "
            "c=sqlite3.connect('/data/scoreup.db'); "
            "print(json.dumps({'users':c.execute('SELECT COUNT(*) FROM users').fetchone()[0],"
            "'clubs':c.execute('SELECT COUNT(*) FROM clubs').fetchone()[0],"
            "'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],"
            "'key':hashlib.sha256(Path('/data/.secret_key').read_bytes()).hexdigest(),"
            "'upload':Path('/data/uploads/persistencia.txt').read_text()})); c.close()"
        )
        before = docker("exec", name, "python", "-c", state_code)
        state = json.loads(before)
        assert state["users"] == 2 and state["clubs"] == 1 and state["integrity"] == "ok"
        docker("rm", "-f", name)
        base = start()
        after = docker("exec", name, "python", "-c", state_code)
        assert before == after, "Cambió el estado tras recrear el contenedor"
        # La cookie previa también sigue siendo válida con la misma clave.
        assert b"Club temporal Docker" in get("/admin/clubes")
        assert token.encode() in get(f"/admin/clubes/{club}/qr")
        get("/logout")
        html = post("/login", {"username": "docker.test", "password": password})
        assert b"Organizaci" in html
        try:
            get("/qr/" + token)
        except urllib.error.HTTPError as error:
            # Firma válida, pero Admin no tiene rol Staff para evaluar.
            assert error.code == 403
        else:
            raise AssertionError("Un Admin no debe evaluar mediante el QR de Staff")
        get("/logout")
        post("/login", {"username": "docker.staff", "password": password})
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', get("/login")).group(1)
        boundary = "scoreup-test-" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"csrf_token\"\r\n\r\n".encode()
            + csrf + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"imagen\"; filename=\"qr.png\"\r\nContent-Type: image/png\r\n\r\n".encode()
            + png + f"\r\n--{boundary}--\r\n".encode()
        )
        upload = urllib.request.Request(base + "/staff/escanear/imagen", data=body,
                                        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        with client.open(upload, timeout=60) as response:
            decoded = json.loads(response.read())
        assert decoded == {"reader": "qreader", "path": "/qr/" + token}
        assert b"Club temporal Docker" in get(decoded["path"])
        print("OK: registro, login, club, QR/PNG, proyección limpia y QReader real por HTTP; base, sesión, firma y evidencia persistentes tras recrear; permisos conservados.")
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "volume", "rm", volume], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
