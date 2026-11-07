#!/usr/bin/env python3
"""Show which Workday fields are flagged invalid in an open tab: block heading, label, current value.  wd_errors.py <url text>"""
import sys, json
from playwright.sync_api import sync_playwright
JS = '''() => [...document.querySelectorAll('[aria-invalid="true"], [data-automation-id="errorMessage"]')].map(el => {
  const box = el.closest('[data-automation-id^="formField-"]');
  const grp = el.closest('[role="group"][aria-labelledby$="-panel"]');
  const h = grp && document.getElementById(grp.getAttribute('aria-labelledby').split(' ')[0]);
  const inp = box && box.querySelector('input, textarea, button[aria-haspopup]');
  return { block: h ? h.textContent.trim() : '', aid: box ? box.getAttribute('data-automation-id') : '',
           label: box ? (box.querySelector('label, legend') || {}).textContent : el.textContent.slice(0, 80),
           value: inp ? (inp.value || inp.textContent || '').slice(0, 60) : '', stamp: box ? box.getAttribute('data-cx-k') : '' }; })'''
BLOCKS = '''() => [...document.querySelectorAll('[role="group"][aria-labelledby$="-panel"]')].map(g => {
  const h = document.getElementById(g.getAttribute('aria-labelledby').split(' ')[0]);
  return (h ? h.textContent.trim() : g.getAttribute('aria-labelledby')) + ' :: ' +
    [...g.querySelectorAll('input[type=text], textarea')].map(i => i.value).filter(Boolean).join(' / ').slice(0, 100); })'''
with sync_playwright() as pw:
    pg = [p for p in pw.chromium.connect_over_cdp('http://127.0.0.1:9222').contexts[0].pages if sys.argv[1] in p.url][-1]
    print(json.dumps({'invalid': pg.evaluate(JS)[:12], 'blocks': pg.evaluate(BLOCKS)}, ensure_ascii=False, indent=0))
