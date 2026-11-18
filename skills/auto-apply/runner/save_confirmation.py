#!/usr/bin/env python3
"""Save a full-page screenshot + the page text of a confirmation / Candidate Home tab into an application folder.
   save_confirmation.py <url text> "<app folder>"   → submitted_confirmation.png, confirmation.txt"""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import sys, os
from playwright.sync_api import sync_playwright
key, folder = sys.argv[1], sys.argv[2]
folder = os.path.abspath(folder)
if not os.path.isdir(folder):
    # A relative path from runner/ used to create a stray skills/applications/<folder>/ (#48).
    print('no such application folder:', folder, '\npass the absolute path', flush=True); sys.exit(2)
with sync_playwright() as pw:
    pages = [p for p in cdp_connect.connect(pw, 'http://127.0.0.1:9222').contexts[0].pages if key in p.url]
    if not pages: print('no tab for', key); sys.exit(1)
    p = pages[-1]
    p.screenshot(path=os.path.join(folder, 'submitted_confirmation.png'), full_page=True)
    open(os.path.join(folder, 'confirmation.txt'), 'w').write(p.url + '\n\n' + p.inner_text('body')[:6000])
    print('saved', folder, '|', p.url[:80])
