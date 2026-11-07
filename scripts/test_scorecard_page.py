#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/scorecard_page_cases.json) against platform_scorecard.page_proof
(Joey 2026-11-04: the confirmation page counts as proof of receipt), plus one score() check that e-mail wins over page and
neither is counted twice. Verdicts in scorecard_page_verdicts.json.
    python3 scripts/test_scorecard_page.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import platform_scorecard as P  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'scorecard_page_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'scorecard_page_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = P.page_proof(c['args']['line'], c['args']['shot'])
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got), 'want', repr(c['expect']))
    f1, f2, f3 = '2026-11-01_A_x', '2026-11-01_B_y', '2026-11-01_C_z'
    res = [{'folder': f, 'at': '2026-11-01T10:00:00', 'ats': 'ashby', 'status': 'submitted', 'by': 'runner'} for f in (f1, f2, f3)]
    em = [{'job_id': 'J1', 'type': 'Confirmation', 'date': '2026-11-01'}]
    sc = P.score(res, em, {f1: 'J1', f2: 'J2', f3: 'J3'}, {}, [], '2026-11-10', frozenset({f1, f2}))['ashby']
    want = dict(confirmed=2, by_email=1, by_page=1, pending=0)
    got = {k: sc[k] for k in want}
    if got == want:
        print('PASS  score: e-mail wins over page, a submit without either is missing')
    else:
        bad += 1; print('FAIL  score', got, 'want', want)
    print(f'{len(cases) + 1 - bad}/{len(cases) + 1} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
