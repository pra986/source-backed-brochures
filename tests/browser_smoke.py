"""Real Chromium smoke test; run after installing Playwright Chromium."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright,expect

out=Path('evaluation/browser-artifacts');out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as data:
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env=dict(os.environ,MINUTES_DATA_DIR=data)
    server=subprocess.Popen([sys.executable,'-m','uvicorn','minutes.app:app','--host','127.0.0.1','--port',str(port)],env=env,stdout=subprocess.DEVNULL)
    try:
        url=f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:urllib.request.urlopen(url+'/api/health',timeout=1);break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Server did not start')
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url);page.locator('#demo').click()
            page.locator('#analyze').click();expect(page.locator('#reviewState')).to_have_text('Draft · review needed')
            expect(page.locator('[data-item-id]')).to_have_count(9);expect(page.locator('#markdown')).to_have_attribute('aria-disabled','true')
            page.locator('.source-link').first.click();expect(page.locator('#source-S001')).to_be_visible()
            page.get_by_label('Edit I007',exact=True).fill('Add a duplicate-confirmation regression test.')
            page.locator('#approved').check();page.locator('#save').click();expect(page.locator('#reviewState')).to_have_text('Reviewed · saved')
            expect(page.locator('#markdown')).to_have_attribute('aria-disabled','false')
            for name in ['markdown','csv','json']:
                with page.expect_download() as event:page.locator('#'+name).click()
                download=event.value;download.save_as(out/download.suggested_filename)
            snapshot=json.loads(next(out.glob('meeting-*.json')).read_text());assert snapshot['revision']==2 and snapshot['reviewed']
            assert 'Add a duplicate-confirmation regression test.' in next(out.glob('*.csv')).read_text()
            page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(out/'desktop.png'),full_page=True)
            page.reload();page.locator('#history button').first.click();expect(page.locator('#reviewState')).to_have_text('Reviewed · saved')
            page.locator('#addItem').click();page.locator('#newText').fill('Reviewer-added follow-up');page.locator('#newSource').select_option('S006');page.locator('#submitItem').click()
            expect(page.locator('#addDialog')).not_to_be_visible();expect(page.locator('#reviewState')).to_have_text('Draft · review needed');expect(page.locator('[data-item-id]')).to_have_count(10)
            expect(page.locator('#markdown')).to_have_attribute('aria-disabled','true')
            page.locator('#approved').check();page.locator('#save').click();expect(page.locator('#reviewState')).to_have_text('Reviewed · saved')
            page.get_by_text('Revision history',exact=True).click();page.locator('#loadRevisions').click();expect(page.locator('.revision-row')).to_have_count(4)
            page.set_viewport_size({'width':390,'height':844});page.evaluate('window.scrollTo(0,0)')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),'Mobile horizontal overflow'
            page.screenshot(path=str(out/'mobile.png'),full_page=True)
            page.locator('#delete').click();page.locator('#cancelDelete').click();expect(page.locator('#review')).to_be_visible()
            page.locator('#delete').click();page.locator('#confirmDelete').click();expect(page.locator('#empty')).to_be_visible();expect(page.locator('#history button')).to_have_count(0)
            assert not errors,errors
            browser.close();print('Browser smoke passed: review, downloads, persistence, manual addition, revisions, responsive layout, deletion.')
    finally:server.terminate();server.wait(timeout=10)
