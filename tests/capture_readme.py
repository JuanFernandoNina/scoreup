"""Capturas públicas del README con datos ficticios y SQLite temporal.

Ejecutar desde la raíz: .venv/Scripts/python.exe tests/capture_readme.py
Requiere las dependencias de desarrollo y Microsoft Edge.
Nunca utiliza scoreup.db ni sesiones de usuarios de la instalación local.
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    images = ROOT / 'image'
    images.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='scoreup-readme-') as directory:
        os.environ['SCOREUP_DB'] = str(Path(directory) / 'demo.db')
        os.environ['SECRET_KEY'] = 'public-screenshot-fixture-only'
        import app as web
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server

        server = make_server('127.0.0.1', 0, web.app, threaded=True)
        base = f'http://127.0.0.1:{server.server_port}'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                errors = []
                def new_context(**kwargs):
                    context = browser.new_context(viewport={'width':1440,'height':1000}, **kwargs)
                    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                    return context

                def reveal_all(page, selector):
                    page.evaluate("document.documentElement.style.scrollBehavior='auto'")
                    for card in page.locator(selector).all():
                        card.scroll_into_view_if_needed()
                    # Esperar al observer sin deshabilitar los efectos de la app.
                    page.wait_for_function("selector => [...document.querySelectorAll(selector)].every(el => el.classList.contains('panel-visible') || el.classList.contains('is-visible'))", arg=selector)
                    page.evaluate('scrollTo(0,0)')
                    page.wait_for_function('scrollY===0')

                context = new_context()
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base)
                page.wait_for_load_state('load')
                assert page.locator('h1').inner_text().startswith('Grandes eventos.')
                page.screenshot(path=str(images/'landing-page.png'), animations='disabled')
                context.close()

                for role, username, password, path in [
                    ('admin','admin','admin','/admin'),
                    ('staff','tomas','staff','/staff'),
                    ('director','lucia','director','/director'),
                ]:
                    context = new_context()
                    page = context.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(base+'/login')
                    page.locator('[name=username]').fill(username)
                    page.locator('[name=password]').fill(password)
                    page.locator('button[type=submit]').click()
                    page.wait_for_url('**'+path)
                    page.wait_for_load_state('load')
                    assert not page.locator('[name=password]').count()
                    reveal_all(page, '.panel-reveal')
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                    page.screenshot(path=str(images/f'dashboard-{role}.png'), full_page=True, animations='disabled')
                    context.close()
                assert not errors, errors
                browser.close()
                print('OK: cuatro capturas nuevas con datos ficticios en image/. Sin modificar la base local.')
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
