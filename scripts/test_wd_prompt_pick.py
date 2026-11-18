#!/usr/bin/env python3
"""JSA-283: Workday prompt lists — run_wd.prompt_queries (search texts tried) and run_wd.pick_by_prefs (closest option).
DeepSeek-written cases: scripts/test_cases/wd_prompt_pick_cases.json; verdicts for cases judged wrong: wd_prompt_pick_verdicts.json.
    python3 scripts/test_wd_prompt_pick.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_wd  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'wd_prompt_pick_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'wd_prompt_pick_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
def T(name, ok, info=''):
    global bad
    v = verdicts.get(name)
    if not ok and v and v.get('verdict') == 'case':
        print(f'SKIP {name}  (case judged wrong: {v["why"][:80]})'); return
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}')); bad += not ok

for c in cases:
    got = run_wd.prompt_queries(c['want']) if c['fn'] == 'prompt_queries' else run_wd.pick_by_prefs(c['opts'], c['prefs'])
    T(c['name'], got == c['expect'], f"got {got!r} want {c['expect']!r}")

# the real Vanguard Field of Study list (run_log 2026-11-10): Joey 2026-11-08 → Computer and Information Science, not the business category
VG = ['Accounting', 'Actuarial Science', 'Computer Engineering', 'Computer Graphics', 'Computer Sciences, Technology, or Business',
      'Computer Systems Analysis', 'Computer and Information Science', 'Management Information Systems', 'Statistics']
PREFS = ['Data Science', 'Applied Data Science', 'Data Analytics', 'Computer Science', 'Information Systems', 'Applied Statistics', 'Statistics']
T('vanguard: Computer and Information Science, not Computer Sciences, Technology, or Business', run_wd.pick_by_prefs(VG, PREFS) == 'Computer and Information Science', run_wd.pick_by_prefs(VG, PREFS))
T('vanguard: the comma option is searched by its head too', 'Computer Sciences' in run_wd.prompt_queries('Computer Sciences, Technology, or Business'))
sys.exit(1 if bad else 0)
