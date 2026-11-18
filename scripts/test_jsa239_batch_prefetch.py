#!/usr/bin/env python3
"""JSA-239 (rule 13): DeepSeek-written cases (test_cases/jsa239_batch_prefetch_cases.json, spec …_spec.md) for batch_apply.prefetch_gate,
plus cmd_prepare end to end on a 10-job mixed batch (fresh closed / restricted / ok / stale / none) with the preparation stubbed:
the skipped jobs are never prepared and do not count against the batch size, the others carry prefetch_left in the report.
Verdicts: jsa239_batch_prefetch_verdicts.json.   python3 scripts/test_jsa239_batch_prefetch.py"""
import json, os, sys, tempfile, types
from datetime import datetime, timedelta
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path[:0] = [os.path.join(ROOT, 'skills/auto-apply/runner'), os.path.join(ROOT, 'config')]
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import batch_apply as B  # noqa: E402
vp = os.path.join(HERE, 'test_cases', 'jsa239_batch_prefetch_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa239_batch_prefetch_cases.json')))
bad = 0
for c in cases:
    act, val = B.prefetch_gate(c['record'], c['today'])
    e = c['expect']
    ok = act == e['action'] and (act == 'skip' and val == e.get('status') or act == 'prepare' and val == e.get('prefetch_left'))
    if not ok and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', act, val, '| expect', e, '|', c['record'], c['today'])
n = len(cases)


def check(name, ok, *info):
    global bad, n
    n += 1
    if not ok:
        bad += 1; print('FAIL', name, *info)


today = datetime.now().strftime('%Y-%m-%d')
ago = lambda d: (datetime.now() - timedelta(days=d)).strftime('%Y-%m-%d')
recs = {'J1': {'status': 'closed', 'read_at': ago(1)}, 'J2': {'status': 'restricted', 'read_at': ago(5)}, 'J3': {'status': 'ok', 'read_at': ago(2), 'needs': 4},
        'J4': {'status': 'closed', 'read_at': ago(6)}, 'J5': {'status': 'ok', 'read_at': ago(0), 'needs': 0}, 'J6': {'status': 'error', 'read_at': ago(1)}}
jobs = [{'id': f'J{i}', 'company': f'Co{i}', 'title': 'Intern', 'ats_url': f'https://boards.greenhouse.io/co{i}/jobs/{i}', 'track': 'Data Sci / Analytics'} for i in range(1, 11)]
tmp = tempfile.mkdtemp(prefix='jsa239_')
batch = os.path.join(tmp, 'b.json')
json.dump({'name': 'b', 'date': today, 'jobs': jobs}, open(batch, 'w'))
prepped = []
B.prefetch_record = lambda jid: recs.get(jid)
B.prep_all = lambda batch_, b: [prepped.append(j['id']) or {'id': j['id'], 'company': j['company'], 'status': 'ok', 'folder': ''} for j in b['jobs']]
B.materials = lambda *a, **k: ('skipped', 0)
B.write_report = lambda batch_, rows, title, ext='.apply': globals().__setitem__('ROWS', rows)
B.cmd_prepare(types.SimpleNamespace(batch=batch, max=None, fresh=False, dry_run=True))
rows = {r['company']: r for r in ROWS}
check('closed fresh + restricted fresh skipped, not prepared', 'J1' not in prepped and 'J2' not in prepped and rows['Co1']['status'].startswith('skipped: closed') and rows['Co2']['status'].startswith('skipped: restricted'), prepped)
check('stale closed, ok, error, none are prepared', all(j in prepped for j in ('J3', 'J4', 'J5', 'J6', 'J7', 'J10')), prepped)
check('prefetch_left on fresh ok records only', rows['Co3'].get('prefetch_left') == 4 and rows['Co5'].get('prefetch_left') == 0 and 'prefetch_left' not in rows['Co4'] and 'prefetch_left' not in rows['Co7'], {k: v.get('prefetch_left') for k, v in rows.items()})
check('every job has a row, skipped ones are not ready', len(rows) == 10 and not rows['Co1']['ready'])
check('the batch file keeps all jobs', len(json.load(open(batch))['jobs']) == 10)
check('a non-dict record file is ignored', B.prefetch_gate([1], today) == ('prepare', None))
prepped.clear()
B.cmd_prepare(types.SimpleNamespace(batch=batch, max=None, fresh=False, dry_run=True, no_prefetch=True))
check('--no-prefetch prepares every job', len(prepped) == 10 and not any('prefetch_left' in r for r in ROWS), prepped)
print(f'JSA-239: {n} cases · {len(verdicts)} verdicts · open disagreements {bad}')
sys.exit(1 if bad else 0)
