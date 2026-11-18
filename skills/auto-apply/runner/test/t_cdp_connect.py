#!/usr/bin/env python3
"""DeepSeek-written cases (scripts/test_cases/cdp_connect_cases.json, from cdp_connect_spec.md) against
cdp_connect.ensure_tab; disagreements are judged in cdp_connect_verdicts.json (JSA-386). Plus a connect() wiring test."""
import json, os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..'))
import cdp_connect as C  # noqa: E402

CASES = os.path.join(ROOT, 'scripts', 'test_cases')


def run(case):
    reqs = []

    def http(method, url):
        reqs.append([method, url])
        if method == 'GET':
            if case['list_result'] == 'unreachable': raise OSError('refused')
            return case['list_result']
        if case.get('new_result') == 'unreachable': raise OSError('refused')
        return {'type': 'page'}
    return C.ensure_tab(case['cdp'], http), reqs


def main():
    cases = json.load(open(os.path.join(CASES, 'cdp_connect_cases.json')))
    vp = os.path.join(CASES, 'cdp_connect_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = run(c); want = (c['expect_return'], [list(r) for r in c['expect_requests']])
        if got == want: print('PASS', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case': print('CASE', c['name'], '—', v['why'][:100]); continue
        bad += 1; print('DIFF', c['name'], '| want', want, '| got', got)
    # connect(): the tab is ensured before Playwright connects; the browser comes back unchanged
    order = []
    C.ensure_tab_hook = None
    orig = C.ensure_tab; C.ensure_tab = lambda cdp, http=None: order.append('tab') or False
    pw = types.SimpleNamespace(chromium=types.SimpleNamespace(connect_over_cdp=lambda cdp, **k: order.append('connect') or 'BR'))
    r = C.connect(pw, 'http://127.0.0.1:9222'); C.ensure_tab = orig
    if (r, order) != ('BR', ['tab', 'connect']): bad += 1; print('DIFF connect_order', r, order)
    print(f'{len(cases) + 1} cases, {bad} unresolved')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
