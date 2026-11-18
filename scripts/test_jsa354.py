#!/usr/bin/env python3
"""JSA-354 (rule 13): DeepSeek-written cases from test_cases/jsa354_spec.md (jsa354_cases.json, verdicts in
jsa354_verdicts.json) for the languages rule: option lists keep working, a text box asking which languages are spoken
lists every language in the facts. Full rule set via runner/rules_bridge.js, example profile + Chinese / English facts.
    python3 scripts/test_jsa354.py"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNNER = os.path.join(ROOT, 'skills', 'auto-apply', 'runner')
TMP = tempfile.mkdtemp(prefix='jsa354_')
CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'jsa354_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'jsa354_cases.json')))
bad = 0


def check(name, ok, *info):
    global bad
    if not ok and name not in verdicts:
        bad += 1
        print('FAIL', name, *info)


prof = json.load(open(os.path.join(ROOT, 'config', 'profile.example.json')))
prof['qa'] = []
prof['languages'] = [{'name': 'Chinese (Mandarin)', 're': 'chinese|mandarin', 'level': 'native'},
                     {'name': 'English', 're': 'english', 'level': 'professional'}]
pp = os.path.join(TMP, 'profile.json')
json.dump(prof, open(pp, 'w'))
fields = [dict(c['field'], key=str(i)) for i, c in enumerate(cases)]
r = subprocess.run(['node', os.path.join(RUNNER, 'rules_bridge.js')], input=json.dumps(fields), capture_output=True,
                   text=True, timeout=120, env=dict(os.environ, JSA_PROFILE=pp, CX_SECOND_OPINION='0'))
got = json.loads(r.stdout or '{}')
if r.returncode:
    print(r.stderr[-800:])
for i, c in enumerate(cases):
    a = got.get(str(i)) or {}
    ok = a.get('status') == c['expect_status']
    if ok and c['expect_status'] == 'ok' and c.get('expect_value') is not None:
        ok = a.get('value') == c['expect_value']
    if c['expect_status'] == 'unknown':
        ok = a.get('status') != 'ok' or a.get('rule') != 'languages'
    check(c['name'], ok, json.dumps(c['field'], ensure_ascii=False)[:200], '→', json.dumps(a, ensure_ascii=False)[:300])
print(f'jsa354: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) — fails {bad}')
sys.exit(1 if bad else 0)
