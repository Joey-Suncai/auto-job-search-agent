#!/usr/bin/env python3
"""Harness for pref_server.validate + pref.apply (rule 13, JSA-101): DeepSeek cases, Claude's verdicts in pref_server_verdicts.json."""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TC = os.path.join(HERE, '..', 'test_cases')
TMP = tempfile.mkdtemp(prefix='jsa_pref_')
os.environ['JOB_STORE_DIR'] = TMP                       # before store is imported: tests never touch data/store
os.environ['JSA_PREFS_LOG'] = os.path.join(TMP, 'prefs.jsonl')
sys.path.insert(0, HERE)
import pref, pref_server  # noqa: E402

cases = json.load(open(os.path.join(TC, 'pref_server_cases.json'), encoding='utf-8'))
vp = os.path.join(TC, 'pref_server_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}


def run_apply(c):
    jobs = [dict({'score': 0}, **j) for j in c['jobs']]
    open(os.path.join(TMP, 'jobs.jsonl'), 'w').write(''.join(json.dumps(j) + '\n' for j in jobs))
    log = os.environ['JSA_PREFS_LOG']
    if os.path.exists(log): os.remove(log)
    err = None
    try:
        pref.apply(c['ids'], c['pref'], via='test')
    except KeyError:
        err = 'unknown'
    after = {r['id']: r.get('joey_pref') for r in pref.store.load('jobs')}
    lines = sum(1 for _ in open(log)) if os.path.exists(log) else 0
    return {'error': err, 'prefs_after': after, 'log_lines': lines}


bad = 0
for c in cases:
    if c['kind'] == 'validate':
        got = list(pref_server.validate(c['method'], c['path'], c.get('headers') or {}, c.get('body', '').encode('utf-8')))
    else:
        got = run_apply(c)
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '\n  got   ', got, '\n  expect', c['expect'])
shutil.rmtree(TMP, ignore_errors=True)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
