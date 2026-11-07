#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/indeed_search.py helpers (rule 13): DeepSeek cases, verdicts in indeed_search_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import indeed_search as I
cases = json.load(open(os.path.join(HERE, 'test_cases', 'indeed_search_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'indeed_search_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f = c['fn']
    got = (I.keep_card(c['title'], c.get('location', '')) if f == 'keep_card' else I.level_of(c['title']) if f == 'level_of'
           else I.title_key(c['title']))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['title'], '|', c.get('location', ''))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
