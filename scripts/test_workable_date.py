#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/workable_date_cases.json, spec workable_date_spec.md) against
run_workable.parse_date / to_mask / same_date (JSA-234: the react-datepicker box takes its placeholder's format).
Claude's verdicts on disagreements in workable_date_verdicts.json ('case' = the case is wrong).
    python3 scripts/test_workable_date.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_workable as W  # noqa: E402


def call(c):
    a = c['args']
    if c['fn'] == 'parse_date':
        r = W.parse_date(a['s']); return list(r) if r else None
    if c['fn'] == 'to_mask':
        return W.to_mask(a['value'], a.get('placeholder'))
    return W.same_date(a['want'], a['got'])


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'workable_date_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'workable_date_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = call(c)
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got), 'want', repr(c['expect']))
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
