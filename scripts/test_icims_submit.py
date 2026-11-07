#!/usr/bin/env python3
"""Harness for the iCIMS submit path (JSA-093, rule 13): DeepSeek cases in test_cases/icims_submit_cases.json (from
icims_submit_spec.md) against run_icims.submit_gate / after_submit / consent_gate and run_form.posting_key; verdicts for
disagreements in icims_submit_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_icims as R  # noqa: E402
import run_form as F  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'icims_submit_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'icims_submit_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    fn = getattr(F if c['fn'] == 'posting_key' else R, c['fn'])
    try:
        got = fn(*c['args'])
    except Exception as e:
        got = f'ERROR {type(e).__name__}: {e}'
    if got == c['expect']:
        continue
    if c['name'] in verdicts:
        print('CASE ', c['name'], '—', verdicts[c['name']]['why'][:120]); continue
    bad += 1
    print('DISAGREE', c['fn'], '|', c['name'], '\n   args', json.dumps(c['args'], ensure_ascii=False)[:400],
          '\n   got ', json.dumps(got, ensure_ascii=False)[:200], '\n   want', json.dumps(c['expect'], ensure_ascii=False)[:200])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
