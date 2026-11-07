#!/usr/bin/env python3
"""Harness for run_wd.block_kind_of (rule 13): DeepSeek cases, Claude's verdicts in block_kind_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_wd
cases = json.load(open(os.path.join(HERE, 'test_cases', 'block_kind_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'block_kind_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
w = run_wd.WD.__new__(run_wd.WD)
bad = 0
for c in cases:
    got = run_wd.block_kind_of(c['section'])
    if got != w.block_kind(c['section']): print('MISMATCH method vs function', c['section'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['section'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
