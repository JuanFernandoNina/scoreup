"""Prueba de la web explicativa en Edge; no interactúa con ScoreUp ni la red."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if output:
    output.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    for label, width, height in [('desktop',1440,1000),('mobile',390,844),('small',320,740)]:
        context = browser.new_context(viewport={'width':width,'height':height})
        context.route('http://**/*', lambda route: route.abort())
        context.route('https://**/*', lambda route: route.abort())
        page = context.new_page()
        errors, network = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: network.append(request.url) if request.url.startswith(('http:','https:')) else None)
        page.goto((root/'index.html').as_uri())
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), label
        assert 'sin internet' in page.locator('#state-title').inner_text()
        assert not page.locator('#run-demo').is_disabled()
        page.get_by_role('button',name='Hay internet de nuevo').click()
        assert 'internet es opcional' in page.locator('#state-title').inner_text()
        page.get_by_role('button',name='Se apaga el router').click()
        assert page.locator('#run-demo').is_disabled()
        assert 'celulares no tienen' in page.locator('#state-title').inner_text()
        page.get_by_role('button',name='Se apaga la laptop').click()
        assert 'no pueden guardar' in page.locator('#state-title').inner_text()
        page.get_by_role('button',name='Campamento sin internet').click()
        page.locator('#run-demo').click()
        page.wait_for_function("document.querySelectorAll('#trace .done').length === 4")
        assert 'No se usó internet' in page.locator('#trace-note').inner_text()
        page.locator('#run-demo').click()
        page.locator('#router').uncheck()
        page.wait_for_timeout(1000)
        assert 'enciende router' in page.locator('#trace-note').inner_text()
        assert page.locator('#trace .done').count() == 0
        page.locator('#router').check()
        for check in page.locator('[data-check]').all()[:2]:
            check.check()
        assert '2 de 10' in page.locator('#check-counter').inner_text()
        broken = page.evaluate("[...document.querySelectorAll('a[href^=\"#\"]')].map(a=>a.getAttribute('href')).filter(h=>h.length>1&&!document.getElementById(h.slice(1)))")
        assert not broken, broken
        page.locator('details summary').first.click()
        assert page.locator('details').first.get_attribute('open') is not None
        page.evaluate("document.documentElement.style.scrollBehavior='auto'; scrollTo(0,0)")
        if output:
            page.screenshot(path=str(output/(label+'.png')), full_page=True, animations='disabled')
        assert not errors, errors
        assert not network, network
        context.close()
        print('OK:',label,'sin red; estados, simulación, cancelación, checklist, FAQ y enlaces')
    context = browser.new_context(viewport={'width':390,'height':844},java_script_enabled=False)
    page = context.new_page()
    page.goto((root/'index.html').as_uri())
    assert page.get_by_role('heading',name='Así sería la conexión.').is_visible()
    assert page.locator('noscript').is_visible()
    context.close()
    browser.close()
print('OK: lectura del diagrama sin JavaScript.')
