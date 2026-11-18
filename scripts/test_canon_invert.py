#!/usr/bin/env python3
"""JSA-267 (rule 13): DeepSeek-written cases from scripts/test_cases/canon_invert_spec.md (canon_invert_cases.json,
verdicts in canon_invert_verdicts.json) for canon.pick_for / canon.judge, against the example canon (fixed facts).
Plus the Wynverlum 11-10 wording. Offline.   python3 scripts/test_canon_invert.py"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
import canon  # noqa: E402

for k in ('sponsorship_future', 'sponsorship_now'):   # the spec's facts, whatever data home is set
    canon.SPEC['fields'][k] = dict(canon.SPEC['fields'].get(k, {}))
canon.SPEC['fields']['sponsorship_future'].update(want='Yes', accept=[r'^yes\b', r'^(i )?(will |would )?(requires?|needs?) (visa |immigration |employer |employment |h-?1b )?sponsorship'], accept_exact=['yes'], reject=[r'\bnot\b', r'\bno\b', r'\bnever\b'])
canon.SPEC['fields']['sponsorship_now'].update(want='No', accept=[r'^no\b'], accept_exact=['no'], reject=[])
canon.learned = lambda tenant: {}

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'canon_invert_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'canon_invert_cases.json')))
bad = 0
for c in cases:
    g = c['args']
    got = canon.pick_for(g['key'], g['label'], g['options']) if c['fn'] == 'pick_for' else canon.judge(g['key'], g['label'], g['value'])[0]
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1
        print('FAIL', c['name'], g, 'expect', c['expect'], 'got', got)
L = 'Are you currently authorized to work in the United States on a full-time basis without the need for sponsorship now or in the future?'
if canon.pick_for('sponsorship_future', L, ['Yes', 'No - I would need sponsorship']) != 'No - I would need sponsorship':
    bad += 1; print('FAIL fixed: Wynverlum 11-10')
if 'wants No' not in canon.judge('sponsorship_future', L, 'Yes')[1]:
    bad += 1; print('FAIL fixed: reason names the wanted answer', canon.judge('sponsorship_future', L, 'Yes')[1])
print(f'canon_invert: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) + fixed checks — fails {bad}')
sys.exit(1 if bad else 0)
