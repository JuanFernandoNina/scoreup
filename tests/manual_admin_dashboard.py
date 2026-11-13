"""Verificación visual del admin en Edge; base temporal, sin tocar datos reales."""
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
    with tempfile.TemporaryDirectory(prefix="scoreup-admin-ui-") as directory:
        os.environ["SCOREUP_DB"] = str(Path(directory) / "test.db")
        os.environ["SECRET_KEY"] = "admin-ui-test-only"
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
                for label, width, height in [("wide", 1920, 1080), ("desktop", 1440, 1000), ("mobile", 390, 844), ("small", 320, 740)]:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base + "/login")
                    page.locator('[name="username"]').fill("admin")
                    page.locator('[name="password"]').fill("admin")
                    page.locator('button[type="submit"]').click()
                    page.wait_for_url("**/admin")
                    page.wait_for_load_state('load')
                    assert page.locator('.admin-metric').count() == 5
                    assert page.locator('[data-metric="clock"] strong').inner_text() == '3'
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), label
                    if output:
                        page.screenshot(path=str(output / (label + '-inicio.png')), full_page=True)
                    if width < 760:
                        assert not page.locator('#admin-sidebar').is_visible()
                        page.get_by_role('button', name='Abrir menú').click()
                        assert page.locator('#admin-sidebar').is_visible()
                        page.keyboard.press('Escape')
                        assert not page.locator('#admin-sidebar').is_visible()
                    page.keyboard.press('Control+k')
                    assert page.locator('#admin-search-input').evaluate('el => el === document.activeElement')
                    page.locator('#admin-search-input').fill('aguilas')
                    assert page.locator('#admin-search-results a').count() == 1
                    page.locator('#admin-search-input').fill('no-existe')
                    assert 'No hay clubes' in page.locator('#admin-search-results').inner_text()
                    page.locator('#admin-search-input').fill('Campamento Regional')
                    page.keyboard.press('Enter')
                    page.wait_for_url('**/admin/eventos/ev-3')
                    page.goto(base + '/admin')
                    page.get_by_role('link', name='Crear evento', exact=True).click()
                    page.wait_for_url('**/admin/eventos?nuevo=1')
                    assert page.locator('#crear-evento').get_attribute('open') is not None
                    page.goto(base + '/admin')
                    page.locator('#admin-season').select_option('2026')
                    page.locator('.admin-season button').click()
                    page.wait_for_url('**/admin?temporada=2026')
                    assert not errors, errors
                    context.close()
                    print('OK:', label, 'indicadores, ancho, menu, busqueda, atajo, crear evento y temporada')
                browser.close()
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
