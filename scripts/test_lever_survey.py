#!/usr/bin/env python3
"""Harness for plan_build.lever_survey + the survey-section filter in build() (rule 13, JSA-075): DeepSeek cases in
test_cases/lever_survey_cases.json, verdicts in lever_survey_verdicts.json. The country answer goes in through
answers.json (key candidate-location), so the profile's own answer does not matter here."""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import plan_build as PB
cases = json.load(open(os.path.join(HERE, 'test_cases', 'lever_survey_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'lever_survey_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
URL = 'https://jobs.lever.co/acme/00000000-0000-0000-0000-000000000000/apply'
bad = 0
for c in cases:
    fields = PB.lever_survey(c['html'])
    got = [{'key': f['key'], 'type': f['type'], 'label': f['label'], 'options': f['options'], 'required': f['required'],
            'survey_for': f.get('survey_for')} for f in fields]
    want = [{k: e.get(k) for k in ('key', 'type', 'label', 'options', 'required', 'survey_for')} for e in c['expect_fields']]
    d = tempfile.mkdtemp()
    if c.get('country') is not None:
        json.dump({'candidate-location': c['country']}, open(os.path.join(d, 'answers.json'), 'w'))
    else:
        json.dump({'candidate-location': None}, open(os.path.join(d, 'answers.json'), 'w'))   # no answer (None = leave blank)
    keys = [f['key'] for f in PB.build(d, fields, URL, 'lever')['fields']] if fields else []
    ok = got == want and keys == c['expect_plan_keys']
    if not ok and c['name'] not in verdicts:
        bad += 1
        print('DISAGREE', c['name'])
        if got != want:
            for g, w in zip(got + [None] * (len(want) - len(got)), want + [None] * (len(got) - len(want))):
                if g != w: print('   field got', g, '\n         want', w)
        if keys != c['expect_plan_keys']:
            print('   plan keys got', keys, '\n             want', c['expect_plan_keys'])

# regression: a real Lever page (2026-11-02) — country select + one all-locations survey (age range)
fx = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner', 'test', 'lever_survey_fixture.html')
if os.path.exists(fx):
    fs = PB.lever_survey(open(fx, encoding='utf-8').read())
    if not (fs and fs[0]['key'] == 'candidate-location' and 'United States' in fs[0]['options'] and fs[0]['option_values']['United States'] == 'US'
            and any(f['label'] == 'What is your age range?' and f['survey_for'] == '*' and f['type'] == 'radio' for f in fs)):
        bad += 1; print('FAIL survey fixture', [(f['key'][:40], f['label'], f.get('survey_for')) for f in fs])
print(f'{len(cases)} cases + page fixture · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
