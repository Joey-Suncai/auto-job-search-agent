#!/usr/bin/env python3
"""Harness for run_icims.py pure helpers (JSA-093, rule 13): DeepSeek cases in test_cases/icims_cases.json (from
icims_spec.md), verdicts for disagreements in icims_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_icims as R

cases = json.load(open(os.path.join(HERE, 'test_cases', 'icims_cases.json')))
_later = json.load(open(os.path.join(HERE, 'test_cases', 'icims_later_cases.json')))   # JSA-143 "Finish Later"
cases += _later['cases'] if isinstance(_later, dict) else _later
vp = os.path.join(HERE, 'test_cases', 'icims_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    fn = getattr(R, c['fn'])
    try:
        got = fn(*c['args'])
    except Exception as e:
        got = f'ERROR {type(e).__name__}: {e}'
    if isinstance(got, tuple):
        got = list(got)
    exp = c['expect']
    if c['fn'] == 'pick_button' and isinstance(got, dict) and isinstance(exp, dict):
        ok = got.get('id') == exp.get('id') and got.get('text') == exp.get('text')
    else:
        ok = got == exp
    if not ok and c['name'] not in verdicts:
        bad += 1
        print('DISAGREE', c['fn'], '|', c['name'], '\n   args', json.dumps(c['args'], ensure_ascii=False)[:300],
              '\n   got ', json.dumps(got, ensure_ascii=False)[:300], '\n   want', json.dumps(exp, ensure_ascii=False)[:300])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
