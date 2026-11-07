#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/linkedin_search.py helpers (rule 13): DeepSeek cases, verdicts in linkedin_search_verdicts.json."""
import json, os, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import linkedin_search as L
TODAY = dt.date(2026, 11, 1)
cases = json.load(open(os.path.join(HERE, 'test_cases', 'linkedin_search_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'linkedin_search_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f, a = c['fn'], c['args']
    if f == 'rel_date':
        got = L.rel_date(a.get('text'), TODAY)
    elif f == 'job_id':
        got = L.job_id(a.get('url'))
    elif f == 'parse_card':
        got = L.parse_card(a['rec'], TODAY)
    elif f == 'company_tiers':
        got = L.company_tiers(a['rows'])
    else:
        got = [x['job_id'] for x in L.pick_new(a['cards'], set(a.get('ids') or []), {tuple(p) for p in a.get('pairs') or []})]
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got, ensure_ascii=False), '| expect', json.dumps(c['expect'], ensure_ascii=False), '| args', json.dumps(a, ensure_ascii=False)[:500])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
