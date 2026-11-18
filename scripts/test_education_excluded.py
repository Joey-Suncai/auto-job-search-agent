#!/usr/bin/env python3
"""Harness for run_form.edu_same (absent keys) + run_form.edu_select_values (rule 13, JSA-330): DeepSeek cases from
test_cases/education_excluded_spec.md, verdicts in test_cases/education_excluded_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_form  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'education_excluded_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'education_excluded_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = getattr(run_form, c['fn'])(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got)[:300], '| expect', json.dumps(c['expect'])[:300])
# plan_build → run_form link (review of JSA-330): the form config's 'excluded' sub-fields end up on the plan field
import plan_build  # noqa: E402
def posting(**cfg):
    return {'applicationForm': {'sections': [{'fieldEntries': [{'id': 'x__systemfield_education_history', 'isRequired': True,
            'field': {'path': '_systemfield_education_history', 'title': 'Education History', 'type': 'EducationHistory',
                      'schoolName': 'required', **cfg}}]}]}, 'surveyForms': []}
f = plan_build.ashby_fields(posting(degree='excluded', major='optional', startDate='excluded', endDate='optional'))[0]
g = plan_build.ashby_fields(posting(degree='optional', major='optional', startDate='optional', endDate='optional'))[0]
if f.get('edu_excluded') != ['degree', 'startDate'] or g.get('edu_excluded') != [] or f['type'] != 'education':
    bad += 1; print('DISAGREE ashby_fields edu_excluded', f.get('edu_excluded'), g.get('edu_excluded'))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
