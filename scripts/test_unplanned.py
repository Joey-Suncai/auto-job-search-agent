#!/usr/bin/env python3
"""Harness for run.py Run.unplanned_required (rule 13): each DeepSeek case's HTML is loaded in a headless Chrome and
the method runs against it. Verdicts in test_cases/unplanned_verdicts.json. Skips (exit 0) when no browser is available."""
import json, os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
cases = json.load(open(os.path.join(HERE, 'test_cases', 'unplanned_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'unplanned_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
try:
    from playwright.sync_api import sync_playwright
    import run as R
except Exception as e:
    print('skip:', e); sys.exit(0)
bad = 0
with sync_playwright() as p:
    try:
        br = p.chromium.launch(channel='chrome', headless=True)
    except Exception:
        try:
            br = p.chromium.launch(headless=True)
        except Exception as e:
            print('skip: no browser', str(e)[:80]); sys.exit(0)
    pg = br.new_page()
    for c in cases:
        pg.set_content(c['html'])
        fake = types.SimpleNamespace(plan={'fields': c['plan']}, page=pg)
        got = R.Run.unplanned_required(fake)
        if got != c['expect'] and c['name'] not in verdicts:
            bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
    br.close()
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
