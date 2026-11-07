#!/usr/bin/env python3
"""Close finished application tabs in the job Chrome (Joey's rule 2026-10-28: close application pages after applying, to save memory).
A tab is closed when it shows a submission confirmation or a post-submit page:
  Greenhouse /confirmation · Workday Candidate Home (/userHome), /jobTasks/completed, "Congratulations", "Application Submitted",
  "Thank you for applying" · a Workday job list reached after submit (?Job_Application_ID=) · leftover example.com marker tabs.
Unfinished forms (an /apply page without a confirmation) are kept.
  ~/.job-agent-venv/bin/python close_done_tabs.py [--dry-run]"""
import re, sys
from playwright.sync_api import sync_playwright
DONE_URL = re.compile(r'/confirmation|/userHome|/jobTasks/completed|Job_Application_ID=|example\.com/\?cx=', re.I)
DONE_TXT = re.compile(r'congratulations|application (was )?submitted|thank you for (applying|your application)|we have received your application', re.I)
dry = '--dry-run' in sys.argv
with sync_playwright() as pw:
    ctx = pw.chromium.connect_over_cdp('http://127.0.0.1:9222').contexts[0]
    pages = [p for p in ctx.pages if p.url.startswith('http')]
    closed, kept = [], []
    for p in pages:
        url = p.url
        try: txt = p.inner_text('body', timeout=3000)[:5000]
        except Exception: txt = ''
        if '/apply' in url and not DONE_TXT.search(txt):
            kept.append(url[:90]); continue                       # unfinished form: keep
        if DONE_URL.search(url) or DONE_TXT.search(txt):
            closed.append(url[:90])
            if not dry and len(ctx.pages) > 1: p.close()
        else:
            kept.append(url[:90])
    print(('would close' if dry else 'closed'), len(closed), closed)
    print('kept', len(kept), kept)
