#!/usr/bin/env python3
"""Harness for canon.check('degree_level', …) (rule 13): DeepSeek cases, Claude's verdicts in degree_audit_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import canon
cases = json.load(open(os.path.join(HERE, 'test_cases', 'degree_audit_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'degree_audit_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = canon.check('degree_level', c['value'])[0]
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['value'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
