#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/dice_search.py helpers (rule 13): DeepSeek cases, verdicts in dice_search_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import dice_search as D
cases = json.load(open(os.path.join(HERE, 'test_cases', 'dice_search_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'dice_search_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f = c['fn']
    if f == 'alt_key':
        got = D.alt_key(c['title'])
    elif f == 'keep':
        got = D.keep(c['title'], c.get('location', ''))
    elif f == 'parse_cards':
        got = D.parse_cards(c['html'])
    else:
        ids, pairs = D.known(c.get('store', []))
        got = [x['guid'] for x in D.pick_new(c['cards'], ids, pairs)]
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
