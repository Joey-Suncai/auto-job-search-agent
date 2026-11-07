#!/usr/bin/env python3
"""Harness for prefilter.start_patterns (rule 13, JSA-087): DeepSeek cases, verdicts in prefilter_start_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts'))
import prefilter as P
cases = json.load(open(os.path.join(HERE, 'test_cases', 'prefilter_start_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'prefilter_start_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    intern, ft = P.start_patterns(c['intern_summer'], c['fulltime_from'])
    got = bool((intern if 'intern' in c['level'].lower() else ft).search(c['text']))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['level'], c['intern_summer'], c['fulltime_from'], repr(c['text']))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
