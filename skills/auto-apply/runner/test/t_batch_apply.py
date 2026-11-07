#!/usr/bin/env python3
"""JSA-229 batch_apply.py pure functions against DeepSeek-written cases (rule 13: DeepSeek writes, Claude judges).
Cases: scripts/test_cases/batch_apply_cases.json · verdicts (cases that misread the spec): batch_apply_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import batch_apply as B
import chrome_lock as L
import run as RUN
import run_workable as RW

def load(name):
    c = json.load(open(os.path.join(REPO, 'scripts', 'test_cases', name)))
    return c.get('cases', c) if isinstance(c, dict) else c
cases = load('batch_apply_cases.json') + load('batch_apply_230_cases.json') + load('batch_apply_note_cases.json') + load('batch_apply_235_cases.json') + load('run_stop_cases.json') + load('workable_offline_cases.json')   # JSA-229 + JSA-230 (spec grew)
vp = os.path.join(REPO, 'scripts', 'test_cases', 'batch_apply_verdicts.json')
skip = json.load(open(vp)) if os.path.exists(vp) else {}

def call(c):
    i = c['input']; f = c['fn']
    if f == 'track': return B.track(i.get('track'))
    if f == 'runner': return B.runner(i.get('ats'))
    if f == 'parse': return B.parse(i.get('output'))
    if f == 'ready': return B.ready(i.get('status'), i.get('reasons') or [], i.get('output') or '')
    if f == 'size': return B.size(i.get('n'), i.get('max'), bool(i.get('login')))
    if f == 'platform': return B.platform(i.get('url'))
    if f == 'command': return B.command(i.get('ats'), i.get('folder'), bool(i.get('submit')), bool(i.get('ds_ok')))
    if f == 'folder_name': return B.folder_name(i.get('date'), i.get('company'), i.get('title'))
    if f == 'split': return {k: [j['id'] for j in v] for k, v in B.split(i.get('jobs') or []).items()}
    if f == 'offline': return B.offline(i.get('ats'), bool(i.get('dry_run')))
    if f == 'offline_items': return B.offline_items(i.get('needs_user'), i.get('gate_items'), i.get('given') or [])
    if f == 'outcome': return B.outcome(i.get('status'))
    if f == 'inherited': return L.inherited(i.get('holder'), i.get('env_pid'), i.get('parent_chain'))
    if f == 'describe': return L.describe(i.get('holder'))
    if f == 'stop_status': return RUN.stop_status(i.get('reasons') or [], bool(i.get('submit')))
    if f == 'offline_unknowns': return RW.offline_unknowns(i.get('fields'), i.get('ans') or {}, i.get('missing') or [])
    if f == 'last_note': return B.last_note(i.get('output'))
    if f == 'merge': return B.merge(i.get('stdout') or {}, i.get('results'))
    raise ValueError(f)

def same(got, exp):
    if isinstance(exp, dict) and isinstance(got, dict):
        return all(same(got.get(k), v) for k, v in exp.items())
    if isinstance(exp, (int, float)) and isinstance(got, (int, float)) and not isinstance(exp, bool):
        return abs(got - exp) < 1e-9
    return got == exp

fails = 0
for c in cases:
    if c['id'] in skip: continue
    got = call(c)
    if not same(got, c['expect']):
        fails += 1; print('FAIL', c['id'], c['fn'], json.dumps(c['input'])[:160], 'expect', c['expect'], 'got', got)
print(f"t_batch_apply: {len(cases) - len(skip)} cases, {len(skip)} judged as misreading the spec, fails {fails}")
sys.exit(1 if fails else 0)
