#!/usr/bin/env python3
"""Harness for board_search.known / pick_new / to_rows (rule 13, JSA-076): DeepSeek cases, verdicts in board_pick_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import board_search as B
cases = json.load(open(os.path.join(HERE, 'test_cases', 'board_pick_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'board_pick_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
F = ('id', 'score', 'tier', 'source', 'track', 'added', 'ats_url')
bad = 0
for c in cases:
    i = c['input']
    if c['fn'] == 'known':
        k, b, ab = B.known(i['rows'])
        got = {'keys': sorted(k), 'boards': sorted([[x, y, v] for (x, y), v in b.items()]), 'ab': sorted(ab)}
        exp = dict(c['expect'], keys=sorted(c['expect']['keys']), boards=sorted(c['expect']['boards']), ab=sorted(c['expect']['ab']))
    elif c['fn'] == 'pick_new':
        res = [(((r[0][0], r[0][1]), r[1]), r[2]) for r in i['results']]
        out = B.pick_new(set(i['keys']), set(i['ab']), res)
        got, exp = {'ids': [p['id'] for p in out], 'tiers': [p['tier'] for p in out]}, c['expect']
    else:
        got = {'rows': [{f: r[f] for f in F} for r in B.to_rows(i['new'], i['rows'], i['today'])]}
        exp = {'rows': [{f: r.get(f) for f in F} for r in c['expect']['rows']]}
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['fn'], c['name'], '\n  got   ', got, '\n  expect', exp)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
