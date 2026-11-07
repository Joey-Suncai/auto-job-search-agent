#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/apply_req_cases.json, from apply_req_spec.md) against
scripts/store/apply_req.py and the /apply route of scripts/scoring/pref_server.validate (JSA-179). Disagreements are
judged in apply_req_verdicts.json ("case" = the case misread the spec).   python3 scripts/test_apply_req.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store')); sys.path.insert(0, os.path.join(HERE, 'scoring'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import apply_req as A  # noqa: E402
import pref_server as P  # noqa: E402

cases = [c for f in ('apply_req_cases.json', 'apply_desk_cases.json') for c in json.load(open(os.path.join(HERE, 'test_cases', f), encoding='utf-8'))]   # desk = JSA-182
vp = os.path.join(HERE, 'test_cases', 'apply_req_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}


def run(c):
    f, a = c['fn'], c['args']
    if f == 'skip_names':
        return A.skip_names(a['text'])
    if f == 'can_queue':
        ok, why = A.can_queue(a['job'], set(a['applied_ids']), a['skip'], a['runner'])
        return ok if (ok or why) else 'refused without a reason'
    if f == 'apply_mode':
        return A.apply_mode(a['job'], a['runner'])
    if f == 'set_fields':
        before = json.dumps(a['job'], sort_keys=True)
        try:
            r = A.set_fields(a['job'], a['status'], a['now'], a.get('note', ''), a.get('by', ''))
        except ValueError:
            return 'error'
        return r if json.dumps(a['job'], sort_keys=True) == before else 'input changed'
    if f == 'queued':
        return [list(x) for x in A.queued(a['rows'])]
    if f == 'desk_alive':
        return A.desk_alive(a['state'], a['now'], **({'stale': a['stale']} if 'stale' in a else {}))
    if f == 'should_notify':
        return A.should_notify(a['state'], a['now'], **{k: a[k] for k in ('stale', 'grace') if k in a})
    if f == 'validate':
        return P.validate(a['method'], a['path'], a['headers'], a['body'].encode('utf-8'))[0]
    raise ValueError(f)


fails = 0
for c in cases:
    try:
        g = run(c)
    except Exception as e:
        g = f'error {type(e).__name__}: {e}'
    if g == c['expect']:
        continue
    v = verdicts.get(c['name'])
    if v and v.get('verdict') == 'case':
        print('CASE ', c['name'], '—', v['why'][:140]); continue
    fails += 1; print('FAIL ', c['name'], '| got', json.dumps(g, ensure_ascii=False)[:300], '| want', json.dumps(c['expect'], ensure_ascii=False)[:300])
print(f'{len(cases)} cases · fails {fails}'); sys.exit(1 if fails else 0)
