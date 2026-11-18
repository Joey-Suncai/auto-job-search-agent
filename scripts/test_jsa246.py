#!/usr/bin/env python3
"""JSA-246 (rule 13): DeepSeek-written cases from scripts/test_cases/jsa246_spec.md (jsa246_cases.json, verdicts in
jsa246_verdicts.json): the full rule set (runner/rules_bridge.js, example profile with future sponsorship = Yes, no saved
answers) for sponsorship-for-this-internship, marketing consent, false place-claim options, digits-only pay boxes and
reason for leaving.   python3 scripts/test_jsa246.py"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNNER = os.path.join(ROOT, 'skills', 'auto-apply', 'runner')
TMP = tempfile.mkdtemp(prefix='jsa246_')
CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'jsa246_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'jsa246_cases.json')))

prof = json.load(open(os.path.join(ROOT, 'config', 'profile.example.json')))
prof['qa'] = []
prof['answers']['spons_future'] = {'yes': True}          # the spec's candidate: no sponsorship now (CPT), yes in the future
pp = os.path.join(TMP, 'profile.json')
json.dump(prof, open(pp, 'w'))
fields = [dict(c['field'], key=str(i)) for i, c in enumerate(cases)]
r = subprocess.run(['node', os.path.join(RUNNER, 'rules_bridge.js')], input=json.dumps(fields), capture_output=True, text=True,
                   timeout=120, env=dict(os.environ, JSA_HOME=TMP, JSA_PROFILE=pp, CX_SECOND_OPINION='0', JSA_NO_PUSH='1'))
got = json.loads(r.stdout or '{}')
if r.returncode:
    print(r.stderr[-800:])
bad = 0
for i, c in enumerate(cases):
    a = got.get(str(i)) or {}
    ok = a.get('status') == c['expect_status'] and (c['expect_status'] != 'ok' or c.get('expect_value') is None or a.get('value') == c['expect_value'])
    if not ok and c['name'] not in verdicts:
        bad += 1
        print('FAIL', c['name'], json.dumps(c['field'], ensure_ascii=False)[:220], '→', json.dumps(a, ensure_ascii=False)[:260], '| want', c['expect_status'], c.get('expect_value'))
print(f'jsa246: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) — fails {bad}')
sys.exit(1 if bad else 0)
