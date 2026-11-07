#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/board_feeds.py helpers (rule 13, JSA-139): DeepSeek cases
(test_cases/board_feeds_cases.json from board_feeds_spec.md), verdicts in board_feeds_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import board_feeds as B  # noqa: E402
raw = json.load(open(os.path.join(HERE, 'test_cases', 'board_feeds_cases.json')))
cases = raw['cases'] if isinstance(raw, dict) else raw
vp = os.path.join(HERE, 'test_cases', 'board_feeds_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f, a = c['fn'], c['args']
    if f == 'parse_yc':
        got = B.parse_yc(a['page'])
    elif f == 'parse_wwr':
        got = B.parse_wwr(a['xml'])
    elif f == 'known':
        ids, pairs = B.known(a['rows'])
        got = {'ids': sorted([list(x) for x in ids]), 'pairs_count': len(pairs)}
    else:
        ids, pairs = B.known(a.get('rows', []))
        got = [x['id'] for x in B.pick_new(a['cards'], ids, pairs)]
    if got == c['expect']:
        print('PASS ', c['name'])
    elif c['name'] in verdicts:
        print('CASE ', c['name'], '—', verdicts[c['name']]['why'])
    else:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
