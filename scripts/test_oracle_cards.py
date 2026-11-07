#!/usr/bin/env python3
"""DeepSeek cases (scripts/test_cases/oracle_cards_cases.json) for run_oracle.edu_fill / submit_refused (JSA-147).
Verdicts in oracle_cards_verdicts.json.    python3 scripts/test_oracle_cards.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_oracle as O  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'oracle_cards_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
_pp = json.load(open(os.path.join(HERE, 'test_cases', 'oracle_profile_cases.json')))   # My Profile page (Ricoh 11-04)
cases += _pp['cases'] if isinstance(_pp, dict) else _pp
vp = os.path.join(HERE, 'test_cases', 'oracle_cards_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    a = c['args']
    f = c['fn']
    got = (O.edu_fill(a.get('school'), a.get('education'), a.get('today')) if f == 'edu_fill' else O.submit_refused(a.get('text')) if f == 'submit_refused'
           else O.classify(a.get('url'), a.get('text')) if f == 'classify' else O.profile_lists(a.get('text'), a.get('job_id'), a.get('title')))
    want = c['expect']
    if c['fn'] == 'submit_refused' and isinstance(want, str) and want and got:   # the matched words: compare case/space-insensitively
        ok = ' '.join(got.lower().split()) == ' '.join(want.lower().split())
    else:
        ok = got == want
    if ok:
        print('PASS ', c['name']); continue
    if (verdicts.get(c['name']) or {}).get('verdict') == 'case':
        print('CASE ', c['name'], '—', verdicts[c['name']]['why']); continue
    bad += 1; print('FAIL ', c['name'], '\n   got ', repr(got), '\n   want', repr(want))
print(f'{len(cases) - bad}/{len(cases)} ok'); sys.exit(1 if bad else 0)
