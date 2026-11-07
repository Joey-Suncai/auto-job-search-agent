#!/usr/bin/env python3
"""Harness for run_form.plan_changes (rule 13, JSA-213): DeepSeek cases, Claude's verdicts in plan_changes_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_form
cases = json.load(open(os.path.join(HERE, 'test_cases', 'plan_changes_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'plan_changes_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    try:
        got = run_form.plan_changes(c['old'], c['new'])
    except Exception as e:
        got = f'ERROR {e!r}'
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
