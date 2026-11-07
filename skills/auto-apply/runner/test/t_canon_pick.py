#!/usr/bin/env python3
"""JSA-005: canon.pick chooses the canon-valid option from a field's own list; plan_build uses it. Prints ALL PASS or N FAILED."""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
os.environ['CX_DATA'] = tempfile.mkdtemp(prefix='cxpick_')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'config')); import jsa_profile; jsa_profile.use_fixture_if_no_user()   # fresh clone: F-1 test fixture (JSA-086)
import canon
fails = 0
def T(name, ok, got=''):
    global fails
    fails += (not ok); print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  -> {got!r}'))

V = ['I identify as one or more of the classifications of protected veterans', 'I identify as a Veteran, just not a protected Veteran',
     'I am not a Veteran, but am a Military Spouse.', 'I am not a Veteran (United States of America)', 'I do not wish to self-identify']
T('veteran: spouse / identify options skipped', canon.pick('veteran_status', V) == 'I am not a Veteran (United States of America)', canon.pick('veteran_status', V))
T('sponsorship future: Yes', canon.pick('sponsorship_future', ['Select One', 'No', 'Yes']) == 'Yes', canon.pick('sponsorship_future', ['Select One', 'No', 'Yes']))
T('source: first real option', canon.pick('source_channel', ['Select One', 'Company Website', 'LinkedIn']) == 'Company Website')
T('per-entry keys are never picked', canon.pick('school', ['University of Chicago', 'University of Illinois Urbana-Champaign']) is None)
T('no valid option → None (ask Joey)', canon.pick('veteran_status', ['I identify as a protected veteran']) is None)
canon.learn('acme.wd1.myworkdayjobs.com', 'gender', 'Man')
T('learned value for the tenant wins', canon.pick('gender', ['Woman', 'Man', 'Decline'], 'acme.wd1.myworkdayjobs.com') == 'Man',
  canon.pick('gender', ['Woman', 'Man', 'Decline'], 'acme.wd1.myworkdayjobs.com'))

import plan_build as PB
PB.run_rules = lambda fields, jd='', company='': {'q1': {'status': 'ok', 'value': 'No', 'rule': 'spons_now'}, 'q2': {'status': 'ok', 'value': 'I identify as a Veteran, just not a protected Veteran', 'rule': 'x'}}
d = tempfile.mkdtemp()
fields = [{'key': 'q1', 'label': 'Will you now or in the future require sponsorship?', 'type': 'select', 'required': True, 'options': ['No', 'Yes']},
          {'key': 'q2', 'label': 'Veteran Status', 'type': 'select', 'required': True, 'options': V},
          {'key': 'q3', 'label': 'How did you hear about us?', 'type': 'select', 'required': True, 'options': ['Job Board', 'Referral']}]
plan = PB.build(d, fields, 'https://acme.wd1.myworkdayjobs.com/x', 'workday')
got = {f['key']: (f.get('answer'), f.get('source')) for f in plan['fields']}
T('plan_build: rule answered sponsorship No → canon fixes to Yes (Brakelwyn 10-28)', got['q1'] == ('Yes', 'canon:sponsorship_future'), got['q1'])
T('plan_build: wrong veteran option → canon option', got['q2'][0] == 'I am not a Veteran (United States of America)', got['q2'])
T('plan_build: no rule for source → first option, not a needs item', got['q3'] == ('Job Board', 'canon:source_channel') and plan['ready'], (got['q3'], plan['needs_user']))
open(os.path.join(d, 'answers.json'), 'w').write('{"Veteran Status": "I do not wish to self-identify"}')
plan = PB.build(d, fields, 'https://acme.wd1.myworkdayjobs.com/x', 'workday')
T("plan_build: Joey's answers.json is never overruled", next(f for f in plan['fields'] if f['key'] == 'q2')['answer'] == 'I do not wish to self-identify')
print('ALL CANON PICK TESTS PASS' if not fails else f'{fails} FAILED'); sys.exit(1 if fails else 0)
