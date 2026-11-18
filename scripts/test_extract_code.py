#!/usr/bin/env python3
"""Harness for gmail_code.extract_code (rule 13): DeepSeek cases, Claude's verdicts in extract_code_verdicts.json.
extract_code_cases.json = JSA-297 (dates / 19-20 codes); extract_code_letters_cases.json = JSA-304 (code block,
letters-only codes, expected length n) + the real Greenhouse bodies from the 2026-11-11 Gmail replay."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import gmail_code
cases = []
for f in ('extract_code_cases.json', 'extract_code_letters_cases.json'):
    cases += json.load(open(os.path.join(HERE, 'test_cases', f)))
vp = os.path.join(HERE, 'test_cases', 'extract_code_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = gmail_code.extract_code(c['text'], c.get('n'))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
