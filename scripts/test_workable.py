#!/usr/bin/env python3
"""Harness for run_workable.py pure helpers (rule 13, JSA-122): DeepSeek cases, verdicts in test_cases/workable_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_workable as W  # noqa: E402
cases = [c for f in ('workable_cases.json', 'workable_b_cases.json') for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]
vp = os.path.join(HERE, 'test_cases', 'workable_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = getattr(W, c['fn'])(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got)[:300], '| expect', json.dumps(c['expect'])[:300])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
