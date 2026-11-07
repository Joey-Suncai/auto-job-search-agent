#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/wellfound_search.py helpers (rule 13): DeepSeek cases, verdicts in wellfound_search_verdicts.json."""
import json, os, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import wellfound_search as W
TODAY = dt.date(2026, 11, 3)
cases = [c for f in ('wellfound_search_cases.json', 'wellfound_search_b_cases.json')
         for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]
vp = os.path.join(HERE, 'test_cases', 'wellfound_search_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f, a = c['fn'], c['args']
    if f == 'job_id':
        got = W.job_id(a.get('href'))
    elif f == 'posted_date':
        got = W.posted_date(a.get('text'), TODAY)
    elif f == 'parse_card':
        got = W.parse_card(a['rec'], TODAY)
    else:
        got = [x['job_id'] for x in W.pick_new(a['cards'], set(a.get('ids') or []), {tuple(p) for p in a.get('pairs') or []})]
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got, ensure_ascii=False), '| expect', json.dumps(c['expect'], ensure_ascii=False), '| args', json.dumps(a, ensure_ascii=False)[:400])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
