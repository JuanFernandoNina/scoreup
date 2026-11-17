"""Proyección: Edge, datos temporales y recursos locales, sin tocar scoreup.db."""
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
    with tempfile.TemporaryDirectory(prefix='scoreup-projection-') as directory:
        os.environ['SCOREUP_DB'] = str(Path(directory) / 'test.db')
        os.environ['SECRET_KEY'] = 'projection-test-only'
        import app as web
        import persist
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server

        db = persist.load()
        db['evaluaciones'] = [e for e in db['evaluaciones'] if e.evento_id != 'ev-3']
        persist.save(db)
        server = make_server('127.0.0.1', 0, web.app, threaded=True)
        base = f'http://127.0.0.1:{server.server_port}'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                context = browser.new_context(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
                external, errors = [], []
                def local_only(route):
                    if route.request.url.startswith(base):
                        route.continue_()
                    else:
                        external.append(route.request.url)
                        route.abort()
                context.route('**/*', local_only)
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/login')
                page.locator('[name=username]').fill('admin')
                page.locator('[name=password]').fill('admin')
                page.locator('button[type=submit]').click()
                page.wait_for_url('**/admin')
                for width in [1440,390,320]:
                    page.set_viewport_size({'width':width,'height':1000})
                    response = page.goto(base + '/admin/mostrar-resultado')
                    assert response.status == 200
                    assert page.locator('.projection-podium article').count() == 3
                    assert page.locator('.projection-list li').count() > 3
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                    assert page.locator('.admin-nav-link.is-active span').inner_text() == 'Resultados'
                    if output:
                        page.screenshot(path=str(output / f'projection-{width}.png'), full_page=True)
                page.locator('#projection-scope').select_option('evento')
                page.locator('#projection-event').select_option('ev-1')
                page.get_by_role('button', name='Mostrar ranking').click()
                assert 'Resultados del evento' in page.locator('h2#projection-title').inner_text()
                assert page.locator('.projection-list li').count() > 0
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.locator('#projection-event').select_option('ev-3')
                page.get_by_role('button', name='Mostrar ranking').click()
                assert page.locator('.projection-empty').is_visible()
                assert page.locator('.projection-podium').count() == 0
                page.goto(base + '/admin/mostrar-resultado?scope=evento')
                assert page.locator('.projection-empty h3').inner_text() == 'Selecciona un evento'
                plain = browser.new_context(storage_state=context.storage_state(), java_script_enabled=False, viewport={'width':390,'height':844})
                plain.route('**/*', local_only)
                nojs = plain.new_page()
                nojs.goto(base + '/admin/mostrar-resultado')
                assert nojs.locator('.projection-podium').is_visible()
                nojs.locator('#projection-scope').select_option('evento')
                nojs.locator('#projection-event').select_option('ev-1')
                nojs.get_by_role('button', name='Mostrar ranking').click()
                assert nojs.locator('#projection-title').inner_text() == 'Resultados del evento'
                assert not errors, errors
                assert not external, external
                browser.close()
                print('OK: proyección Edge 1440/390/320px, podio, ranking completo, filtros, evento vacío, sin selección y sin JavaScript; recursos locales y sin errores JS.')
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
