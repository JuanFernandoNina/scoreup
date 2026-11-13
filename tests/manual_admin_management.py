"""Gestión admin: vistas, tablas y CRUD en Edge, con SQLite temporal."""
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
    with tempfile.TemporaryDirectory(prefix='scoreup-management-ui-') as directory:
        os.environ['SCOREUP_DB'] = str(Path(directory) / 'test.db')
        os.environ['SECRET_KEY'] = 'management-ui-test-only'
        import app as web
        from werkzeug.serving import make_server
        from playwright.sync_api import sync_playwright

        server = make_server('127.0.0.1', 0, web.app, threaded=True)
        base = f'http://127.0.0.1:{server.server_port}'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                for label, width, height in [('desktop',1440,1000),('mobile',390,844),('small',320,740)]:
                    context = browser.new_context(viewport={'width':width,'height':height})
                    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                    page = context.new_page()
                    errors = []
                    external = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(base+'/login')
                    page.locator('[name=username]').fill('admin')
                    page.locator('[name=password]').fill('admin')
                    page.locator('button[type=submit]').click()
                    page.wait_for_url('**/admin')
                    page.on('request', lambda request: external.append(request.url) if not request.url.startswith(base) else None)
                    paths = ['/admin/clubes','/admin/miembros','/admin/clubes/club-1/miembros','/admin/eventos','/admin/eventos/ev-3','/admin/incidentes','/admin/penalizaciones','/admin/penalizaciones/motivos','/admin/usuarios','/admin/resultados','/admin/reportes?tipo=staff']
                    for path in paths:
                        response = page.goto(base+path)
                        assert response.status == 200, (label,path)
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), (label,path)
                        if output and path in ['/admin/clubes','/admin/miembros','/admin/eventos','/admin/incidentes']:
                            page.screenshot(path=str(output/(label+'-'+path.rsplit('/',1)[1]+'.png')), full_page=True)
                    page.goto(base+'/admin/clubes')
                    search = page.locator('.mg-table-search input')
                    search.fill('aguilas')
                    assert page.locator('tbody tr:visible').count() == 1
                    search.fill('no-existe')
                    assert page.get_by_text('No hay registros que coincidan con la búsqueda.', exact=True).is_visible()
                    search.fill('')
                    page.goto(base+'/admin/miembros')
                    assert page.locator('tbody tr:visible').count() == 10
                    page.get_by_role('button',name='Siguiente',exact=True).click()
                    assert page.locator('.mg-current-page').inner_text() == '2 / 4'
                    page.goto(base+'/admin/clubes')
                    page.locator('.mg-create summary').click()
                    page.locator('.mg-create input[name=nombre]').fill('Club prueba '+label)
                    page.locator('.mg-create button[type=submit]').click()
                    page.locator('.mg-table-search input').fill('Club prueba '+label)
                    row = page.locator('tbody tr:visible')
                    row.locator('.mg-edit summary').click()
                    row.locator('.mg-edit input[name=nombre]').fill('Club editado '+label)
                    row.locator('.mg-edit button[type=submit]').click()
                    page.locator('.mg-table-search input').fill('Club editado '+label)
                    row = page.locator('tbody tr:visible')
                    row.get_by_role('link',name='Ver miembros de Club editado '+label).click()
                    page.locator('.mg-create summary').click()
                    page.locator('.mg-create input[name=nombre]').fill('Miembro nuevo '+label)
                    page.locator('.mg-create button[type=submit]').click()
                    assert page.locator('tbody').inner_text().find('Miembro nuevo '+label) >= 0
                    page.once('dialog',lambda dialog:dialog.accept())
                    page.get_by_role('button',name='Eliminar Miembro nuevo '+label,exact=True).click()
                    page.wait_for_load_state('load')
                    page.goto(base+'/admin/clubes')
                    page.locator('.mg-table-search input').fill('Club editado '+label)
                    page.once('dialog',lambda dialog:dialog.accept())
                    page.get_by_role('button',name='Eliminar Club editado '+label,exact=True).click()
                    page.wait_for_load_state('load')
                    page.locator('.mg-table-search input').fill('Club editado '+label)
                    assert page.locator('tbody tr:visible').count() == 0
                    assert not errors, errors
                    assert not external, external
                    context.close()
                    print('OK:',label,'11 vistas, búsqueda, paginación, CRUD club/miembro y sin recursos externos')
                browser.close()
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
