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

# JSA-360: the résumé version of a submitted folder is written into the tracker row (new and promoted rows)
appsV = [{'job_id': 'J2', 'company': 'Acme', 'status': 'Shortlisted', 'applied_on': ''}]
sr.sync([{'folder': 'f1', 'status': 'submitted', 'at': '2026-11-06T10:00:00'}, {'folder': 'f2', 'status': 'submitted', 'at': '2026-11-06T11:00:00'}],
        appsV, jobs, fmap, {'f1': 'A-Classic', 'f2': 'B-Modern'})
ok(next(a for a in appsV if a['job_id'] == 'J1').get('resume_version') == 'A-Classic' and next(a for a in appsV if a['job_id'] == 'J2').get('resume_version') == 'B-Modern', 'new and promoted rows carry resume_version')
appsW = [{'job_id': 'J2', 'company': 'Acme', 'status': 'Shortlisted', 'applied_on': ''}]
sr.sync([{'folder': 'f2', 'status': 'submitted', 'at': '2026-11-06T11:00:00'}], appsW, jobs, fmap, {})
ok('resume_version' not in appsW[0], 'no version found → no field (shown as Unknown, not guessed)')

# JSA-373: a queue line is ticked when its folder has a confirmation page / a Submitted record / a tracker status Applied or Rejected
import tempfile
ok(sr.settled_reason(['a.png', 'submitted_confirmation.png'], '', None) == 'confirmation page', 'confirmation page → settled')
ok(sr.settled_reason([], '# x\n## Submitted (by Joey) 2026-10-28\n- Role', None) == 'application record: Submitted', 'hand-submit record → settled')
ok(sr.settled_reason([], '', 'Rejected') == 'tracker Rejected' and sr.settled_reason([], '', 'Applied') == 'tracker Applied', 'tracker Applied / Rejected → settled')
ok(sr.settled_reason(['status.txt'], 'Not submitted: needs answers\n## Dry run', 'Shortlisted') == '', 'review / needs-user / Shortlisted stays open')
ok(sr.settled_reason(None, None, None) == '', 'nothing known → open')
ok(sr.settled_reason([], 'The ## Submitted word mid-line', None) == '', 'only a heading line counts')
ok(sr.settled_reason([], '## Submitted? no\n## Submittedness', None) == '', 'a look-alike heading does not count')
ok(sr.settled_reason([], '## Submitted by runner 2026-11-01', None) != '' and sr.settled_reason([], '## Submitted', None) != '', 'the runner headings count')
q4, n4 = sr.close_queue('- [ ] t **B** blocked by **A**\n- [ ] t **A** — x', {'A': 'r'})
ok(n4 == 1 and q4.startswith('- [ ] t **B**'), 'a line is ticked for its own (first) folder only')
qq = ('- [ ] t **fA** — needs answers\n- [ ] t **fB** — clicked Submit but no confirmation seen\n- [ ] t **fC** — handoff\n'
      '- [ ] t **fD** — two lines\n- [ ] t **fD** — again\n- [x] t **fE** — done\n- [ ] t QUINSEVFEN J1 no folder token')
ok(sr.queue_folders(qq) == ['fA', 'fB', 'fC', 'fD'], 'open folder names, once each')
with tempfile.TemporaryDirectory() as td:
    for f in ('fA', 'fB', 'fC', 'fD'):
        os.makedirs(os.path.join(td, f))
    open(os.path.join(td, 'fA', 'submitted_confirmation.png'), 'w').write('x')
    open(os.path.join(td, 'fB', 'application_record.md'), 'w').write('## Dry run\n')
    open(os.path.join(td, 'fC', 'job.json'), 'w').write('{}')
    open(os.path.join(td, 'fD', 'application_record.md'), 'w').write('## Submitted (by Joey) 2026-11-01\n')
    sf = sr.settled_folders(qq, td, [{'job_id': 'J9', 'status': 'Rejected'}, {'job_id': 'J8', 'status': 'Shortlisted'}], {'fB': 'J9', 'fC': 'J8'})
    ok(sf == {'fA': 'confirmation page', 'fB': 'tracker Rejected', 'fD': 'application record: Submitted'}, 'settled_folders: confirmation, tracker, record; fC (Shortlisted) stays')
    q3, n3 = sr.close_queue(qq, sf)
    ok(n3 == 4 and q3.count('- [x]') == 5 and '- [ ] t **fC**' in q3 and 'closed: tracker Rejected' in q3, 'close_queue ticks every open line of a settled folder with its reason')
    sf2 = sr.settled_folders(qq, os.path.join(td, 'nope'), [], {})
    ok(sf2 == {}, 'no applications folder → nothing settled')
os.environ['CX_DATA'] = '/tmp/x'
ok(sr.sync_folder('f1', lambda m: None) is None, 'test mode (CX_DATA) never writes the real store')
print(f"fails {fails}")
sys.exit(1 if fails else 0)
