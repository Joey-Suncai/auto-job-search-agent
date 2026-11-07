#!/usr/bin/env python3
"""DeepSeek cases (scripts/test_cases/rules_fix150_cases.json) for the JSA-150 answer-rule fixes, run through rules_bridge.js.
Verdicts in rules_fix150_verdicts.json.    python3 scripts/test_rules_fix150.py"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
cases = json.load(open(os.path.join(HERE, 'test_cases', 'rules_fix150_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
q = [{'key': str(i), 'label': c['label'], 'type': c.get('type', 'text'), 'options': []} for i, c in enumerate(cases)]
r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.join(RUN, '..', 'scripts', 'answer_rules.js')],
                   input=json.dumps(q), capture_output=True, text=True, timeout=60)
ans = json.loads(r.stdout or '{}')
vp = os.path.join(HERE, 'test_cases', 'rules_fix150_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for i, c in enumerate(cases):
    a = ans.get(str(i)) or {}
    rule, val = (a.get('rule'), a.get('value')) if a.get('status') == 'ok' else (None, None)
    if c['expect_rule'] == 'not:phone':
        ok = rule != 'phone'
    elif c['expect_rule'] is None:
        ok = rule is None
    else:
        ok = rule == c['expect_rule'] and (c.get('expect_value') is None or val == c['expect_value'])
    if ok:
        print('PASS ', c['name']); continue
    if (verdicts.get(c['name']) or {}).get('verdict') == 'case':
        print('CASE ', c['name'], '—', verdicts[c['name']]['why']); continue
    bad += 1; print('FAIL ', c['name'], '|', c['label'][:80], '| got', rule, repr(val), '| want', c['expect_rule'], repr(c.get('expect_value')))
print(f'{len(cases) - bad}/{len(cases)} ok'); sys.exit(1 if bad else 0)
