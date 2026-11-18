#!/usr/bin/env python3
"""JSA-327: Workday Degree dropdown — run_wd.bachelor_options (level-style options) and block_check.level_of (a multi-level
option is judged by its master / post-grad word, not by the PhD example in it). DeepSeek-written cases:
scripts/test_cases/wd_degree_level_cases.json; a case judged wrong goes into wd_degree_level_verdicts.json (none so far).
    python3 scripts/test_wd_degree_level.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_wd, block_check  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'wd_degree_level_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'wd_degree_level_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
def T(name, ok, info=''):
    global bad
    v = verdicts.get(name)
    if not ok and v and v.get('verdict') == 'case':
        print(f'SKIP {name}  (case judged wrong: {v["why"][:80]})'); return
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}')); bad += not ok

for c in cases:
    got = run_wd.bachelor_options(c['opts']) if c['fn'] == 'bachelor_options' else block_check.level_of(c['value'])
    T(c['name'], got == c['expect'], f"got {got!r} want {c['expect']!r}")

# the real Entrust / Micron lists (wd_log 2026-11-11): the runner must pick Joey's bachelor's without asking
ENT = ['Associate Degree', "4-year Degree (Bachelor's)", "Post-Graduate Degree (Master's, PhD, JD, etc.)", 'High School']
MIC = ["Master's Level Degree", "Bachelor's Level Degree", 'Doctorate Level Degree']
T('entrust: UIUC bachelor option chosen', (run_wd.bachelor_options(ENT) or [None])[0] == "4-year Degree (Bachelor's)")
T('micron: UIUC bachelor option chosen', (run_wd.bachelor_options(MIC) or [None])[0] == "Bachelor's Level Degree")
T("entrust: the block check reads the post-graduate option as master, not PhD", block_check.level_of("Post-Graduate Degree (Master's, PhD, JD, etc.)") == 'master')
T('a PhD-only post-graduate option stays phd', block_check.level_of('Doctorate - Post Graduate') == 'phd' and block_check.level_of('Graduate Degree (PhD)') == 'phd')
sys.exit(1 if bad else 0)
