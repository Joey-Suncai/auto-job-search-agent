#!/usr/bin/env python3
"""JSA-337: a cached DeepSeek answer (ds_answers.json) never overrides the rules / qa. DeepSeek-written cases
(scripts/test_cases/ds_cache_priority_cases.json) against plan_build.ds_cache_may_answer, plus plan_build.build end to end.
    python3 scripts/test_ds_cache_priority.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import plan_build  # noqa: E402

bad = 0
def T(name, ok, info=''):
    global bad
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}'))
    bad += not ok

for c in json.load(open(os.path.join(HERE, 'test_cases', 'ds_cache_priority_cases.json'))):
    T(c['name'], plan_build.ds_cache_may_answer(c['rule'], c['ds_value']) == c['expect'])

# end to end: AMAT "Which best describes your status?" — cache says earlier year, qa (rules) says second to last year
OPTS = ['I am in my first year of study', 'I am in my second to last year of study', 'I am in an earlier year of study']
F = [{'key': 'q1', 'label': 'Which best describes your status?', 'type': 'combo', 'required': True, 'options': OPTS},
     {'key': 'q2', 'label': 'Preferred duration', 'type': 'combo', 'required': True, 'options': ['3 months', '6 months']}]
d = tempfile.mkdtemp()
json.dump({'^Which best describes your status\\?$': OPTS[2], '^Preferred duration$': '3 months'}, open(os.path.join(d, 'ds_answers.json'), 'w'))
plan_build.run_rules = lambda fields, jd='', company='', cover='': {'q1': {'status': 'ok', 'rule': 'qa', 'value': OPTS[1]}}
pl = plan_build.build(d, F, '', 'workday')
got = {f['key']: (f.get('answer'), f.get('source')) for f in pl['fields']}
T('build: qa answer beats cached DeepSeek answer', got['q1'][0] == OPTS[1] and got['q1'][1].startswith('rules:'), got['q1'])
T('build: cache still fills what the rules cannot answer', got['q2'] == ('3 months', 'ds_answers.json'), got['q2'])
sys.exit(1 if bad else 0)
