#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/oracle_1105_cases.json, spec oracle_1105_spec.md) against
run_oracle.related_question (upload rows without a key — the KeyError of OSTMORFEN / BraRoskel / Fensevpell 11-05), email_value_ok
(OSTMORFEN's emptied e-mail box) and needs_retry (Harmorquin's lost radio click), JSA-220. Then a headless page: next_button picks
the pagination Next, not the hidden legal-disclaimer dialog's footer Next that comes first (Harmorquin fa-ewgu 11-05).
Verdicts in oracle_1105_verdicts.json.
    ~/.job-agent-venv/bin/python scripts/test_oracle_1105.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import run_oracle as R  # noqa: E402


def run_case(c):
    a = c['args']
    try:
        if c['fn'] == 'related_question':
            f = next((x for x in a['order'] if x.get('key') == a['f_key']), {'key': a['f_key'], 'kind': 'text', 'label': '', 'value': ''})
            return R.related_question(a['order'], f, a['rows'])
        if c['fn'] == 'email_value_ok':
            return R.email_value_ok(a['value'], a['email'])
        f = dict(a['f']); f.setdefault('options', [])
        return R.needs_retry(a['row'], f)
    except Exception as e:
        return f'RAISES {type(e).__name__}: {e}'


def page_check():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f'skip page check ({e})'); return 0
    html = ('<html><body><div class="app-dialog" style="display:none"><button class="button app-dialog__footer-button">'
            '<span>Next</span></button></div><input type="email"><div class="apply-flow-pagination">'
            '<button class="button apply-flow-pagination__button" onclick="document.body.dataset.ok=1"><span>Next</span></button>'
            '</div></body></html>')
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel='chrome')   # the installed Chrome; never the job Chrome
        except Exception:
            b = p.chromium.launch(headless=True)
        pg = b.new_page(); pg.set_content(html)
        R.next_button(pg).click(timeout=3000)
        ok = pg.evaluate('document.body.dataset.ok') == '1'
        b.close()
    print(('PASS ' if ok else 'FAIL ') + 'next_button: pagination Next, not the hidden dialog Next')
    return 0 if ok else 1


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'oracle_1105_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'oracle_1105_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = run_case(c)
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', json.dumps(got, default=str)[:300], 'want', json.dumps(c['expect'])[:300])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if (bad or page_check()) else 0


if __name__ == '__main__':
    sys.exit(main())
