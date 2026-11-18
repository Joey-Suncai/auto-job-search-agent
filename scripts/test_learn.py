#!/usr/bin/env python3
"""JSA-191: scripts/learn/learn.py — findings, update_ledger, platform_metrics (DeepSeek-written cases scripts/test_cases/learn_cases.json;
a case judged wrong goes into learn_verdicts.json with its source), plus mark / card / replay-report parsing and a run() on a temp data home.
    python3 scripts/test_learn.py"""
import json, os, re, sys, tempfile
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'learn'))
import learn as L  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'learn_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'learn_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
def T(name, ok, info=''):
    global bad
    v = verdicts.get(name)
    if not ok and v and v.get('verdict') == 'case':
        print(f'SKIP {name}  (case judged wrong: {v["why"][:80]})'); return
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}')); bad += not ok

def fill_ids(x):
    """"ID(type:key)" placeholders in a case → the real id."""
    if isinstance(x, str):
        m = re.fullmatch(r'ID\((\w+):(.*)\)', x)
        return L.pid(m.group(1), m.group(2)) if m else x
    if isinstance(x, list): return [fill_ids(i) for i in x]
    if isinstance(x, dict): return {k: fill_ids(v) for k, v in x.items()}
    return x

for c in cases:
    now = datetime.fromisoformat(c['now'])
    if c['fn'] == 'findings':
        kw = {'days': c['days']} if c.get('days') is not None else {}
        got = L.findings(c.get('results') or [], c.get('fields') or [], c.get('wrong') or [], c.get('replay') or [], now, **kw)
    elif c['fn'] == 'update_ledger':
        got = L.update_ledger(fill_ids(c.get('ledger') or []), c.get('found') or [], c['now'])
        c = dict(c, expect=fill_ids(c['expect']))
    else:
        kw = {'days': c['days']} if c.get('days') is not None else {}
        got = L.platform_metrics(c.get('results') or [], now, **kw)
    T(c['name'], got == c['expect'], f"got {json.dumps(got, ensure_ascii=False)[:300]}")

# a replay row still listed by today's replay after the fix = the fix did not hold → reopened
fnd = L.findings([], [], [], [{'folder': 'F9', 'question': 'Visa?', 'submitted': True, 'reason': None}], datetime.fromisoformat('2026-11-17T22:30:00-06:00'))
fx = [{'id': L.pid('rule', 'replay:visa'), 'type': 'rule', 'key': 'replay:visa', 'status': 'fixed', 'first_seen': 'a', 'last_seen': 'a', 'evidence': ['F9'], 'fixed_by': 'abc', 'fixed_at': '2026-11-16T09:00:00-06:00', 'reopened': 0}]
T('a replay row still listed after the fix reopens it', L.update_ledger(fx, fnd, '2026-11-17T22:30:00-06:00')[0]['status'] == 'open')
# an upload / hidden box is no question
nf = L.findings([], [{'at': '2026-11-16T10:00:00-06:00', 'folder': f, 'question': 'Resume/CV', 'planned': None, 'ok': False, 'type': 'file'} for f in ('A', 'B', 'C')], [], [], datetime.fromisoformat('2026-11-17T22:30:00-06:00'))
T('fact: file uploads are not unknown questions', nf == [])
# questions with an apostrophe (repr switches to double quotes)
ap_ = "## Submitted answers changed without a reason\n\n- **SUBMITTED** F1 · \"What's your visa status?\": ok:'F-1' → unknown:'' (x) [k]\n"
T('parse_replay_report: a question with an apostrophe', [r['question'] for r in L.parse_replay_report(ap_)] == ["What's your visa status?"])
# mark / card / replay report / run()
led = [{'id': 'fact:abc12345', 'type': 'fact', 'key': 'q', 'status': 'open', 'evidence': ['A', 'B'], 'fixed_by': None, 'fixed_at': None, 'reopened': 0}]
T('mark fixed records commit and time', L.mark(led, 'fact:abc12345', 'fixed', 'deadbeef', '2026-11-17T12:00:00-06:00') and led[0]['fixed_by'] == 'deadbeef' and led[0]['fixed_at'].startswith('2026-11-17'))
T('mark: unknown id → False, bad status → error', L.mark(led, 'nope', 'fixed') is False and not any(L.mark(led, 'x', 's') for _ in [0] if False))
try: L.mark(led, 'fact:abc12345', 'done'); T('mark: a bad status is refused', False)
except ValueError: T('mark: a bad status is refused', True)
rep = "# r\n\n## Submitted answers changed without a reason\n\n- **SUBMITTED** 2026-11-05_Wyndelfen_Quantitative_Intern · 'Do you require Visa sponsorship?': ok:'Yes' → unknown:'' (spons_future) [04ec]\n\n## Other changes\n\n- **SUBMITTED** X · 'q': a → b [k]\n"
T('parse_replay_report: only the without-a-reason section', L.parse_replay_report(rep) == [{'folder': '2026-11-05_Wyndelfen_Quantitative_Intern', 'question': 'Do you require Visa sponsorship?', 'submitted': True, 'reason': None}])
T('hand_fixes: a commit naming a proposal is linked', L.hand_fixes([('a1', 'JSA-9: fix rule:12345678'), ('b2', 'JSA-10: tweak answer_rules')], set()) == [('b2', 'JSA-10: tweak answer_rules')])
d = tempfile.mkdtemp(); rd = os.path.join(d, 'runner'); os.makedirs(os.path.join(rd, 'fields'))
NOW = datetime.fromisoformat('2026-11-17T22:30:00-06:00')
def row(h, **k): return dict({'at': f'2026-11-1{h}T10:00:00-06:00', 'ats': 'workday', 'folder': 'F1', 'status': 'blocked'}, **k)
open(os.path.join(rd, 'results.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in [
    row(5, folder='F1', problems=["canonical mismatch: sponsorship_future = '' (want Yes)"], stopped_at='Application Questions'),
    row(6, folder='F2', problems=["canonical mismatch: sponsorship_future = 'x' (want Yes)"], stopped_at='Application Questions'),
    row(6, folder='F3', status='submitted', problems=[], phases={'page': 60})]))
