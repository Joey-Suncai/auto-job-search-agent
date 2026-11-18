#!/usr/bin/env python3
"""JSA-328 (Dell 11-11, Joey 「自动添加 + dry-run 检查」): run_oracle adds the profile's education entries to a required,
empty Education list. DeepSeek-written cases (rule 13) for school_pick / major_pick / degree_pill / empty_required_lists:
test_cases/oracle_add_edu_cases.json; judged disagreements in oracle_add_edu_verdicts.json. Plus the Dell lists."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_oracle as RO  # noqa: E402
C = json.load(open(os.path.join(HERE, 'test_cases', 'oracle_add_edu_cases.json')))
C = C.get('cases', C) if isinstance(C, dict) else C
vp = os.path.join(HERE, 'test_cases', 'oracle_add_edu_verdicts.json')
V = json.load(open(vp)) if os.path.exists(vp) else {}
fails = 0
for i, c in enumerate(C):
    fn = c['fn']
    if fn == 'school_pick': got = RO.school_pick(c['want'], c['options'], c.get('alts') or [])
    elif fn == 'major_pick': got = RO.major_pick(c['major'], c.get('prefs') or [], c['options'])
    elif fn == 'degree_pill': got = RO.degree_pill(c['level'], c['pills'])
    else: got = RO.empty_required_lists(c['blocks'])
    if got != c['expect']:
        if str(i) in V: print(f'JUDGED {i}: {V[str(i)]}')
        else: fails += 1; print(f'FAIL {i} {fn}: got {got!r} want {c["expect"]!r} — {json.dumps(c)[:200]}')
DELL_SCHOOLS = ['University of Illinois at Chicago', 'University of Illinois at Springfield',
                'University of Illinois at Urbana-Champaign', 'University of Illinois University Administration']
fx = [(RO.school_pick('University of Illinois Urbana-Champaign', DELL_SCHOOLS), 'University of Illinois at Urbana-Champaign'),
      (RO.major_pick('Applied Data Science', ['Data Science', 'Applied Data Science'], ['Data Analytics', 'Data Processing', 'Data Science']), 'Data Science'),
      (RO.degree_pill('master', ['Associates', 'Bachelors', 'Doctorate', 'Masters', 'Postdoctorate']), 'Masters'),
      (RO.empty_required_lists([{'title': 'Education', 'required': True, 'items': 0, 'add': 'ADD EDUCATION'},
                                {'title': 'Licenses and Certificates', 'required': False, 'items': 0}]), ['Education'])]
for got, want in fx:
    if got != want: fails += 1; print(f'FAIL Dell fixture: got {got!r} want {want!r}')
print(f'oracle add education: {len(C)} DeepSeek cases + {len(fx)} Dell fixtures, fails {fails}')
sys.exit(1 if fails else 0)
