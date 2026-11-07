#!/usr/bin/env python3
"""Harness for run_oracle.py pure helpers (rule 13, JSA-048; conditional boxes JSA-174): DeepSeek cases, verdicts in test_cases/oracle_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_oracle as R  # noqa: E402
cases = [c for f in ('oracle_cases.json', 'oracle_b_cases.json', 'oracle_cond_cases.json') for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]
vp = os.path.join(HERE, 'test_cases', 'oracle_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    try:
        got = getattr(R, c['fn'])(*c['args'])
    except Exception as e:
        got = f'ERROR {type(e).__name__}: {e}'
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], c['fn'], '| got', json.dumps(got)[:150], '| expect', json.dumps(c['expect'])[:150], '| args', json.dumps(c['args'])[:250])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
