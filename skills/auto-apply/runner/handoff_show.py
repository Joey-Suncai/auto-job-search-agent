#!/usr/bin/env python3
"""Read-only: show what a handoff.json asks for, and what the live page holds right now.
   ~/.job-agent-venv/bin/python handoff_show.py "<app folder>" [--cdp URL]
   Writes nothing, clicks nothing. Safe for both DSH (CDP) and Claude Code."""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import json, os, sys, argparse
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument('folder')
ap.add_argument('--cdp', default='http://127.0.0.1:9222')
a = ap.parse_args()
hp = os.path.join(a.folder, 'handoff.json')
h = json.load(open(hp))
print('handoff created:', h.get('created'), '| tab_marker:', h.get('tab_marker'))
print('page_url:', h.get('page_url'))
print('fields to set:', len(h.get('fields') or []))
for f in h.get('fields') or []:
    print(f"  - {str(f.get('label'))[:60]!r}")
    print(f"      want={str(f.get('want'))[:60]!r} sel={str(f.get('sel'))[:70]}")
    print(f"      page_now={str(f.get('page_now'))[:60]!r} react_now={str(f.get('react_now'))[:40]!r}")
    if f.get('errors'):
        print('      errors:', f['errors'][:3])
with sync_playwright() as pw:
    b = cdp_connect.connect(pw, a.cdp)
    ctx = b.contexts[0]
    pages = [p for p in ctx.pages if h.get('page_url', '')[:80] in p.url] or [p for p in ctx.pages if 'myworkday' in p.url or 'greenhouse' in p.url]
    if not pages:
        print('\nNO MATCHING TAB — reopen the form, then rerun this'); sys.exit(1)
    p = pages[0]
    print('\nlive tab:', p.url[:110])
    pg = p.evaluate('''(keys) => { const out={}; for (const k of keys) { let el=null; try{el=document.querySelector(k)}catch(e){}
        out[k]= el ? (el.value!==undefined && el.value!=='' ? String(el.value).slice(0,80) : (el.innerText||'').trim().slice(0,60)) : 'MISSING'; } return out; }''',
        [f.get('sel') for f in (h.get('fields') or []) if f.get('sel')])
    for k, v in pg.items():
        print('  page value:', v[:80], '  <=', k[:60])
