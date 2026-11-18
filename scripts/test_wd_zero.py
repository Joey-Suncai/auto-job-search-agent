#!/usr/bin/env python3
"""JSA-272 (rule 13): DeepSeek-written cases from scripts/test_cases/wd_zero_spec.md (wd_zero_cases.json, verdicts in
wd_zero_verdicts.json) for run_wd.zero_rejected (a digits-only box where the tenant counts 0 as empty → Joey) and
run_wd.block_kind_of (now also the plan's block test: "Schools Attended N" blocks are matched / deleted). Offline.
python3 scripts/test_wd_zero.py"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
try:
    import run_wd as W  # noqa: E402
except Exception as e:
    print(f'wd_zero: run_wd not importable here ({type(e).__name__}) — skipped'); sys.exit(0)

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'wd_zero_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'wd_zero_cases.json')))
bad = 0
for c in cases:
    g, exp = c['args'], c['expect']
    if c['fn'] == 'zero_rejected':
        got = [f['label'] for f in W.zero_rejected(g['errs'], g['fields'])]
    else:
        got = W.block_kind_of(g['section'])
    if got != exp and c['name'] not in verdicts:
        bad += 1
        print('FAIL', c['name'], g, 'expect', exp, 'got', got)
# fixed: the live BCBS NE error (11-10) and the NCR heading
assert [f['label'] for f in W.zero_rejected(['Error: The field  What is your current annual salary?  is required and must have a value.'],
        [{'label': 'What is your current annual salary?', 'answer': '0'}])] == ['What is your current annual salary?']
assert W.zero_rejected(['Error: The field What is your desired Annual Salary? is required and must have a value.'],
        [{'label': 'What is your desired Annual Salary?', 'answer': '52000'}]) == []
assert W.block_kind_of('Schools Attended 14') == 'education'
print(f'wd_zero: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) — fails {bad}')
sys.exit(1 if bad else 0)
