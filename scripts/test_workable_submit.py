#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/workable_submit_cases.json) against run_workable.confirmed_page and
run_form.posting_key for Workable URLs (JSA-146). Verdicts in workable_submit_verdicts.json.
    python3 scripts/test_workable_submit.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_form as RF  # noqa: E402
import run_workable as W  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'workable_submit_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'workable_submit_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        a = c['args']
        got = W.confirmed_page(a.get('url', ''), a.get('text', '')) if c['fn'] == 'confirmed_page' else RF.posting_key(a['url'])
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got), 'want', repr(c['expect']))
    ad = json.load(open(os.path.join(HERE, 'test_cases', 'workable_address_cases.json')))   # full_address (same JSA)
    for c in (ad['cases'] if isinstance(ad, dict) else ad):
        a = c['args']; cases.append(c)
        got = (W.full_address(a['fields'], a['ans'], a['city_state_zip']).get('address') or {}).get('value')
        if got == c['expect_address_value']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got), 'want', repr(c['expect_address_value']))
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
