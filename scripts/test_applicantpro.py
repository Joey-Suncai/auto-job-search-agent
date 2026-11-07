#!/usr/bin/env python3
"""DeepSeek cases (scripts/test_cases/ats_search_g_cases.json) for ApplicantPro detection / parsing (JSA-149)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import ats_search as A  # noqa: E402
import resolve_careers as RC  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'ats_search_g_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'ats_search_g_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    a = c['args']
    if c['fn'] == 'detect':
        got = [[s, i] for s, i in RC.detect_ats(a['text']) if s == 'applicantpro']
    elif c['fn'] == 'site_id':
        got = A.applicantpro_site_id(a['page'])
    else:
        got = [dict(p) for p in A.parse_applicantpro('', a.get('data'), a['host'])]
    if got == c['expect']:
        print('PASS ', c['name']); continue
    if (verdicts.get(c['name']) or {}).get('verdict') == 'case':
        print('CASE ', c['name'], '—', verdicts[c['name']]['why']); continue
    bad += 1; print('FAIL ', c['name'], '\n   got ', got, '\n   want', c['expect'])
print(f'{len(cases) - bad}/{len(cases)} ok'); sys.exit(1 if bad else 0)
