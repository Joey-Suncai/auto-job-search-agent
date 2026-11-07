#!/usr/bin/env python3
"""Harness for h1b_match (norm / lookup / group_key) and fix_company_h1b (refresh / merge) — rule 13, JSA-098.
DeepSeek cases in test_cases/h1b_match_cases.json (+ h1b_names_cases.json, the JSA-103 name tables); verdicts (why a
case misreads the spec) in h1b_match_verdicts.json / h1b_names_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
sys.path.insert(0, os.path.join(HERE, 'store'))
import h1b_match as M
import fix_company_h1b as F
cases, verdicts = [], {}
for f in ('h1b_match', 'h1b_names'):
    cases += json.load(open(os.path.join(HERE, 'test_cases', f'{f}_cases.json')))
    vp = os.path.join(HERE, 'test_cases', f'{f}_verdicts.json')
    verdicts.update(json.load(open(vp)) if os.path.exists(vp) else {})


def lookup(records, company):
    h = M.H1B(records).lookup(company)
    return {'fy25': h['fy25'], 'total': h['total'], 'first': h['first'], 'names': sorted(h['names'])}


bad = 0
for c in cases:
    i, e = c['input'], c['expect']
    if c['fn'] == 'norm':
        got = {'key': M.norm(i['name'])}
    elif c['fn'] == 'lookup':
        got = lookup(i['records'], i['company']); e = dict(e, names=sorted(e.get('names') or []))
    elif c['fn'] == 'group_key':
        got = {'same': M.group_key(i['a']) == M.group_key(i['b'])}
    elif c['fn'] == 'refresh':
        f = i['facts']
        got = {'row': F.refresh(i['row'], {'fy25': f.get('fy25'), 'total': f.get('total'), 'first': f.get('first')})}
    else:
        rows, merged = F.merge_companies(i['rows'], M.H1B(i['records']))
        fields = set().union(*[r.keys() for r in i['rows']])
        got = {'rows': sorted([{k: r.get(k) for k in fields if k in r} for r in rows], key=lambda r: r['company']),
               'merged': {k: sorted(v) for k, v in merged.items()}}
        e = {'rows': sorted([{k: r.get(k) for k in fields if k in r} for r in e['rows']], key=lambda r: r['company']),
             'merged': {k: sorted(v) for k, v in (e.get('merged') or {}).items()}}
    if got != e and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['fn'], c['name'], '\n  got   ', got, '\n  expect', e)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
