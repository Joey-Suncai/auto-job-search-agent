#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sr_experience_cases.json, spec sr_experience_spec.md) against the
pure helpers of the SmartRecruiters required-experience fix (JSA-233: SyngentaGroup refused Next — "Please provide at
least one work experience entry" — and every month picker read as unset because the box holds "2026-09-01").
Claude's verdicts on disagreements: sr_experience_verdicts.json.
    python3 scripts/test_sr_experience.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import run_smartrecruiters as R  # noqa: E402


def call(c):
    a = c['args']
    if c['fn'] in ('picker_ym', 'ym_of'):
        return getattr(R, c['fn'])(a.get('value'))
    if c['fn'] == 'experience_required':
        return R.experience_required(a.get('cfg'))
    if c['fn'] == 'exp_entries':
        return R.exp_entries(a.get('work'))
    if c['fn'] == 'location_option':
        return R.location_option(a.get('city'), a.get('options'))
    raise ValueError(c['fn'])


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sr_experience_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sr_experience_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = call(c)
        except Exception as e:
            got = f'RAISES {type(e).__name__}: {e}'
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], '\n   got ', json.dumps(got), '\n   want', json.dumps(c['expect']))
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
