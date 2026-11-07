#!/usr/bin/env python3
"""Harness for run_form.date_same / date_value / pick_school / submit_errors (rule 13, JSA-208 + JSA-209): DeepSeek cases
from test_cases/ashby_submit_school_spec.md, Claude's verdicts in test_cases/ashby_submit_school_verdicts.json.
Plus the regression check of JSA-208: a plan written before the prep-time date check (sanitised Creatify fixture,
fictional person) is still typed and read back as MM/DD/YYYY by the runner."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_form  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'ashby_submit_school_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'ashby_submit_school_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    fn = getattr(run_form, c['fn'])
    got = fn(*c['args'])
    exp = c['expect']
    if c['fn'] == 'date_value' and isinstance(exp, list) and exp[0] is None:
        ok = got[0] is None and bool(got[1])                  # a refusal: only "no value + a reason" is checked
    elif c['fn'] == 'date_value':
        ok = got[0] == exp[0] and got[1] is None
    else:
        ok = got == exp
    if not ok and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['fn'], c['name'], '| got', json.dumps(got)[:200], '| expect', json.dumps(exp)[:200])

# JSA-208 regression: the stale plan field (answers.json value kept as Joey wrote it, before plan_build.date_answer ran)
fx = json.load(open(os.path.join(HERE, 'test_cases', 'ashby_stale_date_plan.json')))
date_f = next(f for f in fx['fields'] if f['type'] == 'date')
typed = run_form.date_value(date_f['answer'])
if typed != ['06/14/2027', None]:
    bad += 1; print('REGRESSION JSA-208: stale plan date typed as', typed)
if not run_form.Form.same(None, date_f, '06/14/2027'):
    bad += 1; print('REGRESSION JSA-208: "June 14, 2027" does not read back equal to the box\'s 06/14/2027')
if run_form.Form.same(None, date_f, '06/15/2027'):
    bad += 1; print('REGRESSION JSA-208: another day reads back as the same date')
if not run_form.Form.same(None, date_f, 'June 14, 2027'):     # Lever: a text date box shows what was typed — unchanged
    bad += 1; print('REGRESSION Lever: a date typed as is no longer reads back equal')
# JSA-209 regression: the Ramp red box (sanitised page text) → failed with the field name
ramp = open(os.path.join(HERE, 'test_cases', 'ashby_submit_errors_page.txt'), encoding='utf-8').read()
if run_form.submit_errors(ramp) != ['School']:
    bad += 1; print('REGRESSION JSA-209: Ramp page errors read as', run_form.submit_errors(ramp))
print(f'{len(cases)} cases + 6 regression checks · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
