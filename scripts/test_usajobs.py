#!/usr/bin/env python3
"""Harness for usajobs_search.py + eligibility_fetch.usajobs_jd (rule 13): DeepSeek cases, verdicts in test_cases/usajobs_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import usajobs_search as U, eligibility_fetch as E  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'usajobs_cases.json'))) + [dict(c, fn='runs_for') for c in json.load(open(os.path.join(HERE, 'test_cases', 'usajobs_runs_cases.json')))]
vp = os.path.join(HERE, 'test_cases', 'usajobs_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f, a = c['fn'], c['args']
    if f == 'known':
        ids, pairs = U.known(*a); got = [sorted(ids), sorted([list(p) for p in pairs])]
        exp = c['expect']; exp = [sorted(exp[0]), sorted([list(p) for p in exp[1]])] if isinstance(exp, list) and len(exp) == 2 else exp
    elif f == 'pick_new':
        got = U.pick_new(a[0], set(a[1]), {tuple(p) for p in a[2]}, a[3]); exp = c['expect']
    else:
        got = (E.usajobs_jd if f == 'usajobs_jd' else getattr(U, f))(*a); exp = c['expect']
    got = json.loads(json.dumps(got))
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], f, '| got', json.dumps(got)[:260], '| expect', json.dumps(exp)[:260])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
