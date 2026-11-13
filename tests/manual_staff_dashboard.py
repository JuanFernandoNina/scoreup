"""Prueba del panel en Edge con SQLite temporal; captura opcional por argumento."""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scoreup-staff-ui-") as directory:
        os.environ["SCOREUP_DB"] = str(Path(directory) / "test.db")
        os.environ["SECRET_KEY"] = "staff-ui-test-only"
        import app as web
        from werkzeug.serving import make_server
        from playwright.sync_api import sync_playwright

        server = make_server("127.0.0.1", 0, web.app, threaded=True)
        base = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="msedge", headless=True)
                for label, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844), ("small", 320, 740)]:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base + "/login")
                    page.locator('[name="username"]').fill("tomas")
                    page.locator('[name="password"]').fill("staff")
                    page.locator('button[type="submit"]').click()
                    page.wait_for_url("**/staff")
                    page.wait_for_load_state("load")
                    assert page.locator('.staff-action').count() == 4
                    if output:
                        page.screenshot(path=str(output / (label + "-inicio.png")), full_page=True)
                    for vista in ["inicio", "clubes", "penalizaciones", "incidentes", "evaluar"]:
                        page.goto(base + "/staff?vista=" + vista)
                        assert page.locator('[aria-current="page"]').count() == 1
                        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), (label, vista)
                    page.goto(base + "/staff?vista=clubes")
                    page.locator('#staff-search').fill("aguilas")
                    assert page.locator('.staff-club-row:visible').count() == 1
                    page.locator('#staff-search').fill("no-existe-este-club")
                    assert page.locator('#staff-search-empty').is_visible()
                    page.goto(base + "/staff?club=club-1")
                    for field in page.locator('[data-weight]').all():
                        field.fill("50")
                    assert page.locator('[data-score-output]').inner_text() == "160 pts"
                    slider = page.locator('[data-number]').first
                    slider.evaluate("el => { el.value = 100; el.dispatchEvent(new Event('input', {bubbles:true})); }")
                    assert page.locator('[data-weight]').first.input_value() == "100"
                    assert page.locator('[data-score-output]').inner_text() == "200 pts"
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), (label, "foco")
                    if output:
                        page.screenshot(path=str(output / (label + "-evaluar.png")), full_page=True)
                    page.goto(base + "/staff?vista=incidentes")
                    page.locator('[name="descripcion"]').fill("Prueba visual del panel " + label)
                    page.get_by_role('button', name='Reportar incidente', exact=True).click()
                    page.get_by_role('status').filter(has_text='Incidente reportado correctamente').wait_for()
                    assert page.locator('.staff-history').filter(has_text="Prueba visual del panel " + label).count() == 1
                    page.goto(base + "/staff?vista=penalizaciones")
                    page.locator('[name="comentario"]').fill("Prueba visual de penalizacion " + label)
                    page.get_by_role('button', name='Aplicar penalización', exact=True).click()
                    page.get_by_role('status').filter(has_text='Penalización aplicada correctamente').wait_for()
                    assert page.locator('.staff-history').filter(has_text="Prueba visual de penalizacion " + label).count() == 1
                    assert not errors, errors
                    context.close()
                    print("OK:", label, "navegacion, filtros, puntaje, formularios, historiales y ancho de pantalla")
                browser.close()
        finally:
            server.shutdown()
            thread.join()


if __name__ == "__main__":
    main()
