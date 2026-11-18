#!/usr/bin/env python3
"""Harness for plan_build.date_answer / multi_answer (rule 13, JSA-073): DeepSeek cases in
test_cases/answer_format_cases.json, verdicts in answer_format_verdicts.json. Plus the Sevgalkel / Scientech regressions
through build()."""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import plan_build as PB
cases = json.load(open(os.path.join(HERE, 'test_cases', 'answer_format_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'answer_format_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    if c['fn'] == 'date':
        got, why = PB.date_answer(c['value'])
    else:
        got, why = PB.multi_answer(c['value'], c.get('options'))
    if (got is None) != bool(why):
        bad += 1; print('BROKEN CONTRACT', c['name'], got, why)
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', repr(got), why, '| expect', repr(c['expect']), '|', c['value'], c.get('options'))

# regressions (11-02): answers.json date "June 14, 2027" → 06/14/2027 in the plan; a season in a date box → needs_user
d = tempfile.mkdtemp()
json.dump({'q_date': 'June 14, 2027', 'q_season': 'Summer 2027', 'q_multi': 'On-Cycle Internship, Off-Cycle Internship', 'q_bad': ['Remote']},
          open(os.path.join(d, 'answers.json'), 'w'))
fields = [{'key': 'q_date', 'label': 'When is your earliest availability to start?', 'type': 'date', 'required': True, 'options': []},
          {'key': 'q_season', 'label': 'Start date', 'type': 'date', 'required': True, 'options': []},
          {'key': 'q_multi', 'label': 'Which type(s) of internship are you applying for?', 'type': 'multi', 'required': True,
           'options': ['On-Cycle Internship', 'Off-Cycle Internship']},
          {'key': 'q_bad', 'label': 'Preferred Office(s) Location', 'type': 'multi', 'required': False, 'options': ['U.S.', 'Shanghai']}]
plan = PB.build(d, fields, 'https://jobs.ashbyhq.com/x/00000000-0000-0000-0000-000000000000/application', 'ashby')
by = {f['key']: f for f in plan['fields']}
need = {n['key'] for n in plan['needs_user']}
for name, ok in (('date rewritten to MM/DD/YYYY', by['q_date'].get('answer') == '06/14/2027'),
                 ('season in a date box → needs_user', by['q_season']['status'] == 'needs_user' and 'q_season' in need),
                 ('comma list → multi parts', by['q_multi'].get('answer') == 'On-Cycle Internship | Off-Cycle Internship'),
                 ('non-option multi → listed, optional so skipped', by['q_bad']['status'] == 'skip_optional' and 'q_bad' in need),
                 ('plan not ready while a required date is wrong', plan['ready'] is False)):
    if not ok:
        bad += 1; print('FAIL', name)
print(f'{len(cases)} cases + 5 regressions · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
