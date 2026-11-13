"""Verificación opcional en Edge: SQLite y QR temporales, sin tocar datos locales.

Ejecutar: .venv/Scripts/python.exe tests/manual_browser_qr.py
Requiere playwright instalado en el entorno de desarrollo.
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix="scoreup-browser-") as directory:
        os.environ["SCOREUP_DB"] = str(Path(directory) / "test.db")
        os.environ["SECRET_KEY"] = "browser-test-only"
        import app as web
        import persist
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server

        server = make_server("127.0.0.1", 0, web.app, threaded=True)
        base = f"http://127.0.0.1:{server.server_port}"
        web.app.config["PUBLIC_BASE_URL"] = base
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
                # Sin servicios externos: el decodificador se sirve desde la propia app.
                context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def login(username, password):
                    page.goto(base + "/login")
                    page.locator('[name="username"]').fill(username)
                    page.locator('[name="password"]').fill(password)
                    page.locator('button[type="submit"]').click()
                    page.wait_for_url(lambda url: "/login" not in url)

                login("admin", "admin")
                page.goto(base + "/admin/clubes/club-1/qr")
                with page.expect_download() as pending:
                    page.get_by_role("link", name="Descargar PNG").click()
                qr_file = Path(directory) / "club.png"
                pending.value.save_as(qr_file)
                page.goto(base + "/logout")
                login("tomas", "staff")
                page.get_by_role("link", name="Escanear QR de un club").click()
                page.wait_for_load_state("load")
                assert page.locator('#qr-photo').get_attribute('capture') is None
                assert page.locator('#qr-camera').get_attribute('capture') == 'environment'
                page.locator("#qr-photo").set_input_files(qr_file)
                try:
                    page.wait_for_url("**/staff?club=club-1", timeout=10000)
                except Exception:
                    print("Scanner:", page.locator('#scan-status').inner_text(), "JS errors:", errors)
                    raise
                assert page.locator('h2').first.inner_text() == "Tigres del Valle"
                assert page.locator('section[id^="club-"]').count() == 1
                for field in page.locator('input[name^="val_"]').all():
                    field.fill("88")
                page.get_by_role("button", name="Guardar evaluación oficial", exact=True).click()
                page.get_by_role("status").filter(has_text="Evaluación guardada correctamente").wait_for()
                db = persist.load()
                evaluation = next(e for e in db["evaluaciones"] if e.club_id == "club-1" and e.evento_id == "ev-3")
                assert set(evaluation.valores.values()) == {88.0}
                page.reload()
                assert page.locator('input[name^="val_"]').first.input_value() == "88.0"

                # Imagen sin QR: mensaje legible y sin navegar.
                from PIL import Image
                blank = Path(directory) / "blank.png"
                Image.new("RGB", (200, 200), "white").save(blank)
                page.goto(base + "/staff/escanear")
                page.locator("#qr-photo").set_input_files(blank)
                page.get_by_role("status").filter(has_text="No se encontró un QR").wait_for()
                # QR ajeno: no navegar a una web externa.
                import qrcode
                alien = Path(directory) / "alien.png"
                qrcode.make("https://example.com/unsafe").save(alien)
                page.locator("#qr-photo").set_input_files(alien)
                page.get_by_role("status").filter(has_text="no es un QR de club").wait_for()

                # Un enlace de tarjeta con IP antigua se resuelve en la instalación actual.
                club = next(c for c in db["clubs"] if c.id == "club-1")
                old = Path(directory) / "old-address.png"
                qrcode.make("http://192.168.99.99:5000/qr/" + web._token_club(club)).save(old)
                page.locator("#qr-photo").set_input_files(old)
                page.wait_for_url("**/staff?club=club-1")

                # Cámara real denegada: debe ofrecer la alternativa de foto.
                page.goto(base + "/staff/escanear")
                page.evaluate("() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('denied', 'NotAllowedError'); }; }")
                page.get_by_role("button", name="Activar cámara").click()
                page.get_by_role("status").filter(has_text="No se pudo abrir la cámara").wait_for()
                assert page.get_by_role("button", name="Activar cámara").is_enabled()
                # Flujo de vídeo con una cámara simulada que muestra el QR descargado.
                import base64
                image_url = "data:image/png;base64," + base64.b64encode(qr_file.read_bytes()).decode()
                page.evaluate("""async source => {
                    const image = new Image(); image.src = source; await image.decode();
                    const canvas = document.createElement('canvas');
                    canvas.width = image.width; canvas.height = image.height;
                    canvas.getContext('2d').drawImage(image, 0, 0);
                    window.testCamera = canvas.captureStream(10);
                    navigator.mediaDevices.getUserMedia = async () => window.testCamera;
                }""", image_url)
                page.get_by_role("button", name="Activar cámara").click()
                page.wait_for_url("**/staff?club=club-1")
                assert not errors, errors
                browser.close()
                print("OK: Edge móvil, descarga PNG, lectura local sin internet, evaluación persistida, imágenes inválidas, IP antigua, cámara denegada y vídeo con cámara simulada.")
        finally:
            server.shutdown()
            thread.join()


if __name__ == "__main__":
    main()
