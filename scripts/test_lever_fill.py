#!/usr/bin/env python3
"""Harness for lever_fill/server.payload (rule 13): DeepSeek cases, Claude's verdicts in lever_fill_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'lever_fill'))
import server
cases = json.load(open(os.path.join(HERE, 'test_cases', 'lever_fill_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'lever_fill_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = list(server.payload(c['plan'], c.get('check'), c.get('submitted')))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '\n  got   ', got, '\n  expect', c['expect'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
