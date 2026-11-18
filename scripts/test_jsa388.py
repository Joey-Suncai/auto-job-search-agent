#!/usr/bin/env python3
"""JSA-388 (Joey 2026-11-17): the resume is always the approved direction master; the old four role versions are never selected.
Checks (hand-derived from the row): master_resume(tailoring=False) lays out the approved master unchanged — no changes, no swaps,
no terms; an unknown track → None (the caller fails the job, never a bank pick); the retired bank-pick builders are gone.
Needs an approved master in the data home (test_all.sh runs on a clone of it); skips that part when there is none.
    python3 scripts/test_jsa388.py   → "fails 0" """
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts'))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'resume-updater', 'scripts'))
sys.path.insert(0, os.path.join(HERE, '..', 'config'))
import ds_materials as D
fails = 0
def check(name, cond, detail=''):
    global fails
    if not cond: fails += 1; print('FAIL', name, detail)
    else: print('ok  ', name)

for gone in ('layout_fill', 'layout_search', 'fill_candidates', 'add_fill'):
    check(f'{gone} is retired', not hasattr(D, gone))
check('master_resume has the tailoring switch', 'tailoring' in D.master_resume.__code__.co_varnames[:D.master_resume.__code__.co_argcount])
check('an unknown track has no master → None', D.master_resume('# Job', 'No_Such_Track', 'Acme', 'Intern', os.path.join(tempfile.mkdtemp(), 'r.docx')) is None)
import tailor as TL
if TL.approved_master('ai_pm')[0]:
    jd = '# Product Manager Intern - Acme\n\n' + 'You will own the product roadmap and write product requirements for LLM features. ' * 20
    out = os.path.join(tempfile.mkdtemp(), 'r.docx')
    r = D.master_resume(jd, 'Product_Manager', 'Acme', 'Product Manager Intern', out, tailoring=False)
    check('tailoring off: the master is laid out unchanged (res present, no changes / swaps / terms)',
          r and r.get('res') and r['changes'] == [] and r['swaps'] == [] and r['terms'] == [] and 'unchanged' in r['note'], r and {k: r.get(k) for k in ('note', 'changes', 'swaps')})
else:
    print('skip tailoring-off layout: no approved ai_pm master in this data home')
print('fails', fails); sys.exit(1 if fails else 0)
