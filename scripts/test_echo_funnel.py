#!/usr/bin/env python3
"""JSA-360: echo funnel — interviews and assessments per 100 applications. Hand-worked fixture: 5 applications, 4 e-mails."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store'))
import echo_funnel as F  # noqa: E402

def app(jid, applied, status='Applied', ref='Cold'):
    return {'job_id': jid, 'applied_on': applied, 'status': status, 'referral_status': ref, 'url': ''}

APPS = [app('J1', '2026-10-30', 'Assessment'), app('J2', '2026-10-30', 'Rejected', 'Referred'), app('J3', '2026-11-02'),
        app('J4', '2026-11-03', 'Interview'), app('J5', '2026-10-20'),        # J5 before the start date
        app('J6', '', 'Shortlisted'), app('J7', '2026-11-04', 'Archived')]    # never applied
JOBS = [{'id': 'J1', 'track': 'Quant', 'tier': 'A', 'url': 'https://boards.greenhouse.io/x/jobs/1'},
        {'id': 'J2', 'track': 'Quant', 'tier': 'B', 'url': 'https://acme.wd1.myworkdayjobs.com/en/job/2'},
        {'id': 'J3', 'track': 'PM', 'tier': 'A', 'url': 'https://jobs.lever.co/y/3'},
        {'id': 'J4', 'track': 'PM', 'tier': 'A', 'url': 'https://jobs.ashbyhq.com/z/4'},
        {'id': 'J5', 'track': 'PM', 'tier': 'A', 'url': 'https://boards.greenhouse.io/q/jobs/5'}]
EM = [{'job_id': 'J1', 'type': 'Confirmation', 'date': '2026-10-30'},       # a receipt is not an echo
      {'job_id': 'J1', 'type': 'Assessment', 'date': '2026-11-02'},          # J1: assessment, first echo 3 days after applying
      {'job_id': 'J2', 'type': 'Assessment', 'date': '2026-11-01'},          # J2: assessment, then rejected (history kept)
      {'job_id': 'J4', 'type': 'Interview', 'date': '2026-11-10'},           # J4: interview, 7 days
      {'job_id': 'J5', 'type': 'Interview', 'date': '2026-11-05'}]           # J5 is before the start date → not counted
RES = {'J1': 'A-Classic', 'J2': 'A-Classic', 'J3': 'B-Modern'}                 # J4 unknown

bad = []
def check(c, m):
    if not c: bad.append(m)

r = F.funnel(APPS, EM, JOBS, '2026-10-28', RES)
t = r['total']
check((t['apps'], t['interviews'], t['assessments']) == (4, 1, 2), f'total: {t}')
check(t['per100_interview'] is None and t['per100_assessment'] is None, 'fewer than 20 applications: no percentage')
rows = {(x['dim'], x['value']): x for x in r['rows']}
q = rows[('track', 'Quant')]; check((q['apps'], q['interviews'], q['assessments']) == (2, 0, 2), f'Quant: {q}')
pm = rows[('track', 'PM')]; check((pm['apps'], pm['interviews'], pm['assessments']) == (2, 1, 0), f'PM: {pm}')
check(rows[('platform', 'Workday')]['apps'] == 1 and rows[('platform', 'Greenhouse')]['assessments'] == 1, 'platform')
check(rows[('resume', 'A-Classic')]['apps'] == 2 and rows[('resume', 'Unknown')]['apps'] == 1, f'resume: {[k for k in rows if k[0]=="resume"]}')
check(rows[('referral', 'Referred')]['assessments'] == 1, 'referral')
check(rows[('first echo (days)', '3–6')]['apps'] == 1 and rows[('first echo (days)', '7–13')]['apps'] == 1 and rows[('first echo (days)', '0–2')]['apps'] == 1, f'days: {[(k,v["apps"]) for k,v in rows.items() if k[0].startswith("first")]}')
# a later start date drops the older applications; an earlier one takes J5 in
check(F.funnel(APPS, EM, JOBS, '2026-11-03', RES)['total']['apps'] == 1, 'start date moves the denominator')
check(F.funnel(APPS, EM, JOBS, '2026-10-01', RES)['total']['apps'] == 5, 'earlier start date')
# the percentage appears from 20 applications on
big = [app(f'B{i}', '2026-11-01') for i in range(20)]
eb = [{'job_id': 'B0', 'type': 'Interview', 'date': '2026-11-05'}, {'job_id': 'B1', 'type': 'Assessment', 'date': '2026-11-06'}]
tb = F.funnel(big, eb, [], '2026-10-28', {})['total']
check(tb['per100_interview'] == 5.0 and tb['per100_assessment'] == 5.0, f'per 100: {tb}')
# resume version: from file names, from the ledger field first
check(F.resume_version(['Alex_Doe_Resume_Corlumlum_PM_Intern_A-Classic.pdf', 'cover.txt']) == 'A-Classic', 'file name version')
check(F.resume_version(['cover.txt']) == '', 'no resume file → empty')
check(F.resume_version(['Alex_Doe_Resume_X_Management.pdf']) == '', 'a name that is not a version → empty')
r2 = F.funnel([dict(app('J9', '2026-11-01'), resume_version='B-Modern')], [], [], '2026-10-28', {'J9': 'A-Classic'})
check(('resume', 'B-Modern') in {(x['dim'], x['value']) for x in r2['rows']}, 'the ledger field wins over the file name')
print(f'echo_funnel: {len(bad)} failure(s)')
for b in bad: print('FAIL', b)
sys.exit(1 if bad else 0)
