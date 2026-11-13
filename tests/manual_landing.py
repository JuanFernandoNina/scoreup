"""Portada en Edge: animaciones, móvil, reducción de movimiento y sin JavaScript."""
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
    with tempfile.TemporaryDirectory(prefix="scoreup-landing-ui-") as directory:
        os.environ["SCOREUP_DB"] = str(Path(directory) / "test.db")
        os.environ["SECRET_KEY"] = "landing-ui-test-only"
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
                    external = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("request", lambda request: external.append(request.url) if not request.url.startswith(base) else None)
                    page.goto(base)
                    assert page.locator('h1').count() == 1
                    assert page.locator('.lp-hero-copy').evaluate("el => el.classList.contains('is-visible')")
                    page.wait_for_function("getComputedStyle(document.querySelector('.lp-role-card')).opacity === '0'")
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), (label, 'inicio')
                    if output:
                        page.screenshot(path=str(output / (label + '-hero.png')), animations='disabled')
                    if width < 760:
                        page.locator('.lp-mobile-menu summary').click()
                        assert page.locator('.lp-mobile-menu nav').is_visible()
                        page.locator('.lp-mobile-menu a[href="#roles"]').click()
                        assert page.locator('.lp-mobile-menu').get_attribute('open') is None
                    page.evaluate("document.documentElement.style.scrollBehavior = 'auto'")
                    for element in page.locator('[data-reveal]').all():
                        element.scroll_into_view_if_needed()
                        page.wait_for_function("el => el.classList.contains('is-visible')", arg=element.element_handle())
                    page.locator('#lp-disciplina').evaluate("el => { el.value=100; el.dispatchEvent(new Event('input')); }")
                    assert page.locator('#lp-demo-total').inner_text().startswith('96 ')
                    for input in page.locator('[data-demo-weight]').all():
                        input.evaluate("el => { el.value=50; el.dispatchEvent(new Event('input')); }")
                    assert page.locator('#lp-demo-total').inner_text().startswith('50 ')
                    page.locator('.lp-faqs summary').first.click()
                    assert page.locator('.lp-faqs details').first.get_attribute('open') is not None
                    page.locator('.lp-footer').scroll_into_view_if_needed()
                    assert page.locator('#lp-header').evaluate("el => el.classList.contains('is-scrolled')")
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), (label, 'footer')
                    page.evaluate('scrollTo(0,0)')
                    if output:
                        page.screenshot(path=str(output / (label + '-completa.png')), full_page=True, animations='disabled')
                    assert not errors, errors
                    assert not external, external
                    page.locator('.lp-hero-buttons a[href="/registro"]').click()
                    page.wait_for_url('**/registro')
                    context.close()
                    print('OK:', label, 'scroll, revelado, menú, demo, FAQ, CTA y sin solicitudes externas')
                for label, options in [('reduced', {"reduced_motion": "reduce"}), ('no-js', {"java_script_enabled": False})]:
                    context = browser.new_context(viewport={"width": 390, "height": 844}, **options)
                    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                    page = context.new_page()
                    page.goto(base)
                    assert page.locator('.lp-role-card').first.evaluate("el => getComputedStyle(el).opacity") == '1'
                    assert page.locator('.lp-float-card').first.evaluate("el => getComputedStyle(el).animationName") == ('none' if label == 'reduced' else 'lp-float')
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                    context.close()
                    print('OK:', label, 'contenido visible y accesible')
                browser.close()
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
