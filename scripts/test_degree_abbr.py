#!/usr/bin/env python3
"""Harness for canon.check('degree_level') with an abbreviation prefix (rule 13, JSA-282): DeepSeek cases from
degree_abbr_spec.md, Claude's verdicts on disagreements in degree_abbr_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import canon
cases = json.load(open(os.path.join(HERE, 'test_cases', 'degree_abbr_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'degree_abbr_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases.append({'name': 'real_vanguard_2026_11_10', 'value': 'B.A. - Bachelor of Arts', 'expect': True})
bad = 0
for c in cases:
    got = canon.check('degree_level', c['value'])[0]
    want = verdicts.get(c['name'], {}).get('expect', c['expect'])
    if got != want:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', want, '|', c['value'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
