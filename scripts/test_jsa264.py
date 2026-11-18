#!/usr/bin/env python3
"""JSA-264 (rule 13): DeepSeek-written cases from scripts/test_cases/never_strip_spec.md (never_strip_cases.json,
verdicts in never_strip_verdicts.json) for ds_materials.strip_never; plus fixed checks: the bank-pick resume drops the
role's summary (build_docx prints one since JSA-250 → two pages), never_phrases keeps only names, the master result
carries check / top for write_resume_report, the company's own name is no banned word. Offline.   python3 scripts/test_jsa264.py"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'scripts'))
try:
    import ds_materials as M
except Exception as e:   # a python without docx / numpy: the materials payload is not installed here
    print(f'jsa264: skipped ({type(e).__name__}: {e})'); sys.exit(0)

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'never_strip_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'never_strip_cases.json')))
bad = 0


def check(name, ok, *info):
    global bad
    if not ok and name not in verdicts:
        bad += 1
        print('FAIL', name, *info)


for c in cases:
    g = M.strip_never(c['args']['text'], c['args']['phrases'])
    check(c['name'], g == c['expect'], repr(c['args']), 'expect', repr(c['expect']), 'got', repr(g))

# fixed: chosen_role never carries a summary (legacy resume), whatever ROLES holds
track = next(iter(M.C.ROLES))
role = M.C.ROLES[track]
rs = dict(headline_title='X', skill_lines=[], exp={M.ORG_KEY[e['org']]: [] for e in role['exp']},
          projects={M.ORG_KEY[p['title']]: [] for p in role['projects']})
r = M.chosen_role(dict(resume=rs), dict(track=track, bank_by_id={}, skill_pool={}), (30, 120))
check('fixed: legacy role has no summary', 'summary' not in r, sorted(r))
# fixed: only names are stripped
check('fixed: names only', all(all(x[:1].isupper() for x in w.split()) for w in M.never_phrases()), M.never_phrases())
check('fixed: wording rule untouched', M.strip_never('I did it independently', ['XJTLU']) == 'I did it independently')
# fixed: the master result keeps check / top (source check: write_resume_report reads both)
src = open(os.path.join(ROOT, 'skills', 'auto-apply', 'scripts', 'ds_materials.py'), encoding='utf-8').read()
check('fixed: master res has check and top', 'top=lr.get("top", 0)' in src and 'check=lr.get("check")' in src)
dm = open(os.path.join(ROOT, 'skills', 'resume-updater', 'scripts', 'direction_master.py'), encoding='utf-8').read()
check('fixed: layout returns top', 'cfg=cfg, top=top, bottom=bot' in dm)

# fixed: the company's own name is no banned word, the word elsewhere still is
V = dict(company='Hardelnev', company_low=M.norm('Hardelnev'), stories={'S1': 'x'}, bank_by_id={}, skill_pool={},
         profile='', jd='', corpus='', notes='')
ban = lambda t: [e for e in M.check_text('p1', t, ['S1'], V, {'S1'}) if 'banned' in e]
check('fixed: company name not banned', ban('I want to help Hardelnev grow its donor base.') == [])
check('fixed: banned word elsewhere', ban('A dynamic team at Hardelnev.') != [])

print(f'jsa264: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) + fixed checks — fails {bad}')
sys.exit(1 if bad else 0)
