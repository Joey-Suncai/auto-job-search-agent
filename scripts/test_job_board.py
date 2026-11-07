#!/usr/bin/env python3
"""Harness for skills/auto-apply/runner/job_board.py (rule 13): DeepSeek cases, verdicts in test_cases/job_board_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import job_board as J  # noqa: E402
cases = [c for f in ('job_board_cases.json', 'job_board_b_cases.json') for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]
vp = os.path.join(HERE, 'test_cases', 'job_board_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = getattr(J, c['fn'])(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '| args', json.dumps(c['args']))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
