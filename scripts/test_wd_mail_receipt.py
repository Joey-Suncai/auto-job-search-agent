#!/usr/bin/env python3
"""JSA-306: Workday — no confirmation on the page after Submit → wait for the company's receipt e-mail (run_wd.wd_mail_receipt).
DeepSeek-written cases: scripts/test_cases/wd_mail_receipt_cases.json; a case judged wrong goes into wd_mail_receipt_verdicts.json (none so far).
    python3 scripts/test_wd_mail_receipt.py"""
import json, os, sys
from datetime import datetime, timedelta, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_wd  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'wd_mail_receipt_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'wd_mail_receipt_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
def T(name, ok, info=''):
    global bad
    v = verdicts.get(name)
    if not ok and v and v.get('verdict') == 'case':
        print(f'SKIP {name}  (case judged wrong: {v["why"][:80]})'); return
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}')); bad += not ok

SINCE = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)
def run(meta, wait, wmode):
    calls, logs = [], []
    def waiter(since, company, timeout=180):
        calls.append((since, company, timeout))
        if wmode == 'RAISE': raise RuntimeError('gmail down')
        return wmode
    return run_wd.wd_mail_receipt(meta, SINCE, wait, waiter, logs.append), calls, logs

for c in cases:
    got, calls, logs = run(c['meta'], c['wait'], c['waiter'])
    ok = got == c['expect'] and bool(calls) == c['expect_called']
    if calls and c.get('expect_called'):
        ok = ok and calls[0][1] == c.get('expect_company') and calls[0][0] == SINCE - timedelta(seconds=30) and calls[0][2] == c.get('expect_timeout', c['wait'])
    T(c['name'], ok, f'got {got!r} calls {calls}')

# the two cases of the row: page unchanged + mail → subject (status submitted, confirmed_by email); page unchanged + no mail → None (unconfirmed)
g, _, _ = run({'company': 'Vanguard'}, 180, 'Thank you for applying to Vanguard')
T('row: page unchanged + mail → subject', g == 'Thank you for applying to Vanguard')
g, c_, _ = run({'company': 'Vanguard'}, 180, None)
T('row: page unchanged + no mail → None (unconfirmed)', g is None and len(c_) == 1)
# a rerun of an e-mail-confirmed folder must not submit again (review: only the confirmation png was checked)
import tempfile
d = tempfile.mkdtemp()
T('guard: empty folder → not submitted', run_wd.wd_already_submitted(d) is False)
open(os.path.join(d, 'application_record.md'), 'w').write('# record\n\n## Submitted by run_wd.py 2026-11-17T12:00:00\n- Confirmation: company e-mail "Thank you"\n')
T('guard: application_record.md section (e-mail confirmed) → submitted', run_wd.wd_already_submitted(d) is True)
d2 = tempfile.mkdtemp(); open(os.path.join(d2, 'application_record.md'), 'w').write('# record\nSubmitted by hand later\n')
T('guard: a record without the runner section → not submitted', run_wd.wd_already_submitted(d2) is False)
d3 = tempfile.mkdtemp(); open(os.path.join(d3, 'submitted_confirmation.png'), 'wb').write(b'x')
T('guard: confirmation png → submitted', run_wd.wd_already_submitted(d3) is True)
sys.exit(1 if bad else 0)
