#!/usr/bin/env python3
"""Harness for wd_search.parse_tenant / keep_posting / job_key (rule 13): DeepSeek cases, verdicts in wd_search_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import wd_search as W
cases = json.load(open(os.path.join(HERE, 'test_cases', 'wd_search_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'wd_search_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    if c['fn'] == 'parse_tenant':
        r = W.parse_tenant(c['url']); got = list(r) if r else None
    elif c['fn'] == 'keep_posting':
        got = W.keep_posting(c['title'], c.get('location', ''))
    else:
        got = W.job_key(c['path'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], c['fn'], '| got', got, '| expect', c['expect'], '|', {k: c[k] for k in c if k not in ('name', 'fn', 'expect')})
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
