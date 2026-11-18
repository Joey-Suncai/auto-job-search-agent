#!/usr/bin/env python3
"""Harness for the page-limit check (JSA-312, rule 13): DeepSeek cases in test_cases/field_limits_cases.json (written from
field_limits_spec.md, never from the code), Claude's verdicts in field_limits_verdicts.json. Each case runs through the
three runners' own limit readers — Oracle (run_oracle.box_limits, with the platform's question data), Workday
(run_wd.box_limits) and SuccessFactors (run_successfactors.limit_gate, attributes only) — and field_limits.check."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import field_limits as FL
import run_oracle as O
import run_wd as WD
import run_successfactors as SF

cases = json.load(open(os.path.join(HERE, 'test_cases', 'field_limits_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'field_limits_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}


def val(v):
    return v['repeat'] * int(v['times']) if isinstance(v, dict) else (v or '')


bad = 0
for c in cases:
    v = val(c.get('value'))
    kind = 'textarea'
    f = {'kind': kind, 'type': c.get('input_type') or '', 'label': c['label'], 'maxlength': c.get('maxlength'),
         'minlength': c.get('minlength'), 'hint': c.get('hint') or ''}
    ql = {FL.norm_prompt(c['label']): dict(c['platform'], format=None, pattern=None, source='platform data')} if c.get('platform') else {}
    lim = O.box_limits(f, ql)
    got = {'oracle': FL.check(v, lim, O.clean_label(c['label']))}
    wf = {'type': 'textarea', 'label': c['label'], 'maxlength': c.get('maxlength'), 'minlength': c.get('minlength'),
          'input_type': c.get('input_type') or '', 'hint': (c.get('hint') or '') + (
              f" maximum of {c['platform']['max']} characters" if (c.get('platform') or {}).get('max') else '') + (
              f" at least {c['platform']['min']} characters" if (c.get('platform') or {}).get('min') else ''),
          'status': 'ok', 'answer': v, 'key': 'k', 'required': True}
    out, needs = WD.limit_gate([wf], 'step')
    got['workday'] = out[0].get('limit_fail')
    exp = c['expect']
    for who, g in got.items():
        if g != exp and f"{c['name']}|{who}" not in verdicts and c['name'] not in verdicts:
            bad += 1; print('DISAGREE', who, c['name'], '| got', g, '| expect', exp, '|', c['label'][:60], '|', repr(v[:40]), len(v.strip()))
    # SuccessFactors reads attributes / type / label only (no hint): judged when the case has no hint and no platform data
    if not c.get('hint') and not c.get('platform'):
        sf = {'key': 'k', 'type': 'textarea', 'label': c['label'], 'maxlength': c.get('maxlength'), 'minlength': c.get('minlength'),
              'input_type': c.get('input_type') or ''}
        a = SF.limit_gate([sf], {'k': {'status': 'ok', 'value': v}})['k']
        sg = 'stopped' if a['status'] != 'ok' else None
        if (sg is None) != (exp is None) and f"{c['name']}|sf" not in verdicts and c['name'] not in verdicts:
            bad += 1; print('DISAGREE sf', c['name'], '| stopped' if sg else '| passed', '| expect', exp)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
