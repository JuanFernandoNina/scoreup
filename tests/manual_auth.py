"""Verifica diseño y flujos de acceso con Edge y SQLite temporal."""
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
    with tempfile.TemporaryDirectory(prefix='scoreup-auth-ui-') as directory:
        os.environ['SCOREUP_DB'] = str(Path(directory) / 'test.db')
        os.environ['SECRET_KEY'] = 'auth-ui-test-only'
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
                    errors, external = [], []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('request', lambda request: external.append(request.url) if not request.url.startswith(base) else None)
                    for path in ['/login','/registro']:
                        page.goto(base+path)
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), (label,path)
                        assert page.locator('h1').count() == 1
                        assert page.locator('[name=csrf_token]').input_value()
                        if output:
                            page.screenshot(path=str(output/(label+'-'+path[1:]+'.png')),full_page=True,animations='disabled')
                    # Error de registro: conserva solo los campos no secretos.
                    page.locator('[name=nombre]').fill('Prueba '+label)
                    page.locator('[name=organizacion]').fill('Organizacion '+label)
                    page.locator('[name=username]').fill('admin')
                    page.locator('[name=password]').fill('test-only-password')
                    page.get_by_role('button',name='Mostrar contraseña').click()
                    assert page.locator('[name=password]').get_attribute('type') == 'text'
                    page.get_by_role('button',name='Ocultar contraseña').click()
                    page.locator('button[type=submit]').click()
                    page.get_by_role('alert').filter(has_text='ya está en uso').wait_for()
                    assert page.locator('[name=nombre]').input_value() == 'Prueba '+label
                    assert page.locator('[name=password]').input_value() == ''
                    # Alta real en base de prueba.
                    page.locator('[name=username]').fill('auth-prueba-'+label)
                    page.locator('[name=password]').fill('test-only-password')
                    page.locator('button[type=submit]').click()
                    page.wait_for_url('**/admin')
                    page.goto(base+'/logout')
                    # Login incorrecto y vuelta al club después de escanear sin sesión.
                    club = next(c for c in web.DB['clubs'] if c.id == 'club-1')
                    qr = '/qr/'+web._token_club(club)
                    page.goto(base+qr)
                    assert page.locator('.auth-qr-notice').is_visible()
                    page.locator('[name=username]').fill('tomas')
                    page.locator('[name=password]').fill('wrong-test-only')
                    page.locator('button[type=submit]').click()
                    page.get_by_role('alert').wait_for()
                    assert page.locator('[name=next]').input_value() == qr
                    assert page.locator('[name=username]').input_value() == 'tomas'
                    assert page.locator('[name=password]').input_value() == ''
                    assert not external, external
                    page.locator('[name=password]').fill('staff')
                    page.locator('button[type=submit]').click()
                    page.wait_for_url('**/staff?club=club-1')
                    assert not errors, errors
                    context.close()
                    print('OK:',label,'diseño, contraseña, errores, registro y retorno QR sin recursos externos')
                for options in [{'reduced_motion':'reduce'},{'java_script_enabled':False}]:
                    context = browser.new_context(viewport={'width':390,'height':844},**options)
                    page = context.new_page()
                    page.goto(base+'/login')
                    assert page.locator('button[type=submit]').is_visible()
                    if options.get('reduced_motion'):
                        assert page.locator('.auth-card').evaluate('el => getComputedStyle(el).animationName') == 'none'
                    else:
                        assert not page.locator('[data-password-toggle]').is_visible()
                    context.close()
                browser.close()
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
