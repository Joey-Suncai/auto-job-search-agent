#!/usr/bin/env python3
"""Harness for email_check.pick_same_company (rule 13): DeepSeek cases, Claude's verdicts in same_company_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'daily'), os.path.join(HERE, 'store')]
import email_check
cases = json.load(open(os.path.join(HERE, 'test_cases', 'same_company_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'same_company_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    r = email_check.pick_same_company(c['ids'], c['apps'], c['emails'], c['kind'])
    got = r and r['job_id']
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', json.dumps({k: c[k] for k in ('ids', 'apps', 'emails', 'kind')})[:400])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
