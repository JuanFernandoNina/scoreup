"""Prueba local de reconocimiento: PNG aportado y fotos sintéticas, no fotos reales.

Uso: .venv/Scripts/python.exe tests/manual_photo_qr.py ruta/al/qr.png
Usa SQLite temporal y captura la navegación antes de validar la firma del QR.
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    source = Path(sys.argv[1]).resolve()
    from PIL import Image, ImageFilter, ImageEnhance
    with tempfile.TemporaryDirectory(prefix="scoreup-photo-test-") as directory:
        os.environ["SCOREUP_DB"] = str(Path(directory) / "test.db")
        os.environ["SECRET_KEY"] = "photo-test-only"
        import app as web
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server

        server = make_server("127.0.0.1", 0, web.app, threaded=True)
        base = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            original = Image.open(source).convert("RGB")
            fixtures = {"original": original}
            fixtures["contraste-bajo"] = ImageEnhance.Contrast(original).enhance(0.3)
            fixtures["giro-y-desenfoque-leve"] = original.rotate(17, resample=Image.Resampling.BICUBIC, expand=True, fillcolor="white").filter(ImageFilter.GaussianBlur(0.5))
            for name, xy in [("foto-grande-qr-pequeno-centro", (1800, 1300)), ("foto-grande-qr-esquina", (300, 300))]:
                photo = Image.new("RGB", (4000, 3000), (190, 185, 180))
                photo.paste(original.resize((360, 360), Image.Resampling.LANCZOS), xy)
                fixtures[name] = photo
            # Simular perspectiva moderada mediante una transformación afín.
            fixtures["inclinacion-moderada"] = original.transform(
                (original.width + 200, original.height), Image.Transform.AFFINE,
                (1, -0.22, 0, 0, 1, 0), resample=Image.Resampling.BICUBIC, fillcolor="white")
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(viewport={"width": 390, "height": 844})
                context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                decoded = []
                def capture(route):
                    decoded.append(route.request.url.split("/qr/", 1)[1])
                    route.fulfill(status=200, content_type="text/html", body="QR reconocido")
                context.route("**/qr/*", capture)
                page = context.new_page()
                page.goto(base + "/login")
                page.locator('[name="username"]').fill("tomas")
                page.locator('[name="password"]').fill("staff")
                page.locator('button[type="submit"]').click()
                page.wait_for_url("**/staff")
                for name, image in fixtures.items():
                    path = Path(directory) / (name + ".jpg")
                    image.save(path, quality=90)
                    page.goto(base + "/staff/escanear")
                    # Forzar fallback jsQR para que no dependa de BarcodeDetector.
                    page.evaluate("() => { delete window.BarcodeDetector; }")
                    page.locator('#qr-camera').set_input_files(path)
                    try:
                        page.wait_for_url("**/qr/*", timeout=60000)
                    except Exception:
                        print("FALLO:", name, page.locator('#scan-status').inner_text())
                        raise
                    assert decoded[-1] == decoded[0], "El contenido decodificado debe ser idéntico"
                    print("OK:", name)
                browser.close()
                print("Todas las variantes sintéticas reconocidas; esto no sustituye la foto real del teléfono.")
        finally:
            server.shutdown()
            thread.join()


if __name__ == "__main__":
    main()
