"""Ergonomía móvil de los tres roles con Edge y SQLite temporal."""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    output=Path(sys.argv[1]) if len(sys.argv)>1 else None
    if output:output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='scoreup-mobile-') as directory:
        os.environ['SCOREUP_DB']=str(Path(directory)/'test.db')
        os.environ['SECRET_KEY']='mobile-test-only'
        import app as web
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server
        server=make_server('127.0.0.1',0,web.app,threaded=True)
        base=f'http://127.0.0.1:{server.server_port}'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                for width,height in [(390,844),(320,740)]:
                    for role,username,password,path in [('admin','admin','admin','/admin'),('staff','tomas','staff','/staff'),('director','lucia','director','/director')]:
                        context=browser.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
                        context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base) else route.abort())
                        page=context.new_page();errors=[]
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        page.goto(base+'/login')
                        page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password)
                        page.locator('button[type=submit]').click();page.wait_for_url('**'+path)
                        page.wait_for_load_state('load')
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),(role,width)
                        if role=='admin':
                            page.get_by_role('button',name='Abrir menú',exact=True).tap()
                            assert page.locator('.admin-main').evaluate('el=>el.inert')
                            assert page.locator('.admin-mobile-backdrop').is_visible()
                            page.locator('.admin-mobile-backdrop').tap(position={'x':width-5,'y':200})
                            assert not page.locator('.admin-main').evaluate('el=>el.inert')
                            for section in ['clubes','miembros','eventos','incidentes','usuarios']:
                                page.goto(base+'/admin/'+section)
                                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),(section,width)
                                table=page.locator('.mobile-card-table').first
                                assert table.count()>0,section
                                assert table.evaluate('el=>getComputedStyle(el).display')=='block'
                                assert page.locator('tbody tr:visible').first.locator('td[data-label]').count()>0
                                if output and section in ['clubes','miembros']:
                                    page.screenshot(path=str(output/f'{width}-admin-{section}.png'),full_page=True,animations='disabled')
                        else:
                            nav=page.locator('.staff-nav');box=nav.bounding_box()
                            assert abs(box['y']+box['height']-height)<3,(role,width,box)
                            assert nav.locator('a').first.bounding_box()['height']>=44
                            page.evaluate('scrollTo(0,document.body.scrollHeight)')
                            assert abs(nav.bounding_box()['y']+nav.bounding_box()['height']-height)<3
                            if role=='staff':
                                page.locator('.staff-nav a').filter(has_text='Clubes').tap();page.wait_for_url('**/staff?vista=clubes')
                                page.locator('#staff-search').fill('tigres')
                                assert page.locator('.staff-club-row:visible').count()==1
                                page.locator('.staff-club-row:visible a').tap();page.wait_for_url('**/staff?club=club-1')
                                assert page.locator('[data-weight]').first.evaluate('el=>parseFloat(getComputedStyle(el).fontSize)')>=16
                                for field in page.locator('[data-weight]').all():field.fill('50')
                                assert page.locator('[data-score-output]').inner_text()=='160 pts'
                                if output:
                                    page.evaluate('scrollTo(0,0)');page.wait_for_function('scrollY===0')
                                    page.screenshot(path=str(output/f'{width}-staff-evaluar.png'),full_page=True,animations='disabled')
                                    page.screenshot(path=str(output/f'{width}-staff-pantalla.png'),animations='disabled')
                            else:
                                page.locator('.staff-nav a[href="#resultados"]').tap()
                                page.locator('.director-table').wait_for()
                                assert page.locator('.director-table').evaluate('el=>getComputedStyle(el).display')=='block'
                                assert page.locator('.director-table td[data-label="Puntaje"]').count()>0
                                if output:
                                    page.evaluate('scrollTo(0,0)');page.wait_for_function('scrollY===0')
                                    page.screenshot(path=str(output/f'{width}-director.png'),full_page=True,animations='disabled')
                                    page.screenshot(path=str(output/f'{width}-director-pantalla.png'),animations='disabled')
                        assert not errors,errors
                        context.close();print('OK:',width,role,'navegación, controles táctiles, formularios y tablas')
                browser.close()
        finally:server.shutdown();thread.join()


if __name__=='__main__':main()
