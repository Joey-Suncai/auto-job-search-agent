#!/usr/bin/env python3
"""run_oracle.EXTRACT numbers only the visible rows, and an earlier section's numbers do not survive (JSA-174, Goldman
2026-11-05: section 1's hidden row kept data-ox="6", so section 2's field 6 was looked up on the hidden row and timed out).
Headless Chromium on a static page; no network.   ~/.job-agent-venv/bin/python skills/auto-apply/runner/test/t_oracle_extract.py"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
try:
    import run_oracle as R  # noqa: E402
    from playwright.sync_api import sync_playwright  # noqa: E402
except ImportError as e:                                       # CI / a python without Playwright: nothing to test here
    print(f'skip t_oracle_extract ({e})'); sys.exit(0)

ROW = '<div class="input-row input-row--text"><label class="input-row__label">{l}</label><input class="input-row__control" type="text"></div>'
PAGE = ('<html><body><div id="s1" class="apply-flow-block apply-flow-block--contact">' + ''.join(ROW.format(l=f'S1 field {i}') for i in range(8)) +
        '</div><div id="s2" class="apply-flow-block apply-flow-block--questions" style="display:none">' +
        ''.join(ROW.format(l=f'S2 field {i}') for i in range(8)) + '</div></body></html>')
bad = 0
with sync_playwright() as p:
    try:
        b = p.chromium.launch(headless=True, channel='chrome')   # the installed Chrome (no bundled Chromium here); never the job Chrome
    except Exception as e:
        try:
            b = p.chromium.launch(headless=True)
        except Exception:
            print(f'skip t_oracle_extract (no Chrome / Chromium: {type(e).__name__})'); sys.exit(0)
    pg = b.new_page(); pg.set_content(PAGE)
    st1 = pg.evaluate(R.EXTRACT)
    pg.evaluate("() => { document.getElementById('s1').style.display = 'none'; document.getElementById('s2').style.display = 'block'; }")
    st2 = pg.evaluate(R.EXTRACT)
    f1 = st1['fields'] if isinstance(st1, dict) else st1
    f2 = st2['fields'] if isinstance(st2, dict) else st2
    labels = [f['label'] for f in f2]
    if labels != [f'S2 field {i}' for i in range(8)]:
        bad += 1; print('FAIL section 2 labels', labels)
    for i in range(8):
        loc = pg.locator(f'[data-ox="{i}"]')
        if loc.count() != 1 or not loc.first.is_visible() or loc.first.inner_text().strip() != f'S2 field {i}':
            bad += 1; print('FAIL data-ox', i, 'count', loc.count())
        else:
            loc.locator('input.input-row__control').click(timeout=3000)   # the click that timed out on the hidden row
    b.close()
print('ALL PASS' if not bad else f'{bad} FAILED'); sys.exit(1 if bad else 0)
