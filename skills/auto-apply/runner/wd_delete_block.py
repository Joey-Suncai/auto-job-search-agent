#!/usr/bin/env python3
"""Delete one repeat block (e.g. "Work Experience 1") in an open Workday tab.  wd_delete_block.py <url text> "<block heading>" """
import sys, time
from playwright.sync_api import sync_playwright
key, heading = sys.argv[1], sys.argv[2]
with sync_playwright() as pw:
    pg = [p for p in pw.chromium.connect_over_cdp('http://127.0.0.1:9222').contexts[0].pages if key in p.url][-1]
    pid = pg.evaluate('''(h) => { const g = [...document.querySelectorAll('[role="group"][aria-labelledby$="-panel"]')]
        .find(g => { const e = document.getElementById(g.getAttribute('aria-labelledby').split(' ')[0]); return e && e.textContent.trim() === h; });
        return g ? g.getAttribute('aria-labelledby') : null; }''', heading)
    print('panel', pid)
    ok = pg.evaluate('''(pid) => { let e = document.getElementById(pid); const q = 'button[data-automation-id="panel-set-delete-button"], button[aria-label*="Delete" i]';
        while (e && !(e.querySelector(q) || [...e.querySelectorAll('button')].find(b => /^delete$/i.test(b.textContent.trim())))) e = e.parentElement;
        if (!e) return false; const b = e.querySelector(q) || [...e.querySelectorAll('button')].find(b => /^delete$/i.test(b.textContent.trim()));
        b.setAttribute('data-cx-del', '1'); return true; }''', pid)
    print('delete button found', ok)
    pg.locator('[data-cx-del="1"]').first.click(timeout=5000); time.sleep(1.5)
    print('after', pg.evaluate('''() => [...document.querySelectorAll('[role="group"][aria-labelledby$="-panel"]')].map(g => (document.getElementById(g.getAttribute('aria-labelledby').split(' ')[0])||{}).textContent)'''))
