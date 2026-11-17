"""Tema común y scroll de los tres paneles; SQLite temporal y Edge."""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    output=Path(sys.argv[1]) if len(sys.argv)>1 else None
    if output: output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='scoreup-panel-theme-') as directory:
        os.environ['SCOREUP_DB']=str(Path(directory)/'test.db')
        os.environ['SECRET_KEY']='panel-theme-test-only'
        import app as web
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server
        server=make_server('127.0.0.1',0,web.app,threaded=True)
        base=f'http://127.0.0.1:{server.server_port}'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                for label,width,height in [('desktop',1440,1000),('mobile',390,844),('small',320,740)]:
                    for role,username,password,path in [('admin','admin','admin','/admin'),('staff','tomas','staff','/staff'),('director','lucia','director','/director')]:
                        context=browser.new_context(viewport={'width':width,'height':height})
                        context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base) else route.abort())
                        page=context.new_page();errors=[];external=[]
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        page.on('request',lambda request:external.append(request.url) if not request.url.startswith(base) else None)
                        page.goto(base+'/login')
                        page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password)
                        page.locator('button[type=submit]').click();page.wait_for_url('**'+path)
                        page.wait_for_load_state('load')
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'),(role,label)
                        assert page.locator('[data-panel-theme]').count()==1
                        if role=='staff':
                            assert page.locator('.staff-action').count()==4
                            assert '36, 92, 238' in page.locator('.staff-hero').evaluate('el => getComputedStyle(el).backgroundImage') or 'linear-gradient' in page.locator('.staff-hero').evaluate('el => getComputedStyle(el).backgroundImage')
                        if role=='director':
                            qr=page.locator('.director-qr-image img')
                            assert qr.is_visible()
                            assert qr.evaluate('(image)=>image.complete && image.naturalWidth > 0')
                            assert qr.get_attribute('src')=='/director/qr.png'
                            assert page.locator('#qr-de-mi-club').inner_text().count('Tigres del Valle')==1
                            with page.expect_download() as download:
                                page.get_by_role('link',name='Descargar QR en PNG',exact=True).click()
                            assert download.value.suggested_filename=='scoreup-club-1-qr.png'
                            assert page.locator('.director-stat').count()==4
                            assert not page.locator('form[method=post]').count()
                            assert 'Campamento Regional' not in page.locator('.director-table').inner_text()
                            page.locator('.director-season button').click();page.wait_for_url('**/director?temporada=2026')
                            page.wait_for_load_state('load')
                        assert page.locator('.panel-reveal').count()>0,(role,label)
                        page.evaluate("document.documentElement.style.scrollBehavior='auto'")
                        for card in page.locator('.panel-reveal').all():
                            card.scroll_into_view_if_needed()
                            page.wait_for_function("el=>el.classList.contains('panel-visible')",arg=card.element_handle())
                        page.locator('footer').last.scroll_into_view_if_needed()
                        if page.evaluate('document.documentElement.scrollHeight > innerHeight'):
                            page.wait_for_function("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--panel-scroll'))>0")
                        page.evaluate('scrollTo(0,0)')
                        if output:page.screenshot(path=str(output/(label+'-'+role+'.png')),full_page=True,animations='disabled')
                        assert not errors,errors
                        assert not external,external
                        context.close();print('OK:',label,role,'tema, scroll, ancho y recursos locales')
                for options in [{'reduced_motion':'reduce'},{'java_script_enabled':False}]:
                    context=browser.new_context(viewport={'width':390,'height':844},**options)
                    page=context.new_page();page.goto(base+'/login')
                    page.locator('[name=username]').fill('tomas');page.locator('[name=password]').fill('staff')
                    page.locator('button[type=submit]').click();page.wait_for_url('**/staff')
                    assert page.locator('.staff-card').last.evaluate('el=>getComputedStyle(el).opacity')=='1'
                    if options.get('reduced_motion'):
                        assert page.locator('.staff-hero').evaluate("el=>getComputedStyle(el,'::after').animationName")=='none'
                    context.close()
                browser.close()
        finally:server.shutdown();thread.join()


if __name__=='__main__':main()