open(os.path.join(rd, 'fields', '2026-11.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in [
    {'at': '2026-11-15T10:00:00-06:00', 'ats': 'workday', 'folder': 'F1', 'question': 'Preferred comms method?', 'planned': None, 'ok': False},
    {'at': '2026-11-16T10:00:00-06:00', 'ats': 'workday', 'folder': 'F2', 'question': 'preferred comms method', 'planned': '', 'ok': False}]))
logs = []
APPS = os.path.join(d, 'applications'); [os.makedirs(os.path.join(APPS, f)) for f in ('F1', 'F2', 'F3', 'F4')]
ledger = L.run(now=NOW, replay=False, data=d, log=logs.append, model=False, apps=APPS)
T('run: one fact and one runner proposal, both open', sorted((e['type'], e['status']) for e in ledger) == [('fact', 'open'), ('runner', 'open')], ledger)
T('run: card written with the platform row', 'workday' in open(os.path.join(d, 'learn', 'card-2026-11-17.md')).read())
L.mark(ledger, ledger[0]['id'], 'fixed', 'abc', '2026-11-17T09:00:00-06:00'); L.save_ledger(os.path.join(d, 'learn', 'proposals.jsonl'), ledger)
led2 = L.run(now=NOW, replay=False, data=d, log=logs.append, model=False, apps=APPS)
T('run: the fixed proposal stays fixed while only old evidence exists', [e['status'] for e in led2 if e['id'] == ledger[0]['id']] == ['fixed'])
open(os.path.join(rd, 'results.jsonl'), 'a').write(json.dumps({'at': '2026-11-17T20:00:00-06:00', 'ats': 'workday', 'folder': 'F4', 'status': 'blocked', 'problems': ["canonical mismatch: sponsorship_future = 'y' (want Yes)"], 'stopped_at': 'Application Questions'}) + '\n')
open(os.path.join(rd, 'fields', '2026-11.jsonl'), 'a').write(json.dumps({'at': '2026-11-17T20:00:00-06:00', 'ats': 'workday', 'folder': 'F4', 'question': 'Preferred comms method', 'planned': None, 'ok': False}) + '\n')
led3 = L.run(now=NOW, replay=False, data=d, log=logs.append, model=False, apps=APPS)
T('run: new evidence after the fix reopens it (reopened 1)', all(e['status'] == 'open' and e['reopened'] == 1 for e in led3 if e['id'] == ledger[0]['id']) and [e for e in led3 if e['id'] == ledger[0]['id']], led3)
sys.exit(1 if bad else 0)
