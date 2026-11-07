#!/usr/bin/env python3
"""Harness for run_form.Form.same on date fields (rule 13): DeepSeek cases, Claude's verdicts in date_readback_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_form
cases = json.load(open(os.path.join(HERE, 'test_cases', 'date_readback_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'date_readback_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = run_form.Form.same(None, {'type': 'date', 'label': 'Graduation Date', 'answer': c['want']}, c['got'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['want'], 'vs', c['got'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
