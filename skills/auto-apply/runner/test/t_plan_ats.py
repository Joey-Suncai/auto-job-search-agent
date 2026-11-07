#!/usr/bin/env python3
"""JSA-004: plan_build reads a Lever apply page and an Ashby posting (offline fixtures saved 2026-10-30)."""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
os.environ['CX_DATA'] = tempfile.mkdtemp(prefix='cxats_')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'config')); import jsa_profile; jsa_profile.use_fixture_if_no_user()   # fresh clone: F-1 test fixture (JSA-086)
import plan_build as PB
fails = 0
def T(name, ok, got=''):
    global fails
    fails += (not ok); print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  -> {got!r}'))

lv = PB.lever_fields(open(os.path.join(HERE, 'lever_form_fixture.html'), encoding='utf-8').read())
keys = {f['key']: f for f in lv}
T('lever: standard fields', all(k in keys for k in ('name', 'email', 'phone', 'resume')), sorted(keys)[:8])
spons = next((f for f in lv if 'sponsorship' in f['label'].lower()), None)
T('lever: custom card question with options', spons and spons['type'] == 'radio' and spons['options'] == ['Yes', 'No'], spons)
uni = next((f for f in lv if 'school do you currently attend' in f['label'].lower()), None)
T('lever: university select options come from the page', uni and 'University of Chicago' in ' '.join(uni['options']), uni and uni['options'][:6])
T('lever: selectors use the field name', spons and spons['sel'].startswith('[name="cards['), spons and spons['sel'])
plan = PB.build(tempfile.mkdtemp(), lv, 'https://jobs.lever.co/protective/40354575-2b06-42cd-93fb-f9ea82bdec7c/apply', 'lever')
ans = {f['label']: f.get('answer') for f in plan['fields']}
T('lever plan: sponsorship now or future = Yes', ans.get(spons['label']) == 'Yes', ans.get(spons['label']))
T('lever plan: name / email', ans.get('Full name') == 'Alex Rivera' and ans.get('Email') == 'alex.rivera@example.com')

ab = PB.ashby_fields(json.load(open(os.path.join(HERE, 'ashby_ostbraros.json'), encoding='utf-8')))
ak = {f['label']: f for f in ab}
T('ashby: system fields + resume file', ak.get('Name', {}).get('key') == '_systemfield_name' and ak.get('Resume', {}).get('type') == 'file', sorted(ak)[:6])
T('ashby: Boolean → Yes / No radio', ak.get('Prior Government Employment?', {}).get('options') == ['Yes', 'No'])
T('ashby: EEO survey is demographic', ak.get('Veteran Status', {}).get('demographic') is True)
plan = PB.build(tempfile.mkdtemp(), ab, 'https://jobs.ashbyhq.com/ostbraros/ae4a6f7d-a240-4fa2-8c8e-04cc906e4ef9', 'ashby')
aa = {f['label']: f.get('answer') for f in plan['fields']}
T('ashby plan: ready, veteran + government answered', plan['ready'] and aa.get('Veteran Status') == 'I am not a protected veteran' and aa.get('Prior Government Employment?') == 'No', aa)
T('url parsers', PB.lever_parse_url('https://jobs.lever.co/zoox/7206fd97-14e4-43a0-b903-ba65dfeee53e/apply') == ('zoox', '7206fd97-14e4-43a0-b903-ba65dfeee53e')
  and PB.ashby_parse_url('https://jobs.ashbyhq.com/ostbraros/ae4a6f7d-a240-4fa2-8c8e-04cc906e4ef9/application?embed=true')[0] == 'ostbraros')
# JSA-105: "meet the years of experience required" reads <folder>/jd.md — none → Yes; years asked → Joey, never DeepSeek triage
yq = [{'key': 'yoe', 'label': 'Do you meet the years of experience required for this position?', 'type': 'radio', 'options': ['Yes', 'No'], 'required': True}]
d1 = tempfile.mkdtemp(); open(os.path.join(d1, 'jd.md'), 'w').write('# Intern\nSummer 2027 internship for current students. No prior experience required.\n')
p1 = PB.build(d1, yq, 'https://x.wd1.myworkdayjobs.com/en-US/ext/job/1', 'workday')
T('yoe: internship jd.md → Yes', p1['fields'][0].get('answer') == 'Yes' and p1['ready'], p1['fields'][0])
d2 = tempfile.mkdtemp(); open(os.path.join(d2, 'jd.md'), 'w').write('# Analyst\nQualifications: 2+ years of experience in analytics.\n')
p2 = PB.build(d2, yq, 'https://x.wd1.myworkdayjobs.com/en-US/ext/job/2', 'workday')
T('yoe: 2+ years → needs Joey, no triage', not p2['ready'] and p2['needs_user'] and p2['needs_user'][0].get('no_triage') and p2['fields'][0].get('no_triage'), p2['needs_user'])
p3 = PB.build(tempfile.mkdtemp(), yq, 'https://x.wd1.myworkdayjobs.com/en-US/ext/job/3', 'workday')
T('yoe: no jd.md → needs Joey', not p3['ready'] and p3['needs_user'][0].get('no_triage'), p3['needs_user'])
print('ALL ATS PLAN TESTS PASS' if not fails else f'{fails} FAILED'); sys.exit(1 if fails else 0)
