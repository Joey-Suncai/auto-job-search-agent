#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/builtin_search.py helpers (rule 13): DeepSeek cases, verdicts in builtin_search_verdicts.json."""
import json, os, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import builtin_search as B
TODAY = dt.date(2026, 11, 1)
cases = json.load(open(os.path.join(HERE, 'test_cases', 'builtin_search_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'builtin_search_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f, a = c['fn'], c['args']
    exp = c['expect']
    if f == 'job_id':
        got = B.job_id(a.get('url'))
    elif f == 'parse_card':
        got = B.parse_card(a['rec'], TODAY)
    elif f == 'known':
        ids, pairs = B.known(a['rows'])
        got = {'ids': sorted(ids), 'pairs': sorted([list(p) for p in pairs])}
        exp = {'ids': sorted(exp.get('ids') or []), 'pairs': sorted([list(p) for p in exp.get('pairs') or []])}
    else:
        got = [x['job_id'] for x in B.pick_new(a['cards'], set(a.get('ids') or []), {tuple(p) for p in a.get('pairs') or []})]
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got, ensure_ascii=False), '| expect', json.dumps(exp, ensure_ascii=False), '| args', json.dumps(a, ensure_ascii=False)[:500])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
