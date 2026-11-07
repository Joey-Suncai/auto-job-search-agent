"""sync_results (JSA-014): pure steps, no files. Prints `fails 0` when everything passes."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_results as sr

fails = 0
def ok(c, label):
    global fails
    fails += 0 if c else 1
    print(("PASS " if c else "FAIL ") + label)

jobs = [{'id': 'J1', 'company': 'Brasevnev', 'title': 'Data Engineer Intern', 'level': 'Internship', 'score': 50.9, 'track': 'Data Engineer', 'url': 'u1'},
        {'id': 'J2', 'company': 'Acme', 'title': 'PM Intern', 'level': 'Internship'},
        {'id': 'J3', 'company': 'Beta', 'title': 'DA Intern', 'level': 'Internship'}]
apps = [{'job_id': 'J2', 'company': 'Acme', 'status': 'Shortlisted', 'applied_on': ''},
        {'job_id': 'J3', 'company': 'Beta', 'status': 'Rejected', 'applied_on': '2026-10-20', 'notes': 'x'}]
res = [{'folder': 'f1', 'status': 'submitted', 'at': '2026-10-30T14:01:36'},
       {'folder': 'f1', 'status': 'dry-run', 'at': '2026-10-30T14:00:00'},
       {'folder': 'f2', 'status': 'submitted', 'at': '2026-10-31T09:00:00'},
       {'folder': 'f3', 'status': 'submitted', 'at': '2026-10-31T10:00:00'},
       {'folder': 'f4', 'status': 'submitted', 'at': '2026-10-31T11:00:00'}]
fmap = {'f1': 'J1', 'f2': 'J2', 'f3': 'J3'}
ch, unk, done = sr.sync(res, apps, jobs, fmap)
j1 = next(a for a in apps if a['job_id'] == 'J1')
ok(j1['status'] == 'Applied' and j1['applied_on'] == '2026-10-30' and j1['company'] == 'Brasevnev', 'no row → new Applied row from the jobs store')
ok(apps[0]['status'] == 'Applied' and apps[0]['applied_on'] == '2026-10-31', 'Shortlisted row → Applied')
ok(apps[1]['status'] == 'Rejected' and apps[1]['applied_on'] == '2026-10-20', 'a Rejected row is never changed')
ok(unk == ['f4'], 'a folder without a job id is reported, not guessed')
ok(done == ['f1', 'f2', 'f3', 'f4'], 'dry-run lines are not submissions')
ch2, _, _ = sr.sync(res, apps, jobs, fmap)
ok(ch2 == [] and sum(1 for a in apps if a['job_id'] == 'J1') == 1, 'idempotent: a second sync changes nothing')
q = "- [ ] 2026-10-30 **f1** — Workday needs answers\n- [x] old **f1** — done\n- [ ] 2026-10-30 **f9** — other"
q2, n = sr.close_queue(q, ['f1'])
ok(n == 1 and q2.startswith('- [x] 2026-10-30 **f1**') and '- [ ] 2026-10-30 **f9**' in q2, "only the submitted folder's open lines are ticked")
appsA = [{'job_id': 'J2', 'company': 'Acme', 'status': 'Archived', 'applied_on': ''}]
sr.sync([{'folder': 'f2', 'status': 'submitted', 'at': '2026-11-05T10:00:00'}], appsA, jobs, fmap)
ok(appsA[0]['status'] == 'Applied' and appsA[0]['applied_on'] == '2026-11-05', 'Archived (never applied, JSA-013) row → Applied on a submit')
os.environ['CX_DATA'] = '/tmp/x'
ok(sr.sync_folder('f1', lambda m: None) is None, 'test mode (CX_DATA) never writes the real store')
print(f"fails {fails}")
sys.exit(1 if fails else 0)
