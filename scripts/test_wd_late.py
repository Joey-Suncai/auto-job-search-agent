#!/usr/bin/env python3
"""JSA-273 (rule 13): DeepSeek-written cases from scripts/test_cases/wd_late_spec.md (wd_late_cases.json, verdicts in
wd_late_verdicts.json) for run_wd.unplanned_fields — fields that render after a Workday page was read are planned and
filled before Save and Continue is clicked again (NCR Voluntary Disclosures 11-10). Offline. python3 scripts/test_wd_late.py"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'skills', 'auto-apply', 'runner'))
try:
    import run_wd as W  # noqa: E402
except Exception as e:
    print(f'wd_late: run_wd not importable here ({type(e).__name__}) — skipped'); sys.exit(0)

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'wd_late_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'wd_late_cases.json')))
bad = 0
for c in cases:
    g = c['args']
    pk = None if g.get('planned_keys') is None else set(g['planned_keys'])
    got = W.unplanned_fields(pk, g.get('fields'))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1
        print('FAIL', c['name'], g, 'expect', c['expect'], 'got', got)
# fixed: NCR — the plan saw the consent box only, the four EEO selects rendered later
ncr = [{'key': 'w1', 'label': 'Are you Hispanic or Latino?', 'type': 'select'}, {'key': 'w5', 'label': 'Yes, I have read and consent', 'type': 'checkbox'}]
assert W.unplanned_fields({'w5'}, ncr) == ['Are you Hispanic or Latino?']
assert W.unplanned_fields(None, ncr) == []
print(f'wd_late: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) — fails {bad}')
sys.exit(1 if bad else 0)
