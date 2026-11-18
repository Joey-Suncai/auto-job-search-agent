#!/usr/bin/env python3
"""Harness for run_form.receipt_plan + runner_common.unconfirmed_action (rule 13, JSA-391): DeepSeek cases from
test_cases/async_receipt_spec.md, verdicts in test_cases/async_receipt_verdicts.json; plus the SuccessFactors / Lever
wiring: no in-place e-mail wait remains by default."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUNNER)
import run_form as RF, runner_common as RC  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'async_receipt_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'async_receipt_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    fn = getattr(RF if c['fn'] == 'receipt_plan' else RC, c['fn'])
    got = fn(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
import argparse, re
src = open(os.path.join(RUNNER, 'run_form.py'), encoding='utf-8').read()
if not re.search(r"--mail-wait'?, type=int, default=0", src):
    bad += 1; print('DISAGREE run_form --mail-wait default is not 0')
sf = open(os.path.join(RUNNER, 'run_successfactors.py'), encoding='utf-8').read()
if 'wait_for_mail(since, company, timeout=300)' in sf:
    bad += 1; print('DISAGREE run_successfactors still waits 300 s in place')
# a pending Lever row (receipt: pending, submit_at) is picked up by receipt_confirm and searched since the click, not since the results line
sys.path.insert(0, os.path.join(HERE, 'daily'))
import receipt_confirm as RCF
from datetime import datetime, timedelta
now = datetime.now().astimezone()
row = {'folder': 'f1', 'status': 'unconfirmed', 'receipt': 'pending', 'at': (now - timedelta(minutes=2)).isoformat(timespec='seconds'),
       'submit_at': (now - timedelta(minutes=3)).isoformat(timespec='seconds')}
if [r['folder'] for r in RCF.open_unconfirmed([row], now)] != ['f1']:
    bad += 1; print('DISAGREE receipt_confirm does not pick up a pending row')
seen = {}
import tempfile, shutil
home = tempfile.mkdtemp(); runner_d = os.path.join(home, 'runner'); apps = os.path.join(home, 'apps'); os.makedirs(runner_d); os.makedirs(os.path.join(apps, 'f1'))
json.dump({'company': 'Acme', 'title': 'Intern'}, open(os.path.join(apps, 'f1', 'job.json'), 'w'))
open(os.path.join(runner_d, 'results.jsonl'), 'w').write(json.dumps(row) + '\n')
def finder(since, company, **k):
    seen['since'] = since; return None
try:
    RCF.run(runner=runner_d, apps=apps, finder=finder, now=now, dry=True, log=lambda m: None, sync=lambda *a, **k: None, close=lambda *a, **k: None)
except Exception as e:
    bad += 1; print('DISAGREE receipt_confirm.run raised', type(e).__name__, str(e)[:100])
if seen.get('since') is None or abs((datetime.fromisoformat(row['submit_at']).astimezone() - timedelta(seconds=30) - seen['since']).total_seconds()) > 1:
    bad += 1; print('DISAGREE receipt_confirm searched since', seen.get('since'), 'not the click time')
shutil.rmtree(home, ignore_errors=True)
# runner_common.finish: told=True → no queue / push for 'unconfirmed'; a receipt-pending line carries receipt + submit_at; the pushed case pushes
import tempfile
td = tempfile.mkdtemp(); os.environ['JSA_NO_PUSH'] = '1'
os.makedirs(os.path.join(td, 'f1')); os.makedirs(os.path.join(td, 'data'))
pushes, queues = [], []
RF.push = lambda *a, **k: pushes.append(a)
RF.queue = lambda *a, **k: queues.append(a)
def run_finish(told, pending, status='unconfirmed'):
    del pushes[:], queues[:]
    R = RC.Run('lever', 'https://jobs.lever.co/acme/11111111-1111-1111-1111-111111111111/apply', os.path.join(td, 'f1'), os.path.join(td, 'f1'),
               submit=True, log=lambda m: None, data_dir=os.path.join(td, 'data'))
    R.finish({'status': status, 'problems': [], 'fields': [{'label': 'Name', 'want': 'A', 'page': 'A', 'ok': True, 'type': 'text'}], 'receipt_pending': pending},
             told=told, extra=({'receipt': 'pending', 'submit_at': '2026-11-17T10:00:00-06:00'} if pending else None))
    return json.loads(open(os.path.join(td, 'data', 'results.jsonl')).read().strip().splitlines()[-1])
line = run_finish(True, False)
if pushes or queues:
    bad += 1; print('DISAGREE told=True still pushed / queued', pushes, queues)
line = run_finish(False, True)
if pushes or queues or line.get('receipt') != 'pending' or line.get('submit_at') != '2026-11-17T10:00:00-06:00':
    bad += 1; print('DISAGREE pending line', pushes, queues, line)
run_finish(False, False)
if not pushes:
    bad += 1; print('DISAGREE an unconfirmed result with nobody told must push')
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
