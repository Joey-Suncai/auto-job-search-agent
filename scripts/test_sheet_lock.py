#!/usr/bin/env python3
"""JSA-366: only one session may apply a given morning prefetch sheet (11-16: two sessions applied the same
prefetch-2026-11-16 sheet at 13:12 and 13:20 — collect_batch --apply had no claim, so qa_add ran twice and the sheet was
marked answered twice). Also: a draft slot is never written into qa. Offline: temp profile + temp forms folder.
    python3 scripts/test_sheet_lock.py"""
from datetime import datetime
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CB = os.path.join(ROOT, 'skills', 'auto-apply', 'runner', 'collect_batch.py')
TMP = tempfile.mkdtemp(prefix='jsa_lock_')
bad = 0


def check(name, ok, *info):
    global bad
    if not ok:
        bad += 1; print('FAIL', name, *info)


def q(i, text, pick=None, **kw):
    e = {'id': i, 'question': text, 'options': ['Day shift', 'Night shift'], 'type': 'select', 'kind': 'fact', 'answer': {'pick': pick} if pick else None}
    e.update(kw); return e


def run(d, sheet, extra=()):
    json.dump(sheet, open(os.path.join(d, 'questions.json'), 'w'))
    env = dict(os.environ, JSA_HOME=TMP, JSA_PROFILE=os.path.join(TMP, 'profile.json'), JSA_FORMS_DIR=d, JSA_NO_PUSH='1')
    return subprocess.run([sys.executable, CB, '--apply', os.path.join(d, 'questions.json'), '--source', 'test'] + list(extra),
                          capture_output=True, text=True, env=env)


def qa():
    return [e['q'] for e in json.load(open(os.path.join(TMP, 'profile.json'))).get('qa') or []]


def lines(d):
    p = os.path.join(d, 'asked.jsonl')
    return len(open(p).read().splitlines()) if os.path.exists(p) else 0


shutil.copy(os.path.join(ROOT, 'config', 'fixtures', 'f1_student', 'profile.json'), os.path.join(TMP, 'profile.json'))
d = os.path.join(TMP, 'forms'); os.makedirs(d)
S = 'prefetch-2026-11-16'

# 1. first apply saves the answer and marks the sheet
r = run(d, {'name': S, 'questions': [q('P1', 'Zq preferred work shift?', 'Day shift')]})
check('first apply ok', r.returncode == 0, r.stdout, r.stderr[-300:])
check('first apply saved', qa().count('Zq preferred work shift?') == 1, qa()[-3:])
n_lines = lines(d)

# 2. a second session applying the same sheet is refused with a message; nothing written
r = run(d, {'name': S, 'questions': [q('P1', 'Zq preferred work shift?', 'Day shift')]})
check('second apply refused', r.returncode == 1 and 'already applied' in r.stdout, r.returncode, r.stdout, r.stderr[-200:])
check('second apply wrote no qa', qa().count('Zq preferred work shift?') == 1)
check('second apply wrote no asked line', lines(d) == n_lines)

# 3. the sheet rebuilt the same day with a new answered question: only the new one is applied
r = run(d, {'name': S, 'questions': [q('P1', 'Zq preferred work shift?', 'Day shift'), q('P2', 'Zq second shift choice?', 'Night shift')]})
check('rebuilt sheet ok', r.returncode == 0, r.stdout, r.stderr[-200:])
check('rebuilt: old not re-sent, new saved', qa().count('Zq preferred work shift?') == 1 and qa().count('Zq second shift choice?') == 1, qa()[-4:])

# 4. a live holder of the claim refuses; a dead holder's claim is taken over
lock = os.path.join(d, S + '.apply.lock')
json.dump({'pid': os.getpid(), 'at': datetime.now().isoformat(timespec='seconds')}, open(lock, 'w'))
r = run(d, {'name': S, 'questions': [q('P3', 'Zq third shift pick?', 'Day shift')]})
check('live claim refuses', r.returncode == 1 and 'another session' in r.stdout, r.returncode, r.stdout)
check('live claim: nothing saved', 'Zq third shift pick?' not in qa())
check('live claim kept', os.path.exists(lock))
json.dump({'pid': 2 ** 22 + 12345, 'at': datetime.now().isoformat(timespec='seconds')}, open(lock, 'w'))
r = run(d, {'name': S, 'questions': [q('P3', 'Zq third shift pick?', 'Day shift')]})
check('dead claim taken over', r.returncode == 0 and 'Zq third shift pick?' in qa(), r.returncode, r.stdout, r.stderr[-200:])
check('claim released after apply', not os.path.exists(lock))

# 5. --reapply deliberately re-sends an already handled sheet
r = run(d, {'name': S, 'questions': [q('P3', 'Zq third shift pick?', 'Night shift')]}, ['--reapply'])
check('--reapply allowed', 'already applied' not in r.stdout, r.stdout)

# 6. draft slots never reach qa
d2 = os.path.join(TMP, 'forms2'); os.makedirs(d2)
sheet = {'name': 'prefetch-2026-11-17', 'questions': [
    q('D1', 'Zq draft answer slot?', None, answer={'pick': 'Day shift', 'draft': True}),
    q('D2', 'Zq suggested only slot?', None, block='derived', suggested={'pick': 'Day shift'}),
    q('D3', 'Zq draft essay slot?', None, answer={'text': 'a drafted essay', 'draft': True}, kind='essay', options=[], type='textarea'),
]}
r = run(d2, sheet)
check('draft sheet ok', r.returncode == 0, r.stdout, r.stderr[-200:])
check('draft slot not in qa', not any(x.startswith('Zq draft') or x.startswith('Zq suggested') for x in qa()), qa()[-4:])
sheet['accept_derived'] = True; sheet['name'] = 'prefetch-2026-11-18'
r = run(d2, sheet)
check('accepted derived suggestion saved, draft still not', 'Zq suggested only slot?' in qa() and not any(x.startswith('Zq draft') for x in qa()), qa()[-4:])

# 7. a deferred sheet (「今天不答」) is not an applied one: answers filled later are applied
d3 = os.path.join(TMP, 'forms3'); os.makedirs(d3)
open(os.path.join(d3, 'asked.jsonl'), 'w').write(json.dumps({'sheet': 'prefetch-2026-11-19', 'how': 'deferred', 'n': None, 'questions': ['Zq later shift?']}) + '\n')
r = run(d3, {'name': 'prefetch-2026-11-19', 'questions': [q('L1', 'Zq later shift?', 'Day shift')]})
check('deferred then answered applies', r.returncode == 0 and 'Zq later shift?' in qa(), r.returncode, r.stdout)

# 8. a claim older than 6 hours is stale although its pid is alive
json.dump({'pid': os.getpid(), 'at': '2020-01-01T00:00:00'}, open(os.path.join(d3, 'prefetch-2026-11-20.apply.lock'), 'w'))
r = run(d3, {'name': 'prefetch-2026-11-20', 'questions': [q('L2', 'Zq old claim shift?', 'Day shift')]})
check('old claim is stale', r.returncode == 0 and 'Zq old claim shift?' in qa(), r.returncode, r.stdout)

shutil.rmtree(TMP, ignore_errors=True)
print(f'sheet_lock: fails {bad}')
sys.exit(1 if bad else 0)
