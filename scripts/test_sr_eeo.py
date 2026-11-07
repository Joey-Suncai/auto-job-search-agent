#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sr_eeo_cases.json) against run_smartrecruiters.plan_questions (EEO
blocks → gender / race lists) and OTHER_TEXT ("Other (free text)" follow-ups) — Bosch 2026-11-04. Verdicts in
sr_eeo_verdicts.json.
    python3 scripts/test_sr_eeo.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_smartrecruiters as R  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sr_eeo_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sr_eeo_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = R.plan_questions(c['args']['raw']) if c['fn'] == 'plan_questions' else bool(R.OTHER_TEXT.search(c['args']['label']))
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', json.dumps(got)[:250], 'want', json.dumps(c['expect'])[:250])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
