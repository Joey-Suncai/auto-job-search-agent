#!/usr/bin/env python3
"""Harness for ds_materials.fill_candidates (rule 13, JSA-063): DeepSeek cases, verdicts in fill_candidates_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts'))
import ds_materials as D
cases = json.load(open(os.path.join(HERE, 'test_cases', 'fill_candidates_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'fill_candidates_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    i = c['input']
    got = [list(x) for x in D.fill_candidates(i['selection'], i['base'], i['bank'], i['pool'], i['jd'])]
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '\n  got   ', got, '\n  expect', c['expect'])
# add_fill: bullet goes to the end of its entry, skill line before the last (Languages) line; input not mutated
rs = {'exp': {'HP': ['HP01']}, 'projects': {'JSA': ['JSA02']}, 'skill_lines': ['SK1', 'SK6']}
r2 = D.add_fill(rs, ('bullet', 'JSA', 'JSA08')); r3 = D.add_fill(r2, ('skill', None, 'SK5'))
if r3['projects']['JSA'] != ['JSA02', 'JSA08'] or r3['skill_lines'] != ['SK1', 'SK5', 'SK6'] or rs['projects']['JSA'] != ['JSA02']:
    bad += 1; print('add_fill wrong', r3, rs)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
