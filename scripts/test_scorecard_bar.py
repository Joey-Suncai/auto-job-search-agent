#!/usr/bin/env python3
"""Harness for platform_scorecard.bar_for (rule 13, 2026-11-02): DeepSeek cases, verdicts in scorecard_bar_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import platform_scorecard as P
cases = json.load(open(os.path.join(HERE, 'test_cases', 'scorecard_bar_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'scorecard_bar_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = P.bar_for(c['platform'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
