#!/usr/bin/env python3
"""Harness for score_v2.sponsor_factor / label_blocks (rule 13): DeepSeek cases, verdicts in test_cases/sponsor_profile_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_v2 as S  # noqa: E402
TC = os.path.join(HERE, '..', 'test_cases')
cases = json.load(open(os.path.join(TC, 'sponsor_profile_cases.json')))
vp = os.path.join(TC, 'sponsor_profile_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = getattr(S, c['fn'])(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['args'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
