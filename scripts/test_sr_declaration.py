#!/usr/bin/env python3
"""Harness for run_smartrecruiters.declaration_rule (rule 13, JSA-326): DeepSeek cases from test_cases/sr_declaration_spec.md,
verdicts in test_cases/sr_declaration_verdicts.json. Also checks the hook in the page-2 loop (apply_declarations)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_smartrecruiters as SR  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'sr_declaration_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'sr_declaration_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = SR.declaration_rule(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got), '| expect', json.dumps(c['expect']))
# the hook: a required single-option declaration box the rules left unanswered becomes ok; nothing else is touched
REL = 'I hereby grant permission to any person, firm or corporation to release to the Company any information regarding my past work or employment. I waive any and all claims.'
fields = [{'key': 'a', 'label': REL, 'type': 'checkbox', 'required': True, 'options': ['* ' + REL]},
          {'key': 'b', 'label': REL, 'type': 'checkbox', 'required': False, 'options': ['* ' + REL]},
          {'key': 'c', 'label': 'I agree to receive marketing emails', 'type': 'checkbox', 'required': True, 'options': ['I agree to receive marketing emails']},
          {'key': 'd', 'label': REL, 'type': 'checkbox', 'required': True, 'options': ['* ' + REL]}]
ans = {'b': {'status': 'unknown'}, 'd': {'status': 'ok', 'value': 'x', 'rule': 'terms'}}
out = SR.apply_declarations(fields, ans)
ok = (out['a']['status'] == 'ok' and out['a']['rule'] == 'declaration:background_release' and out['a']['value'] == '* ' + REL
      and 'b' in out and out['b'].get('status') != 'ok' and 'c' not in out and out['d']['rule'] == 'terms')
if not ok:
    bad += 1; print('DISAGREE apply_declarations', json.dumps(out)[:400])
print(f'{len(cases)} cases + hook · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
