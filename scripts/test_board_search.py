#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/board_search.py helpers (rule 13): DeepSeek cases, verdicts in board_search_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import board_search as B
cases = json.load(open(os.path.join(HERE, 'test_cases', 'board_search_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'board_search_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f = c['fn']
    got = B.parse_board(c['url']) if f == 'parse_board' else B.posting_id(c['url']) if f == 'posting_id' else B.keep_posting(c['title'], c['location'])
    if isinstance(got, tuple): got = list(got)
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c.get('url') or (c.get('title'), c.get('location')))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
