#!/usr/bin/env python3
"""Harness for the Oracle dry run's page-limit handling (JSA-312, rule 13): DeepSeek cases in
test_cases/oracle_limits_cases.json (from oracle_limits_spec.md, incl. the VERMORGAL 11-11 refusal replay), Claude's verdicts
in oracle_limits_verdicts.json. One row goes through run_oracle's own steps: box_limits → box_plan (rule answers) /
open_drafts (drafts) → page_verdict (the page's marks after the fill); write_questions keeps the page's limit."""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import field_limits as FL
import run_oracle as O
import run_workable as W

cases = json.load(open(os.path.join(HERE, 'test_cases', 'oracle_limits_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'oracle_limits_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
val = lambda v: v['repeat'] * int(v['times']) if isinstance(v, dict) else (v or '')


def run_row(c):
    v, l = val(c['answer']), c.get('limits') or {}
    f = {'kind': c['kind'], 'label': c['label'], 'type': 'text', 'maxlength': None, 'hint': ''}
    lim = FL.merge({'max': l.get('max'), 'min': l.get('min'), 'format': l.get('format'), 'source': 'the page'}, O.box_limits(f))
    lim = lim if (lim['max'] or lim['min'] or lim['format']) else None
    if c['source'] == 'draft':
        _, missing = O.open_drafts([{'key': '1', 'label': c['label'], 'kind': c['kind'], 'maxlength': None, 'limits': lim}], {},
                                   {O.open_id(c['label']): v})
        if missing:
            return 'redraft', missing[0]['limit'], missing[0].get('min')
    else:
        v = FL.fix_url(v, lim, O.clean_label(c['label']), 'text')        # the runner's step before box_plan
        bp = O.box_plan(c['label'], c['kind'], c['required'], {'status': 'ok', 'value': v, 'rule': 'qa:1'}, None, {}, [],
                        {'maxlength': None, 'type': 'text', 'limits': lim})
        if bp and bp['action'] == 'ask':
            return 'stop_ask', None, None
        if bp and bp['action'] == 'leave':
            return 'leave', None, None
    g = {'kind': c['kind'], 'label': c['label'], 'value': v, 'invalid': c.get('page_invalid'), 'page_error': c.get('page_error'), 'limits': lim}
    return ('page_stop' if O.page_verdict({}, g) else 'fill'), None, None


bad = 0
for c in cases:
    got = run_row(c)
    exp = (c['expect'], c.get('expect_limit') if c['expect'] == 'redraft' else None, c.get('expect_min') if c['expect'] == 'redraft' else None)
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', exp, '|', c['label'][:50], '|', repr(val(c['answer'])[:30]))

# questions.json: the page's limit replaces VERMORGAL's guess (1500 → 200), a guess never replaces a known limit
with tempfile.TemporaryDirectory() as d:
    lab = "Would you please share some details about your future career aspirations? Anything you'd like the hiring review team to know when reviewing your candidacy?"
    json.dump([{'id': 'vermorgal_q13', 'label': lab, 'limit': 1500}], open(os.path.join(d, 'questions.json'), 'w'))
    W.write_questions(d, [{'id': O.open_id(lab), 'label': lab, 'limit': 200, 'limit_from': 'platform data', 'redraft': '1086 characters'}])
    q = json.load(open(os.path.join(d, 'questions.json')))
    W.write_questions(d, [{'id': 'vermorgal_q13', 'label': lab, 'limit': 1500, 'limit_from': 'guess'}])
    q2 = json.load(open(os.path.join(d, 'questions.json')))
    if not (len(q) == 1 and q[0]['limit'] == 200 and q[0].get('redraft') and q2[0]['limit'] == 200):
        bad += 1; print('FAIL write_questions keeps the page limit', q, q2)
# the platform's REST answer (recruitingCEQuestions) → limits by prompt
rest = {'items': [{'Prompt': '<p>What is your current degree minor? if applicable.</p>', 'MinimumLength': 5, 'MaximumLength': 50},
                  {'Prompt': lab, 'MinimumLength': None, 'MaximumLength': 200}, {'Prompt': 'Gender', 'MaximumLength': None}]}
t = FL.limits_from_json(rest)
m = FL.lookup('What is your current degree minor? if applicable.', t)
if not (m and m['min'] == 5 and m['max'] == 50 and FL.lookup(lab, t)['max'] == 200 and len(t) == 2):
    bad += 1; print('FAIL limits_from_json', t)
# live shapes (Hunt Oil, 2026-11-11): profile-block metadata (MaximumLength as a string), the name block ('Length'), a
# questionnaire row with no limits (left out), and one prompt in two blocks (tightest wins)
live = {'items': [{'AttributeName': 'Major', 'Prompt': 'Major', 'MaximumLength': '240', 'Type': 'STRING'},
                  {'AttributeName': 'FirstName', 'Prompt': 'First Name', 'Length': '150'},
                  {'Prompt': 'What is your major?', 'MinimumLength': None, 'MaximumLength': None, 'UIDisplayType': 'TextBox'},
                  {'Prompt': 'Status', 'MaximumLength': '240'}, {'Prompt': 'Status', 'MaximumLength': 30}]}
t = FL.limits_from_json(live)
if not (t.get('major', {}).get('max') == 240 and t.get('first name', {}).get('max') == 150 and 'what is your major' not in t
        and t['status']['max'] == 30):
    bad += 1; print('FAIL live REST shapes', t)
print(f'{len(cases)} cases + 3 fixed checks · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
