#!/usr/bin/env python3
"""Offline test for the manual-verdict layer in eligibility_merge.py (Alex 2026-10-29).
Run: python3 _test_merge.py   -> must print "fails 0"."""
import importlib.util, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('em', os.path.join(HERE, 'eligibility_merge.py'))
em = importlib.util.module_from_spec(spec)
spec.loader.exec_module(em)

fails = []


def check(name, cond, detail=''):
    if not cond:
        fails.append(f'{name}: {detail}')


def run(jobs, results, today):
    d = tempfile.mkdtemp()
    jp, rp, op = (os.path.join(d, n) for n in ('jobs.json', 'res.json', 'out.json'))
    json.dump(jobs, open(jp, 'w'))
    json.dump(results, open(rp, 'w'))
    conflicts = em.main(jp, rp, op, today)
    return json.load(open(op)), (conflicts or [])


def row(i, title, score, **kw):
    j = {'id': i, 'company': 'Acme', 'title': title, 'level': 'Internship', 'location': 'NYC',
         'score': score, 'tier': 'A', 'url': 'https://x/' + i, 'elig_key': 'url:https://x/' + i}
    j.update(kw)
    return j


# 1. a live manual verdict wins over a fresh automatic one, and the conflict is reported
jobs = [row('J1', 'Intern', 80, elig_manual={'elig': '已关闭', 'reason': '岗位已下线', 'evidence': '404',
                                             'codes': 'CLOSED', 'by': 'test', 'at': '2026-10-29',
                                             'until': '2026-11-30'},
            elig='可投', elig_checked='2026-10-01'),
        row('J2', 'Different Intern', 50, elig='可投')]
res = {'J1': {'v': 'Eligible', 'c': '', 'e': ''}, 'J2': {'v': 'Eligible', 'c': '', 'e': ''}}
out, conflicts = run(jobs, res, '2026-10-29')
j1 = next(j for j in out if j['id'] == 'J1')
check('manual keeps verdict', j1['elig'] == '已关闭', j1['elig'])
check('auto verdict kept for audit', j1.get('elig_auto') == '可投', str(j1.get('elig_auto')))
check('tier blocked', j1['tier'] == 'Blocked', str(j1.get('tier')))
check('conflict reported', any(c['id'] == 'J1' and c['auto'] == '可投' for c in conflicts), str(conflicts))

# 2. an expired manual verdict hands control back to the gate
jobs = [row('J3', 'Intern', 60, elig_manual={'elig': '已关闭', 'reason': 'old', 'at': '2026-09-01', 'until': '2026-10-01'},
            elig='已关闭', elig_checked='2026-09-02')]
res = {'J3': {'v': 'Eligible', 'c': '', 'e': ''}}
out, _ = run(jobs, res, '2026-10-29')
j3 = next(j for j in out if j['id'] == 'J3')
check('expired manual yields to automation', j3['elig'] == '可投', j3['elig'])
check('expiry flagged', j3.get('elig_manual_expired') == '2026-10-01', str(j3.get('elig_manual_expired')))

# 3. a manual duplicate keeps dup_of although dedupe clears every dup_of first
jobs = [row('J4', 'AI Solution Architect Graduate Intern', 90, elig='可投'),
        row('J5', 'AI Solution Architect Intern', 70,
            elig_manual={'elig': '重复', 'reason': '与 J4 是同一个岗位', 'dup_of': 'J4', 'at': '2026-10-29',
                         'until': '2026-11-30'}, elig='可投')]
res = {'J4': {'v': 'Eligible', 'c': '', 'e': ''}, 'J5': {'v': 'Eligible', 'c': '', 'e': ''}}
out, conflicts = run(jobs, res, '2026-10-29')
j5 = next(j for j in out if j['id'] == 'J5')
check('manual dup kept', j5['elig'] == '重复' and j5['dup_of'] == 'J4', f"{j5['elig']} {j5.get('dup_of')}")
check('manual dup is a conflict', any(c['id'] == 'J5' for c in conflicts), str(conflicts))

# 4. rows without the marker are untouched, and the row count never changes
jobs = [row('J6', 'Intern A', 40, elig='可投'), row('J7', 'Intern B', 30, elig='可投')]
res = {'J6': {'v': 'Eligible', 'c': '', 'e': ''}}
out, conflicts = run(jobs, res, '2026-10-29')
check('row count stable', len(out) == 2, str(len(out)))
check('automatic row unchanged', next(j for j in out if j['id'] == 'J6')['elig'] == '可投')
check('no manual -> no conflict', conflicts == [], str(conflicts))

# 5. JSA-385: the old label "Blocked: no sponsorship" no longer overrides the gate; "citizenship required" still does
jobs = [row('J8', 'Intern C', 60, elig='可投', sponsorship='Blocked: no sponsorship'),
        row('J9', 'Intern D', 55, elig='可投', sponsorship='Blocked: citizenship required'),
        row('J10', 'Intern E', 50, elig='可投')]
res = {'J8': {'v': 'Eligible', 'c': 'NO_SPONSORSHIP_INTERN', 'e': 'We are unable to sponsor'},
       'J9': {'v': 'Eligible', 'c': '', 'e': ''},
       'J10': {'v': 'Eligible', 'c': 'NO_FUTURE_SPONSORSHIP_INTERN', 'e': 'not require sponsorship now or in the future'}}
out, conflicts = run(jobs, res, '2026-11-17')
o = {j['id']: j for j in out}
check('385 label no-sponsorship stays 可投', o['J8']['elig'] == '可投' and o['J8']['tier'] == 'A', f"{o['J8']['elig']} {o['J8']['tier']}")
check('385 tag in reason', '无担保（实习用 CPT）' in o['J8']['elig_reason'], o['J8']['elig_reason'])
check('385 citizenship label still blocks', o['J9']['elig'] == '不可投' and o['J9']['tier'] == 'Blocked', o['J9']['elig'])
check('385 future wording is 可投 with its own tag', o['J10']['elig'] == '可投' and '降一档' in o['J10']['elig_reason'], o['J10']['elig_reason'])

jobs = [row('J11', 'Data Analyst', 60, level='New grad', elig='可投', sponsorship='Blocked: no sponsorship')]
out, _ = run(jobs, {'J11': {'v': 'Eligible', 'c': '', 'e': ''}}, '2026-11-17')
check('385 full-time row with the label stays blocked', out[0]['elig'] == '不可投' and out[0]['tier'] == 'Blocked', f"{out[0]['elig']} {out[0]['tier']}")

print('fails', len(fails))
for f in fails:
    print(' FAIL', f)
sys.exit(1 if fails else 0)
