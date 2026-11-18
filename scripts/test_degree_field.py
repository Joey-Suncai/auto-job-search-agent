#!/usr/bin/env python3
"""Harness for run_wd.master_options / bachelor_options + canon.degree_field_ok (rule 13, JSA-282): DeepSeek cases from
degree_field_spec.md, Claude's verdicts on disagreements in degree_field_verdicts.json, plus the real Vanguard list."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_wd
cases = json.load(open(os.path.join(HERE, 'test_cases', 'degree_field_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'degree_field_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases.append({'name': 'real_vanguard_2026_11_10', 'fn': 'master_options',
              'options': ['M.A. - Master of Arts', 'M.S.T. - Master of Science in Taxation', 'M.S. - Master of Science'],
              'expect': ['M.S. - Master of Science', 'M.A. - Master of Arts']})
bad = 0
for c in cases:
    got = getattr(run_wd, c['fn'])(c['options'])
    want = verdicts.get(c['name'], {}).get('expect', c['expect'])
    if got != want:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', want)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
