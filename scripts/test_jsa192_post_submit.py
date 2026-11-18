#!/usr/bin/env python3
"""JSA-192 (rule 13): DeepSeek-written cases (test_cases/jsa192_post_submit_cases.json, spec …_spec.md) for learn/post_submit.proposals /
overdue, plus a run() on a temp data home (proposal file written, nothing written to the profile). Verdicts: jsa192_post_submit_verdicts.json.
    python3 scripts/test_jsa192_post_submit.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'learn'))
import post_submit as PS  # noqa: E402
vp = os.path.join(HERE, 'test_cases', 'jsa192_post_submit_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa192_post_submit_cases.json')))
bad = 0
for c in cases:
    got = PS.proposals(c['lines'], c['items'], c.get('covered') or []) if c['kind'] == 'proposals' else PS.overdue(c['items'], c['today'])
    if c['kind'] == 'proposals':
        got = [{k: p[k] for k in (('question', 'answer', 'options', 'folders', 'n') if p.get('options') else ('question', 'answer', 'folders', 'n'))} for p in got]
    exp = [{k: v for k, v in e.items() if not (k == 'options' and not v)} for e in c['expect']]
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got)[:300], '| expect', json.dumps(c['expect'])[:300])
n = len(cases)


def check(name, ok, *info):
    global bad, n
    n += 1
    if not ok:
        bad += 1; print('FAIL', name, *info)


# run() on a temp data home: 3 audited-right ds_answers forms → one proposal, profile untouched
home = tempfile.mkdtemp(prefix='jsa192_')
for d in ('config', 'data/runner/audit', 'data/runner/fields'):
    os.makedirs(os.path.join(home, d))
base = json.load(open(os.path.join(HERE, '..', 'config', 'profile.example.json'))); base['qa'] = []
pj = os.path.join(home, 'config', 'profile.json'); json.dump(base, open(pj, 'w'))
before = open(pj).read()
Q = 'Which of these best describes your remote work preference zzq?'
with open(os.path.join(home, 'data/runner/fields/2026-11.jsonl'), 'w') as f:
    for i in range(3):
        f.write(json.dumps({'folder': f'F{i}', 'question': Q, 'planned': 'Hybrid', 'page': 'Hybrid', 'source': 'ds_answers.json', 'ok': True, 'options': []}) + '\n')
with open(os.path.join(home, 'data/runner/audit/items.jsonl'), 'w') as f:
    for i in range(3):
        f.write(json.dumps({'folder': f'F{i}', 'question': Q, 'answer': 'Hybrid', 'check': 'right', 'judged': None, 'audited': '2026-11-10'}) + '\n')
    f.write(json.dumps({'folder': 'F9', 'question': 'Doubt?', 'answer': 'x', 'check': 'unsure', 'judged': None, 'audited': '2026-11-10'}) + '\n')
os.environ['JSA_HOME'] = home
import importlib, paths
importlib.reload(paths)
PS.run('2026-11-17')
props = [json.loads(l) for l in open(os.path.join(home, 'data/runner/audit/qa_proposals.jsonl'))]
md = open(os.path.join(home, 'data/runner/audit/qa_proposals.md')).read()
check('run: one proposal, status open', len(props) == 1 and props[0]['n'] == 3 and props[0]['status'] == 'open', props)
PS.run('2026-11-18')
props2 = [json.loads(l) for l in open(os.path.join(home, 'data/runner/audit/qa_proposals.jsonl'))]
check('run again: state carries over, first_seen kept', props2[0]['first_seen'] == '2026-11-17', props2)
check('run: the md carries the qa_add command and the overdue doubt', 'qa_add.py' in md and 'Doubt?' in md, md)
check('run: nothing is written to the profile', open(pj).read() == before)
# review fixes (2026-11-17): risky classes are never proposed, three roles at one company are one witness, the printed command is shell-quoted
check('risky: sponsorship / EEO / contact never proposed', PS.risky('Will you now or in the future require sponsorship?') and PS.risky('What is your gender?') and not PS.risky('Preferred work arrangement zzq?'))
L3 = [{'folder': f'2026-11-1{i}_Acme_Role{i}', 'question': 'Q zz?', 'planned': 'A', 'page': 'A', 'source': 'ds_answers.json', 'ok': True} for i in range(3)]
I3 = [{'folder': l['folder'], 'question': 'Q zz?', 'check': 'right', 'judged': None} for l in L3]
check('three roles at one company are one witness', PS.proposals(L3, I3) == [])
L3b = [dict(l, folder=f'2026-11-1{i}_Co{i}_Role') for i, l in enumerate(L3)]
check('three companies are three witnesses', len(PS.proposals(L3b, [dict(i, folder=l['folder']) for i, l in zip(I3, L3b)])) == 1)
import shlex
check('shlex quoting keeps $() inert', shlex.split(shlex.quote('x $(rm -rf ~) `id` "q"')) == ['x $(rm -rf ~) `id` "q"'])
# run_daily.post_submit: both steps run, a failure of one never raises and shows in the line
sys.path.insert(0, os.path.join(HERE, 'daily'))
import types, run_daily as RD  # noqa: E402
calls = []
def fake(cmd, **k):
    calls.append(os.path.basename(cmd[1]))
    return types.SimpleNamespace(returncode=0 if len(calls) == 1 else 1, stdout='audit: 3 folder(s) · 40 answers → x.md\n', stderr='boom')
RD.subprocess.run = fake
line = RD.post_submit()
check('post_submit runs the audit then the review; a failing step is logged, not raised', calls == ['audit_sample.py', 'post_submit.py'] and line.startswith('交后复核：audit: 3 folder(s)'), calls, line)
print(f'JSA-192: {n} cases · {len(verdicts)} verdicts · open disagreements {bad}')
sys.exit(1 if bad else 0)
