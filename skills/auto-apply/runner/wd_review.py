#!/usr/bin/env python3
"""Print the key items of a Workday Review page (open tab in the job Chrome) for the pre-submit check.
   ~/.job-agent-venv/bin/python wd_review.py <text in the tab URL, e.g. the job req id>"""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import os, re, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077)
from playwright.sync_api import sync_playwright

def main():
    key = sys.argv[1]
    with sync_playwright() as pw:
        pages = [p for p in cdp_connect.connect(pw, 'http://127.0.0.1:9222').contexts[0].pages if key in p.url]
        if not pages: print('no tab for', key); return
        t = pages[-1].inner_text('body')
    def g(rx):
        m = re.search(rx, t, re.I)
        return m.group(0).replace('\n', ' | ')[:120] if m else '-'
    out = {
        'step': g(r'current step \d of \d[^\n]*'),
        'name': g(r'\nName\n[^\n]+'), 'preferred': g(r'Preferred Name\n[^\n]+'), 'phone': g(r'Phone\n[^\n]+'),
        'work_blocks': re.findall(r'\n((?:Work Experience|Work History)[^\n]*\d)\n', t),
        'companies': [c for c in jsa_profile.get('employers', []) if c in t],
        'unexpected_in_work': [w for w in jsa_profile.get('not_work_items', []) if w in t],
        'schools': [e['school'] for e in jsa_profile.get('education', []) if e['school'] in t],
        'degrees': re.findall(r'\nDegree\n+([^\n]+)', t)[:3], 'fields_of_study': re.findall(r'Field of Study\n+([^\n]+)', t)[:3],
        'source': g(r'Hear About Us\?\n+[^\n]+'), 'veteran': g(r'veteran[^\n]*\n+[^\n]+'), 'gender': g(r'gender[^\n]*\n+[^\n]+'),
        'race': g(r'(ethnicity|race)[^\n]*\n+[^\n]+'), 'disability': g(r'disabilit[^\n]*\n+[^\n]+'),
        'sponsorship': re.findall(r'sponsor[^\n]*\n+([^\n]+)', t, re.I)[:3], 'any_employer': g(r'any employer[^\n]*\n+[^\n]+'),
        'middle_NA': bool(re.search(r'\bN/A\b', t)), 'phone_extension_bug': bool(re.search(r'x\s*447', t)),
    }
    print(json.dumps(out, ensure_ascii=False, indent=0))

main()
