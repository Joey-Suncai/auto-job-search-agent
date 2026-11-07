#!/usr/bin/env python3
"""Harness for gmail_code.imap_since (rule 13): DeepSeek cases, verdicts in test_cases/imap_since_verdicts.json."""
import json, os, sys
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import gmail_code as G  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'imap_since_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'imap_since_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = G.imap_since(datetime.fromisoformat(c['since'].replace('Z', '+00:00')))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['since'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
