"""Real-browser end-to-end smoke test; run separately from unittest discovery."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evaluation'/'browser-artifacts'
OUT.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as data:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=subprocess.Popen([sys.executable,'-m','uvicorn','showroom.app:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env={**os.environ,'SHOWROOM_DATA_DIR':data},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        base=f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                with urlopen(base+'/api/health',timeout=1):break
            except OSError:time.sleep(.1)
        else:raise AssertionError('Server did not become healthy.')
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base)
            page.locator('.car').first.wait_for()
            assert page.locator('.car').count()==11
            page.locator('#message').fill('Show automatic cars under 12 lakh')
            page.locator('#ask').click()
            page.get_by_text('Answer generated from the catalog. No booking was created.',exact=True).wait_for()
            assert page.locator('.car').count()==3
            page.locator('details.tool summary').click()
            assert 'search' in page.locator('#trace').inner_text()
            page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
            page.locator('#resetFilters').click()
            page.locator('[data-car-id="CAR-001"]').wait_for()
            page.get_by_label('Select CAR-001 for comparison').check()
            page.get_by_label('Select CAR-002 for comparison').check()
            page.locator('#compare').click()
            page.get_by_role('heading',name='Current catalog comparison').wait_for()
            page.locator('#authButton').click()
            page.locator('#toggleAuth').click()
            page.locator('#name').fill('Demo Customer')
            page.locator('#email').fill('browser-demo@example.test')
            page.locator('#password').fill('Local-browser-pass-123')
            page.locator('#authSubmit').click()
            page.locator('#auth').wait_for(state='hidden')
            page.locator('[data-car-id="CAR-001"]').get_by_role('button',name='Request booking').click()
            page.locator('#booking').wait_for(state='visible')
            # Confirmation without consent is rejected in the UI.
            page.locator('#confirm').click()
            page.get_by_text('Confirm that you understand this is a demo request.',exact=True).wait_for()
            page.locator('#consent').check()
            page.locator('#confirm').click()
            page.locator('#booking').wait_for(state='hidden')
            assert 'No real reservation or payment' in page.locator('#status').inner_text()
            page.locator('#myBookings').click()
            page.get_by_role('button',name='Cancel demo request').click()
            page.get_by_text('cancelled',exact=False).wait_for()
            assert page.get_by_role('button',name='Cancel demo request').count()==0
            page.get_by_label('Close requests').click()
            page.locator('#authButton').click()
            page.get_by_role('button',name='Sign in',exact=True).wait_for()
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
            assert errors==[],errors
            browser.close()
        print('Browser smoke passed: search, compare, signup, consent, booking, cancellation, logout, mobile width, JS errors.')
    finally:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait()
