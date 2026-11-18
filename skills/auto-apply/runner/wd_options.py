#!/usr/bin/env python3
"""List the options of one Workday dropdown/prompt in an open tab (job Chrome).  wd_options.py <url text> <label text> [category to open]"""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import sys, time, json
from playwright.sync_api import sync_playwright
key, label = sys.argv[1], sys.argv[2]; cat = sys.argv[3] if len(sys.argv) > 3 else None
JS = '''() => [...document.querySelectorAll('[data-automation-id="promptOption"], [role="listbox"] [role="option"]')]
  .filter(o => o.getClientRects().length && !o.closest('[data-automation-id^="formField-"]')).map(o => o.textContent.replace(/\\s+/g, ' ').trim())'''
with sync_playwright() as pw:
    pg = [p for p in cdp_connect.connect(pw, 'http://127.0.0.1:9222').contexts[0].pages if key in p.url][-1]
    box = pg.locator('[data-automation-id^="formField-"]').filter(has_text=label).first
    box.scroll_into_view_if_needed(); box.locator('input, button[aria-haspopup="listbox"]').first.click(); time.sleep(1.2)
    top = pg.evaluate(JS); sub = None
    if cat:
        pg.locator('[data-automation-id="promptOption"]').filter(has_text=cat).first.click(); time.sleep(1.2); sub = pg.evaluate(JS)
    pg.keyboard.press('Escape')
    print(json.dumps({'top': top, 'sub': sub}, ensure_ascii=False))
