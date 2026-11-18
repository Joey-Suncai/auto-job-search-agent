#!/usr/bin/env python3
"""JSA-193 step 8: scripts/daily/receipt_confirm.py — DeepSeek-written cases (scripts/test_cases/receipt_confirm_cases.json),
verdicts for cases judged wrong in receipt_confirm_verdicts.json (none so far), plus run() on a temp data home with a fake mailbox.
    python3 scripts/test_receipt_confirm.py"""
import json, os, sys, tempfile
from datetime import datetime, timedelta
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'daily'))
import receipt_confirm as RC  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'receipt_confirm_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'receipt_confirm_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
def T(name, ok, info=''):
    global bad
    v = verdicts.get(name)
    if not ok and v and v.get('verdict') == 'case':
        print(f'SKIP {name}  (case judged wrong: {v["why"][:80]})'); return
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}')); bad += not ok

for c in cases:
    if c['fn'] == 'open_unconfirmed':
        kw = {'days': c['days']} if c.get('days') is not None else {}
        got = [r['folder'] for r in RC.open_unconfirmed(c['rows'], datetime.fromisoformat(c['now']), **kw)]
    else:
        kw = {'hours': c['hours']} if c.get('hours') is not None else {}
        got = RC.receipt_decision(c['at'], c['subject'], datetime.fromisoformat(c['now']), **kw)
    T(c['name'], got == c['expect'], f"got {got!r} want {c['expect']!r}")

# run(): three unconfirmed folders — one has a receipt mail, one is 50 h old without mail, one is 2 h old without mail
NOW = datetime.fromisoformat('2026-11-17T12:00:00-06:00')
d = tempfile.mkdtemp(); runner, apps = os.path.join(d, 'runner'), os.path.join(d, 'apps'); os.makedirs(runner); os.makedirs(apps)
ago = lambda h: (NOW - timedelta(hours=h)).isoformat(timespec='seconds')
rows = [{'at': ago(3), 'folder': 'F_mail', 'url': 'https://x/1', 'ats': 'lever', 'status': 'unconfirmed'},
        {'at': ago(50), 'folder': 'F_old', 'url': 'https://x/2', 'ats': 'workday', 'status': 'unconfirmed'},
        {'at': ago(2), 'folder': 'F_new', 'url': 'https://x/3', 'ats': 'successfactors', 'status': 'unconfirmed'},
        {'at': ago(1), 'folder': 'F_done', 'url': 'https://x/4', 'ats': 'lever', 'status': 'unconfirmed'},
        {'at': ago(0.5), 'folder': 'F_done', 'url': 'https://x/4', 'ats': 'lever', 'status': 'submitted'}]
open(os.path.join(runner, 'results.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in rows))
for f, co in (('F_mail', 'Acme'), ('F_old', 'Globex'), ('F_new', 'Initech'), ('F_done', 'Hooli')):
    os.makedirs(os.path.join(apps, f)); json.dump({'company': co}, open(os.path.join(apps, f, 'job.json'), 'w'))
asked, synced, logs = [], [], []
def finder(since, company, **kw):
    asked.append((company, since)); return 'Thank you for applying to Acme' if company == 'Acme' else None
closed = []
r = RC.run(runner=runner, apps=apps, finder=finder, now=NOW, log=logs.append, sync=synced.append, close=lambda n, h: closed.append(n))
T('run: one confirmed, one to Joey, one waiting', r == {'confirmed': ['F_mail'], 'joey': ['F_old'], 'waiting': ['F_new']}, r)
T('run: a folder with a later submitted row is not asked', 'Hooli' not in [a[0] for a in asked], asked)
T('run: the mailbox is read since the click minus 30 s', dict(asked)['Acme'] == NOW - timedelta(hours=3, seconds=30), asked)
T('run: tracker sync called for the confirmed folder only', synced == ['F_mail'], synced)
lines = [json.loads(l) for l in open(os.path.join(runner, 'results.jsonl'))]
T('run: results line submitted + confirmed_by email', lines[-1]['folder'] == 'F_mail' and lines[-1]['status'] == 'submitted' and lines[-1]['confirmed_by'] == 'email', lines[-1])
T('run: application_record.md has a Submitted section', '## Submitted' in open(os.path.join(apps, 'F_mail', 'application_record.md')).read())
q = open(os.path.join(runner, 'queue.md')).read()
T('run: queue line for the 50 h folder', '**F_old** — no receipt e-mail in 48' in q and 'F_new' not in q, q)
RC.run(runner=runner, apps=apps, finder=finder, now=NOW, log=logs.append, sync=synced.append, close=lambda n, h: closed.append(n))
T('run: the second run adds no second queue line and no second confirmation', open(os.path.join(runner, 'queue.md')).read().count('F_old') == 1 and synced == ['F_mail'])
T('run: the to-do entry of the confirmed folder is closed', closed == ['F_mail'], closed)
# review safeguards
def fresh_home(rows, companies):
    d = tempfile.mkdtemp(); rn, ap = os.path.join(d, 'runner'), os.path.join(d, 'apps'); os.makedirs(rn); os.makedirs(ap)
    open(os.path.join(rn, 'results.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in rows))
    for f, co in companies.items():
        os.makedirs(os.path.join(ap, f)); json.dump({'company': co}, open(os.path.join(ap, f, 'job.json'), 'w'))
    return rn, ap
def boom(since, company, **kw): raise RuntimeError('imap down')
rn, ap = fresh_home([{'at': ago(10), 'folder': 'F_x', 'status': 'unconfirmed'}], {'F_x': 'Acme'})
r = RC.run(runner=rn, apps=ap, finder=boom, now=NOW, log=lambda *_: 0, sync=lambda n: 0, close=lambda n, h: 0)
T('safeguard: a mailbox error is never "no receipt" (10 h old, finder raises → waiting, no queue line)', r['waiting'] == ['F_x'] and not os.path.exists(os.path.join(rn, 'queue.md')), r)
rn, ap = fresh_home([{'at': ago(3), 'folder': 'F_a', 'status': 'unconfirmed'}, {'at': ago(2), 'folder': 'F_b', 'status': 'unconfirmed'}], {'F_a': 'Acme', 'F_b': 'ACME'})
asked2 = []
r = RC.run(runner=rn, apps=ap, finder=lambda s, c, **kw: asked2.append(c) or 'Application received', now=NOW, log=lambda *_: 0, sync=lambda n: 0, close=lambda n, h: 0)
T('safeguard: two open folders of one company → none confirmed, mailbox not asked', r['confirmed'] == [] and asked2 == [], (r, asked2))
rn, ap = fresh_home([{'at': ago(60), 'folder': 'F_old', 'status': 'unconfirmed'}], {'F_old': 'Acme'})
asked3 = []
r = RC.run(runner=rn, apps=ap, finder=lambda s, c, **kw: asked3.append(c) or 'Application received', now=NOW, log=lambda *_: 0, sync=lambda n: 0, close=lambda n, h: 0)
T('safeguard: after 48 h a later mail no longer confirms (it could be another role) → Joey', r['joey'] == ['F_old'] and asked3 == [], (r, asked3))
open(os.path.join(rn, 'queue.md'), 'w').write(open(os.path.join(rn, 'queue.md')).read().replace('- [ ]', '- [x]'))
RC.run(runner=rn, apps=ap, finder=finder, now=NOW, log=lambda *_: 0, sync=lambda n: 0, close=lambda n, h: 0)
T('safeguard: a ticked queue line is not asked again', open(os.path.join(rn, 'queue.md')).read().count('F_old') == 1)
sys.exit(1 if bad else 0)
