#!/usr/bin/env python3
"""Harness for field_limits.fix_url (JSA-312, rule 13): DeepSeek cases in test_cases/fix_url_cases.json (from
fix_url_spec.md), Claude's verdicts in fix_url_verdicts.json. wants_url is given to the function as a url format."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import field_limits as FL
cases = json.load(open(os.path.join(HERE, 'test_cases', 'fix_url_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'fix_url_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = FL.fix_url(c['value'], {'format': 'url'} if c['wants_url'] else None, 'Describe it', 'text')
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', repr(got), '| expect', repr(c['expect']))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
