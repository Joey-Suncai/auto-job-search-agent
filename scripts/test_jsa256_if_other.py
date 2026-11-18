#!/usr/bin/env python3
"""JSA-256 (rule 13): DeepSeek-written cases (test_cases/jsa256_if_other_cases.json, spec …_spec.md) + the real P4 of the 2026-11-09
sheet ("If other, please specify" asked alone, 4 jobs; Nevharpell form fields). Verdicts: jsa256_if_other_verdicts.json.
    python3 scripts/test_jsa256_if_other.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path[:0] = [os.path.join(ROOT, 'skills/auto-apply/runner'), os.path.join(ROOT, 'config')]
import form_prefetch as FP  # noqa: E402
vp = os.path.join(HERE, 'test_cases', 'jsa256_if_other_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa256_if_other_cases.json')))
cases += [
 {'name': 'real_DV_Trading_if_other_after_unanswered_firm_list', 'fields': [
   {'label': 'If yes, select your most recent proprietary trading firm experience', 'type': 'combo', 'options': ['Talkelsev', 'Citadel Securities', 'Other'], 'answer': None},
   {'label': 'If other, please specify', 'type': 'text', 'answer': None}], 'target': 1, 'expect': 'drop'},
 {'name': 'real_if_other_alone_first_field_kept', 'fields': [{'label': 'If other, please specify.', 'type': 'text', 'answer': None}], 'target': 0, 'expect': 'keep'},
 {'name': 'real_how_heard_other_context', 'fields': [
   {'label': 'How did you hear about this job?', 'type': 'select', 'options': ['LinkedIn', 'Other'], 'answer': 'Other'},
   {'label': 'If other, please specify.', 'type': 'text', 'answer': None}], 'target': 1, 'expect': 'keep_with_context',
  'label': 'How did you hear about this job? — you chose Other: If other, please specify.'}]
bad = 0
for c in cases:
    r = FP.other_followup(c['fields'], c['target'])
    got = 'keep' if r is None else r if r == 'drop' else 'keep_with_context'
    ok = got == c['expect'] and (c['expect'] != 'keep_with_context' or r == c.get('label'))
    if not ok and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', r, '| expect', c['expect'], c.get('label', ''), '|', json.dumps(c['fields'], ensure_ascii=False)[:300])
# items_of_plan (review 2026-11-17): the follow-up never keeps a rewritten label; context is its own field
def plan_of(prev_answer, extra=()):
    fs = [{'key': 'a', 'label': 'How did you hear?', 'type': 'combo', 'options': ['X', 'Other'], 'answer': prev_answer}] + list(extra) + \
         [{'key': 'b', 'label': 'If other, please specify', 'type': 'text', 'options': []}]
    nu = [{'key': 'b', 'label': 'If other, please specify', 'options': [], 'required': True, 'why': 'no rule'}]
    if prev_answer is None:
        nu.insert(0, {'key': 'a', 'label': 'How did you hear?', 'options': ['X', 'Other'], 'required': True, 'why': 'no rule'})
    return {'fields': fs, 'needs_user': nu}


def chk(name, ok, *info):
    global bad
    if not ok:
        bad += 1; print('FAIL', name, *info)


items = {i['key']: i for i in FP.items_of_plan(plan_of(None), {}, set())}
chk('unanswered previous: follow-up stays open but deferred (job not ready), question before stays', set(items) == {'a', 'b'} and items['b'].get('deferred') and 'deferred' not in items['a'], items)
items = FP.items_of_plan(plan_of('X'), {}, set())
chk('previous answered X (not Other): follow-up dropped', items == [], items)
items = FP.items_of_plan(plan_of('Other'), {}, set())
chk('previous answered Other: follow-up kept, label unchanged, context separate', len(items) == 1 and items[0]['label'] == 'If other, please specify' and 'you chose Other' in items[0].get('context', '') and not items[0].get('deferred'), items)
items = FP.items_of_plan(plan_of(['X', 'Other']), {}, set())
chk('multi-select answer containing Other keeps the follow-up', len(items) == 1 and 'Other' in items[0].get('context', ''), items)
items = FP.items_of_plan(plan_of('Other', extra=[{'key': 'h', 'label': 'token', 'type': 'hidden'}, {'key': 'f', 'label': 'CV', 'type': 'file'}]), {}, set())
chk('hidden / file fields between do not hide the previous question', len(items) == 1 and 'context' in items[0], items)
print(f'JSA-256: {len(cases) + 5} cases · {len(verdicts)} verdicts · open disagreements {bad}')
sys.exit(1 if bad else 0)
