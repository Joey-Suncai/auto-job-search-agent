#!/usr/bin/env python3
"""Harness for wd_signin.choose_password (rule 13): DeepSeek cases (fake passwords), verdicts in choose_password_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import wd_signin
cases = json.load(open(os.path.join(HERE, 'test_cases', 'choose_password_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'choose_password_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    r = wd_signin.choose_password(c['page_text'], c['pw'], c['long_pw'])
    got = 'long' if (c['long_pw'] and r == c['long_pw'] and r != c['pw']) else 'regular'
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['page_text'][:100], len(c['pw']), len(c['long_pw']))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
