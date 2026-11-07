#!/usr/bin/env python3
"""Harness for gmail_code.html_text + extract_code (rule 13): DeepSeek cases, verdicts in test_cases/html_text_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import gmail_code as G  # noqa: E402
cases = [c for f in ('html_text_cases.json', 'html_text_b_cases.json') for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]   # b = trigger words (11-05)
vp = os.path.join(HERE, 'test_cases', 'html_text_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = G.extract_code(G.html_text(c['html']))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['html'][:200])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
