#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/smartrecruiters_cases.json) against run_smartrecruiters'
pure helpers (JSA-112): parse_posting, clean_label, plan_questions, IF_OTHER. Verdicts in smartrecruiters_verdicts.json.
    python3 scripts/test_smartrecruiters.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_smartrecruiters as R  # noqa: E402


def call(c):
    a = c['args']
    if c['fn'] == 'parse_posting':
        return R.parse_posting(a['url'])
    if c['fn'] == 'clean_label':
        return R.clean_label(a['text'])
    if c['fn'] == 'plan_questions':
        return R.plan_questions(a['raw'])
    return bool(R.IF_OTHER.search(a['label']))


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'smartrecruiters_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'smartrecruiters_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = call(c)
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', json.dumps(got)[:300], 'want', json.dumps(c['expect'])[:300])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
