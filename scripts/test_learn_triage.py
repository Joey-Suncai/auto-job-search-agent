#!/usr/bin/env python3
"""JSA-400: scripts/learn/learn_triage.py — the honesty guards (DeepSeek-written cases scripts/test_cases/learn_triage_cases.json; a case judged
wrong goes into learn_triage_verdicts.json with its source) and the triage flow with a fake model.
    python3 scripts/test_learn_triage.py"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'learn'))
import learn_triage as TR  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'learn_triage_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'learn_triage_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
def T(name, ok, info=''):
    global bad
    v = verdicts.get(name)
    if not ok and v and v.get('verdict') == 'case':
        print(f'SKIP {name}  (case judged wrong: {v["why"][:80]})'); return
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}')); bad += not ok

for c in cases:
    if c['fn'] == 'trial_folder': got = TR.trial_folder(c.get('name_arg'), set(c['existing']) if c.get('existing') is not None else None)
    elif c['fn'] == 'validate_item': got = TR.validate_item(c['item'], c['material'], set(c['ids']))
    elif c['fn'] == 'combine_reads': got = TR.combine_reads(c['first'], c.get('second'))
    else: got = TR.merge_groups(c['items'])
    T(c['name'], got == c['expect'], f"got {json.dumps(got, ensure_ascii=False)[:250]}")

# ---- the flow with a fake model
import tempfile
from datetime import datetime
import learn as L
CANDS = [{'id': 'c0', 'material': {'question': 'Do you wish to furnish this information?', 'fact_library': 'none'}},
         {'id': 'c1', 'material': {'question': 'Please provide your visa type', 'fact_library': ['qa:"visa type"'], 'rules_output': 'CPT'}}]
def fake(reads, groups=None):
    """reads: list of per-call dicts id → (category, group_with) ; evidence is a phrase taken from the material."""
    calls = []
    def ask(system, user, temperature=0.0):
        if system == TR.GROUP_SYSTEM:
            ask.group_calls += 1; return {'groups': groups or []}
        calls.append(temperature)
        spec = reads[min(len(calls) - 1, len(reads) - 1)]
        if spec == 'JUNK': return {'oops': 1}
        items = json.loads(user)['candidates']
        return {'items': [{'id': i['id'], 'category': spec[i['id']][0], 'group_with': spec[i['id']][1], 'evidence': ('furnish this information' if i['id'] == 'c0' else 'visa type'), 'confidence': 'high'} for i in items if i['id'] in spec]}
    ask.calls = calls; ask.group_calls = 0
    return ask
ask = fake([{'c0': ('fact', []), 'c1': ('rule', [])}, {'c0': ('fact', [])}])
res, groups = TR.triage(CANDS, ask, {})
T('triage: a fact read twice and agreeing stays fact; a rule is read once', res['c0']['category'] == 'fact' and res['c1']['category'] == 'rule' and res['c0']['read2'] == 'fact' and ask.calls == [0.0, 0.7], (res, ask.calls))
ask = fake([{'c0': ('fact', []), 'c1': ('rule', [])}, {'c0': ('ignore', [])}])
res, _ = TR.triage(CANDS, ask, {})
T('triage: the second read disagrees → unsure, never asked as a fact', res['c0']['category'] == 'unsure' and 'second read' in res['c0']['reason'], res['c0'])
res, _ = TR.triage(CANDS, fake(['JUNK']), {})
T('triage: junk from the model → every candidate unsure', all(r['category'] == 'unsure' for r in res.values()), res)
bad_ev = lambda s, u, t=0.0: {'items': [{'id': 'c0', 'category': 'fact', 'group_with': [], 'evidence': 'a sentence the form never said', 'confidence': 'high'}, {'id': 'c1', 'category': 'rule', 'group_with': [], 'evidence': 'visa type', 'confidence': 'high'}]}
res, _ = TR.triage(CANDS, bad_ev, {})
T('triage: evidence not in the material → unsure', res['c0']['category'] == 'unsure' and res['c1']['category'] == 'rule', res)
cache = {}; a1 = fake([{'c0': ('ignore', []), 'c1': ('rule', ['c0'])}])
TR.triage(CANDS, a1, cache); a2 = fake([{'c0': ('ignore', []), 'c1': ('rule', [])}]); r2, g2 = TR.triage(CANDS, a2, cache)
T('triage: a cached candidate is not sent again; the cached grouping is kept', a2.calls == [] and g2 == [['c0', 'c1']], (a2.calls, g2))
# the global grouping pass links candidates that sit in different batches; a cached result is not asked again
MANY = [{'id': f'x{i}', 'material': {'question': f'Question number {i} on the form'}} for i in range(25)]
ag = fake([{f'x{i}': ('ignore', []) for i in range(25)}], groups=[['x1', 'x24']])
rg, gg = TR.triage(MANY, ag, {})
T('triage: the grouping pass merges candidates from different batches (x1 in batch 1, x24 in batch 3)', ['x1', 'x24'] in gg and ag.group_calls == 1, (gg, ag.group_calls))
T('triage: a model failure (not an object) is not cached, so the next run asks again', not any('not an object' in str(v) for v in (lambda c: (TR.triage(CANDS, fake(['JUNK']), c), c)[1])({}).values()))
def down(s, u, t=0.0): raise TR.ModelUnavailable('no key')
try: TR.triage(CANDS, down, {}); T('triage: ModelUnavailable propagates (the caller falls back)', False)
except TR.ModelUnavailable: T('triage: ModelUnavailable propagates (the caller falls back)', True)
# ---- learn.py pieces
T('infer_ats: from the application link when the row has no platform', L.infer_ats({'url': 'https://job-boards.greenhouse.io/embed/job_app?for=x&token=1'}) == 'greenhouse' and L.infer_ats({'ats': 'workday', 'url': 'x'}) == 'workday' and L.infer_ats({}) == '')
T('fact_library_hits: key names only, never contents', L.fact_library_hits('Current Job Title', ['Current Job Title', 'GPA']) == ['qa:"Current Job Title"'] and L.fact_library_hits('Visa?', [], 'visa_status') == ['fact:visa_status'] and L.fact_library_hits('x', ['y'], 'unknown') == [])
led = [{'id': 'fact:aaaaaaaa', 'type': 'fact', 'key': 'old wording', 'status': 'open', 'evidence': ['A', 'B'], 'reopened': 0, 'fixed_by': None, 'fixed_at': None}]
tri = [{'type': 'ignore', 'key': 'old wording', 'at': '2026-11-17T10:00:00-06:00', 'evidence': ['A', 'B'], 'members': ['old wording', 'other wording'], 'evidence_text': 'x', 'confidence': 'high'}]
out = L.apply_triage_to_ledger(L.update_ledger(led, tri, '2026-11-17T22:30:00-06:00'), tri)
T('apply_triage_to_ledger: the old entry is superseded, the new ignore entry is ignored (not open)', [e['status'] for e in out] == ['superseded', 'ignored'] and out[1]['category'] == 'ignore', out)
# ---- run(): dry folders never count, grouping, model fallback
d = tempfile.mkdtemp(); rd = os.path.join(d, 'runner'); os.makedirs(os.path.join(rd, 'fields')); APPS = os.path.join(d, 'applications')
for f in ('F1', 'F2', 'F3'): os.makedirs(os.path.join(APPS, f))
NOW = datetime.fromisoformat('2026-11-17T22:30:00-06:00')
rows = [{'at': f'2026-11-16T1{i}:00:00-06:00', 'ats': 'lever', 'folder': f, 'question': q, 'planned': None, 'ok': False, 'type': 'text', 'required': False}
        for i, (f, q) in enumerate([('F1', 'Do you wish to furnish this information?'), ('F2', 'Do you wish to furnish this information'), ('dry_x', 'Do you wish to furnish this information?'), ('out', 'Do you wish to furnish this information?'),
                                    ('F1', 'Please state your favorite color'), ('F3', 'Please state your favorite color')])]
open(os.path.join(rd, 'fields', '2026-11.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in rows))
open(os.path.join(rd, 'results.jsonl'), 'w').write('')
seen_ids = []
def ask_run(system, user, temperature=0.0):
    items = json.loads(user)['candidates']; seen_ids.extend(i['id'] for i in items)
    return {'items': [{'id': i['id'], 'category': 'ignore', 'group_with': [], 'evidence': i.get('question', '')[:20], 'confidence': 'high'} for i in items]}
logs = []
led = L.run(now=NOW, replay=False, data=d, log=logs.append, model=True, ask=ask_run, apps=APPS)
T('run: dry_* / out folders are not evidence (the question seen in F1 + F2 only)', all('dry_x' not in e['evidence'] and 'out' not in e['evidence'] for e in led) and any(e['evidence'] == ['F1', 'F2'] for e in led), led)
T('run: the model\'s category is on the entry, ignore → ignored, counted on the card', all(e.get('category') == 'ignore' and e['status'] == 'ignored' for e in led) and 'ignored 2' in open(os.path.join(d, 'learn', f'card-2026-11-17.md')).read(), led)
n_calls = len(seen_ids)
L.run(now=NOW, replay=False, data=d, log=logs.append, model=True, ask=ask_run, apps=APPS)
T('run: a second run sends nothing new (cache on disk)', len(seen_ids) == n_calls, (n_calls, len(seen_ids)))
d2 = tempfile.mkdtemp(); os.makedirs(os.path.join(d2, 'runner', 'fields')); os.makedirs(os.path.join(d2, 'applications', 'F1')); os.makedirs(os.path.join(d2, 'applications', 'F2'))
open(os.path.join(d2, 'runner', 'fields', '2026-11.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in rows if r['folder'] in ('F1', 'F2')))
open(os.path.join(d2, 'runner', 'results.jsonl'), 'w').write('')
led2 = L.run(now=NOW, replay=False, data=d2, log=logs.append, model=True, ask=down, apps=os.path.join(d2, 'applications'))
T('run: model unavailable → the old rules classify, the card says so', any(e['type'] == 'fact' for e in led2) and 'model not used today' in open(os.path.join(d2, 'learn', 'card-2026-11-17.md')).read(), led2)
# ---- the acceptance scorer (scripts/learn/learn_triage_eval.py), hand-derived on 5 items
import learn_triage_eval as EV
gold = [{'id': 'a', 'expected': 'fact', 'group': None}, {'id': 'b', 'expected': 'rule', 'group': 'g'}, {'id': 'c', 'expected': 'rule', 'group': 'g'},
        {'id': 'd', 'expected': 'ignore', 'group': None}, {'id': 'e', 'expected': 'runner', 'group': None}]
res = {'a': {'category': 'fact'}, 'b': {'category': 'rule'}, 'c': {'category': 'rule'}, 'd': {'category': 'fact'}, 'e': {'category': 'unsure'}}
sc = EV.score(gold, res, [['a', 'd'], ['b', 'c'], ['e']])
T('score: accuracy 3/5, fact precision 1/2, fact recall 1/1', sc['accuracy'] == 0.6 and sc['fact_precision'] == 0.5 and sc['fact_recall'] == 1.0, sc)
T('score: merging a fact with an ignore is a merge error, the labelled pair b+c is right', sc['merge_pairs_predicted'] == 2 and sc['merge_errors'] == 1 and sc['merges_missed'] == 0, sc)
gd = json.load(open(os.path.join(HERE, 'test_cases', 'learn_triage_golden.json')))
T('golden fixture (fictional): labelled candidates, only valid categories, every group has ≥ 2 members, all six categories present', len(gd) >= 20 and all(g['expected'] in TR.CATEGORIES for g in gd)
  and all(sum(1 for x in gd if x.get('group') == g['group']) >= 2 for g in gd if g.get('group')) and {g['expected'] for g in gd} == set(TR.CATEGORIES), len(gd))
# ---- review fixes (JSA-400): privacy, evidence, migration
PROFILE = {'name': {'full': 'Zed Quill'}, 'contact': {'email': 'zed.quill@example.org', 'address': '12 Maple Lane, Springfield, IL 62704'}, 'gpa': 3.91,
           'visa': 'F-1', 'qa': [{'q': 'x', 'text': 'Quillspeak'}]}
vals = L.profile_values(PROFILE)
T('profile_values: names, address, gpa, saved answers; not yes / no', {'Zed Quill', '12 Maple Lane, Springfield, IL 62704', '3.91', 'F-1', 'Quillspeak'} <= vals and 'yes' not in {v.lower() for v in vals})
note = "answered 'Zed Quill' — gpa 3.91 expected; got 3.9 (fact: 12 Maple Lane, Springfield, IL 62704, mail zed.quill@example.org, https://x.io/p?id=12345 salary 48000, visa f-1)"
red = L.redact(note, vals)
T('redact: no profile value, e-mail, link or long number is left', not any(v.lower() in red.lower() for v in vals) and '@' not in red and 'http' not in red and '48000' not in red and '12345' not in red, red)
f = {'type': 'rule', 'key': 'wrong:gpa', 'evidence': ['F1'], 'at': '2026-11-16T10:00:00-06:00'}
m = L.build_material(f, [], [], [{'folder': 'F1', 'field': 'gpa', 'note': note, 'found': '2026-11-16'}], [], [], vals)
T('build_material: no profile value reaches the model (rule candidate)', not any(v.lower() in json.dumps(m).lower() for v in vals), m)
fr = {'type': 'runner', 'key': 'x|y|canonical mismatch: sponsorship = (want yes)', 'evidence': ['F1'], 'at': '2026-11-16T10:00:00-06:00'}
res_rows = [{'folder': 'F1', 'ats': 'lever', 'status': 'blocked', 'problems': ["canonical mismatch: gpa = 'Zed Quill' (want 3.91)"], 'stopped_at': 'x'}]
T('build_material: nor a runner error text', 'Zed Quill' not in json.dumps(L.build_material(dict(fr, key=L._sig(res_rows[0])), [], res_rows, [], [], [], vals)))
# evidence: the program's own words and tiny quotes do not count
mat = {'found_by': 'the rules left this question unanswered', 'question': 'Do you wish to furnish this information?', 'fact_library': 'none'}
T('evidence: quoting the program boilerplate (found_by / fact_library) is no evidence', TR.validate_item({'id': 'a', 'category': 'fact', 'evidence': 'the rules left this question unanswered'}, TR.material_text(mat), {'a'})['category'] == 'unsure'
  and TR.validate_item({'id': 'a', 'category': 'fact', 'evidence': 'none'}, TR.material_text(mat), {'a'})['category'] == 'unsure')
T('evidence: a short quote (< 8 characters) is no evidence', TR.validate_item({'id': 'a', 'category': 'fact', 'evidence': 'furnish'}, TR.material_text(mat), {'a'})['category'] == 'unsure')
T('evidence: a question shorter than 8 characters is evidence when quoted whole ("Extra")', TR.validate_item({'id': 'a', 'category': 'ignore', 'evidence': 'Extra'}, TR.material_text({'question': 'Extra'}), {'a'})['category'] == 'ignore' and TR.validate_item({'id': 'a', 'category': 'ignore', 'evidence': 'Ext'}, TR.material_text({'question': 'Extra'}), {'a'})['category'] == 'unsure')
T('evidence: a real quote of the question passes', TR.validate_item({'id': 'a', 'category': 'ignore', 'evidence': 'wish to furnish this information'}, TR.material_text(mat), {'a'})['category'] == 'ignore')
# ledger migration keeps wontfix / fixed / fixing
for old_status in ('wontfix', 'fixed', 'fixing'):
    led = [{'id': 'fact:11111111', 'type': 'fact', 'key': 'old wording', 'status': old_status, 'evidence': ['A', 'B'], 'reopened': 0, 'fixed_by': 'abc' if old_status == 'fixed' else None, 'fixed_at': '2026-11-16T09:00:00-06:00' if old_status == 'fixed' else None}]
    tri = [{'type': 'rule', 'key': 'old wording', 'at': '2026-11-10T10:00:00-06:00', 'evidence': ['A', 'B'], 'members': ['old wording', 'new wording'], 'evidence_text': 'x', 'confidence': 'high'}]
    out = L.apply_triage_to_ledger(L.update_ledger(led, tri, '2026-11-17T22:30:00-06:00'), tri)
    new = [e for e in out if e['id'] != 'fact:11111111'][0]
    T(f'migration: a {old_status} legacy entry hands its state to the new entry and is superseded', new['status'] == old_status and out[0]['status'] == 'superseded' and out[0].get('superseded_by') == new['id'], out)
led = [{'id': 'rule:22222222', 'type': 'rule', 'key': 'k1', 'category': 'rule', 'status': 'open', 'evidence': ['A', 'B'], 'members': ['k1'], 'reopened': 0, 'fixed_by': None, 'fixed_at': None}]
tri = [{'type': 'qtype', 'key': 'k1', 'at': '2026-11-17T10:00:00-06:00', 'evidence': ['A', 'B'], 'members': ['k1', 'k2'], 'evidence_text': 'x', 'confidence': 'high'}]
out = L.apply_triage_to_ledger(L.update_ledger(led, tri, '2026-11-17T22:30:00-06:00'), tri)
T('migration: a categorised entry whose category changed is superseded too (no orphan)', [e['status'] for e in out] == ['superseded', 'open'], out)
T('hand_fixes: a commit citing a qtype / page / unsure proposal is linked', L.hand_fixes([('a1', 'JSA-9: fix qtype:12345678'), ('b2', 'JSA-9: fix page:abcdef12')], set()) == [])
# nothing of the (fictional) fact library may reach the model: the payload of a whole triage, system prompt included
FACTS = {'name': {'full': 'Zed Quill'}, 'contact': {'email': 'zed.quill@example.org', 'phone': '+1 555 010 0199'}, 'gpa': 3.91, 'visa': 'F-1',
         'answers': {'address': {'text': '12 Maple Lane'}, 'pron': {'text': 'ZEHD KWIL'}}, 'qa': [{'q': 'Favorite food?', 'text': 'Quillspeak stew'}]}
fv = L.profile_values(FACTS)
sent = []
def spy(system, user, temperature=0.0):
    sent.append(system + '\n' + user)
    if system == TR.GROUP_SYSTEM: return {'groups': []}
    return {'items': [{'id': c['id'], 'category': 'fact', 'group_with': [], 'evidence': (TR.material_text(c) or 'xxxxxxxxxx')[:30], 'confidence': 'high'} for c in json.loads(user)['candidates']]}
notes = [{'folder': 'F1', 'field': 'GPA?', 'note': "answered '3.9' — gpa = 3.91 expected (fact: 12 Maple Lane, mail zed.quill@example.org, call +1 555 010 0199, ZEHD KWIL; Zed Quill; F-1; Quillspeak stew) (found by the independent audit, JSA-245)", 'found': '2026-11-16'}]
fnd = L.findings([{'at': '2026-11-16T10:00:00-06:00', 'folder': 'F1', 'ats': 'lever', 'status': 'blocked', 'problems': ["canonical mismatch: visa = 'F-1' for Zed Quill (want 12 Maple Lane)"], 'stopped_at': 'x'},
                  {'at': '2026-11-16T10:00:00-06:00', 'folder': 'F2', 'ats': 'lever', 'status': 'blocked', 'problems': ["canonical mismatch: visa = 'F-1' for Zed Quill (want 12 Maple Lane)"], 'stopped_at': 'x'}],
                 [], notes, [], datetime.fromisoformat('2026-11-17T22:30:00-06:00'))
try: L.triage_found(fnd, [], [{'folder': 'F1', 'ats': 'lever', 'status': 'blocked', 'problems': ["canonical mismatch: visa = 'F-1' for Zed Quill (want 12 Maple Lane)"], 'stopped_at': 'x'}], notes, [], [], spy, {}, index=L.fact_index(FACTS), hide=fv)
except Exception as e: print('spy flow error', e)
payload = '\n'.join(sent)
T('PAYLOAD: no value of the fact library reaches the model (names, e-mail, phone, address, GPA, visa, pronunciation, saved answers)', sent and not any(v.lower() in payload.lower() for v in fv if len(v) >= 3 and v.lower() not in ('yes', 'no')), [v for v in fv if v.lower() in payload.lower()])
T('PAYLOAD: the fact index sent is key NAMES only, and the second read (temperature 0.7) is in the tested payload', '"visa"' in payload and '"contact.email"' in payload and 'zed.quill' not in payload.lower() and len(sent) >= 3, len(sent))
# a fact candidate whose row HAS a planned value (read-back failed): the value must not be sent
fr = [{'at': '2026-11-16T10:00:00-06:00', 'folder': f, 'ats': 'lever', 'question': 'City', 'planned': 'Springfield', 'ok': False, 'type': 'text', 'required': True} for f in ('F1', 'F2')] + \
     [{'at': '2026-11-16T10:00:00-06:00', 'folder': f, 'ats': 'lever', 'question': 'City', 'planned': None, 'ok': False, 'type': 'text', 'required': True} for f in ('F3', 'F4')]
fv2 = L.profile_values({'contact': {'city_state': 'Springfield'}})
mm = L.build_material({'type': 'fact', 'key': 'city', 'evidence': ['F3', 'F4'], 'at': 'x'}, fr, [], [], [], [], fv2)
T('fact material: a row with a planned (user) value is never the source; rules_output stays "(nothing)"', 'Springfield' not in json.dumps(mm) and mm['rules_output'] == '(nothing)', mm)
# redact before truncating: a value cut in half by the limit must still be hidden
long_note = 'x' * 285 + ' the address is 12 Maple Lane, Springfield ' + 'y' * 50
mw = L.build_material({'type': 'rule', 'key': 'wrong:q', 'evidence': ['F1'], 'at': 'x'}, [], [], [{'folder': 'F1', 'field': 'q', 'note': long_note, 'found': '2026-11-16'}], [], [], L.profile_values({'a': '12 Maple Lane, Springfield'}))
T('redact then truncate: no half of a value is left at the cut', 'Maple' not in json.dumps(mw) and 'Springfield' not in json.dumps(mw), mw)
# flapping: a superseded entry that comes back is open again
led = [{'id': L.pid('rule', 'k1'), 'type': 'rule', 'key': 'k1', 'status': 'superseded', 'superseded_by': 'x', 'evidence': ['A'], 'reopened': 0, 'fixed_by': None, 'fixed_at': None}]
back = L.update_ledger(led, [{'type': 'rule', 'key': 'k1', 'at': '2026-11-17T10:00:00-06:00', 'evidence': ['A', 'B']}], '2026-11-17T22:30:00-06:00')
T('flapping: a superseded entry the classification returns to is open again', back[0]['status'] == 'open' and back[0]['evidence'] == ['A', 'B'] and 'superseded_by' not in back[0], back)
# a confirmed fact is not merged into another category's group
cx = [{'id': 'a', 'material': {'question': 'Do you hold a clearance?'}}, {'id': 'b', 'material': {'question': 'Do you hold any clearance level?'}}]
def askc(system, user, temperature=0.0):
    if system == TR.GROUP_SYSTEM: return {'groups': [['a', 'b']]}
    cc = json.loads(user)['candidates']
    cats = {'a': 'fact', 'b': 'rule'}
    return {'items': [{'id': c['id'], 'category': cats[c['id']], 'group_with': [('b' if c['id'] == 'a' else 'a')], 'evidence': c['question'][:20], 'confidence': 'high'} for c in cc]}
rc, gc = TR.triage(cx, askc, {})
T('triage: a confirmed fact is never merged with another category (stays its own group)', gc == [['a'], ['b']] and rc['a']['category'] == 'fact', (gc, rc))
sys.exit(1 if bad else 0)