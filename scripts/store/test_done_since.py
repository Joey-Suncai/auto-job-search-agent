#!/usr/bin/env python3
"""Harness for done_since.py (rule 13, JSA-126): DeepSeek cases, verdicts in test_cases/done_since_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
TC = os.path.join(HERE, '..', 'test_cases')
sys.path.insert(0, HERE)
import done_since as D  # noqa: E402
cases = json.load(open(os.path.join(TC, 'done_since_cases.json'), encoding='utf-8'))
vp = os.path.join(TC, 'done_since_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    if c['fn'] == 'entries':
        got = D.entries(c['rows'])
    elif c['fn'] == 'since':
        got = D.since(c['rows'], c['day'])
    else:
        got = D.new_since([tuple(e) for e in c['before']], c['rows'])
    exp = [tuple(e) for e in c['expect']]
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', exp)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
