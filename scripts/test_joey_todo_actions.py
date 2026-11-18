#!/usr/bin/env python3
"""JSA-389: open tracker actions (e-mailed assessments / interviews / forms) are rows of Joey's to-do list."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store'))
import joey_todo as J  # noqa: E402

T = '2026-11-17'
def app(jid, status, action, ddl='', **kw):
    return dict(job_id=jid, company=kw.get('company', 'Co ' + jid), title='Intern', status=status, action_needed=action, action_deadline=ddl)

ROWS = [
    app('J1', 'Assessment', 'Set up Honorlock, then take the Acme quantitative challenge (45 min) via the link in the email by Nov 20', '2026-11-20'),
    app('J2', 'Assessment', 'Take the Beta Capital Quant Coding Challenge on HackerRank by Dec 10', '2026-12-10'),
    app('J3', 'Assessment', 'Take the Coderbyte assessment'),
    app('J4', 'Applied', 'Book a 15-minute phone screening via the scheduling link'),
    app('J5', 'Applied', 'Complete the WOTC questionnaire via the link in the email.'),
    app('J6', 'Applied', '请确认（Claude 不确定）：Other — a welcome message'),
    app('J7', 'Applied', 'Enter the one-time passcode 400733 within 10 minutes', '2026-11-11'),
    app('J8', 'Applied', 'Enter the one-time pass code 846817 on the portal within 10 minutes, or request a new code'),
    app('J9', 'Rejected', 'Download the assignment package and upload it by Nov 11', '2026-11-11'),
    app('J10', 'Interview', '等结果'),
    app('J11', 'Applied', ''),
    app('J12', 'Assessment', 'Take the Gamma assessment', '2026-11-10'),
    app('J13', 'Archived', 'Take the Delta assessment'),
]
got = J.tracker_actions(ROWS, T)
ids = [r['job_id'] for r in got]
bad = []
def check(c, m):
    if not c: bad.append(m)

check(ids == ['J12', 'J1', 'J2', 'J3', 'J4', 'J5', 'J6'] or ids[:3] == ['J12', 'J1', 'J2'], f'order by deadline: {ids}')
check(set(ids) == {'J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J12'}, f'set (no codes / rejected / archived / waiting / empty): {ids}')
by = {r['job_id']: r for r in got}
check(by['J1']['kind'] == 'assessment' and by['J3']['kind'] == 'assessment', 'assessment kind')
check(by['J4']['kind'] == 'interview', 'interview kind')
check(by['J5']['kind'] == 'form', 'form kind')
check(by['J6']['kind'] == 'confirm', 'confirm kind')
check(by['J1']['deadline'] == '2026-11-20' and by['J1']['days_left'] == 3 and not by['J1']['overdue'], 'deadline / days_left')
check(by['J12']['overdue'] is True, 'overdue marked')
check(by['J3']['deadline'] == '' and by['J3']['days_left'] is None, 'no deadline')
check(all(r['sources'] == ['tracker'] and r['folder'] == r['job_id'] for r in got), 'folder = job id, source tracker')

# merged into the list: dated actions first by deadline; Assessment no longer closes a queue row
q = J.parse_queue('- [ ] 2026-11-01T10:00:00 **F1** — Submit your transcript — https://x')
m = J.merge(q, [], {}, set(), {'J20': 'Assessment'}, {}, {'F1': 'J20'}, T + 'T10:00', actions=got)
check([r['folder'] for r in m][:3] == ['J12', 'J1', 'J2'], f'merged order: {[r["folder"] for r in m]}')
check('F1' in [r['folder'] for r in m], 'Assessment status keeps a queue row open')
m2 = J.merge(q, [], {}, set(), {'J20': 'Offer'}, {}, {'F1': 'J20'}, T, actions=[])
check(m2 == [], 'Offer still closes')
g = J.tracker_actions([app('K1', 'Applied', 'Verify your identity with Persona before the interview'),
                      app('K2', 'Applied', 'Take the online assessment; one-time code 123 expires')], T)
check([r['job_id'] for r in g] == ['K1', 'K2'], 'identity / mixed text kept')
m3 = J.merge(q, [], {}, set(), {}, {}, {'F1': 'J1'}, T, actions=got)
check('J1' in [r['folder'] for r in m3] and 'F1' in [r['folder'] for r in m3], 'runner stop does not hide a dated action')
# JSA-394: Offer rows keep their open action; the kind patterns are narrower
o = J.tracker_actions([app('O1', 'Offer', 'Accept the Acme offer and return the signed letter by Nov 25', '2026-11-25'),
                       app('O2', 'Applied', 'Complete the questionnaire sent by the recruiter'),
                       app('O3', 'Applied', 'Reply to the recruiter to schedule a call'),
                       app('O4', 'Applied', 'Fill out the contest entry form'),
                       app('O5', 'Applied', 'Pass the latest build test of the portal link'),
                       app('O6', 'No response', 'Take the Zeta assessment')], T)
k = {r['job_id']: r['kind'] for r in o}
k2 = {r['job_id']: r['kind'] for r in J.tracker_actions([app('P1', 'Applied', 'Complete the take-home test'), app('P2', 'Applied', 'Schedule time with the hiring manager'),
                                                         app('P3', 'Applied', 'Book time on calendly'), app('P4', 'Applied', 'Pick a time for your final round')], T)}
check(k2 == {'P1': 'assessment', 'P2': 'interview', 'P3': 'interview', 'P4': 'interview'}, f'JSA-394 more kinds: {k2}')
check(k == {'O1': 'offer', 'O2': 'form', 'O3': 'interview', 'O4': 'form', 'O5': 'form'}, f'JSA-394 kinds: {k}')
gg = J.group_by_kind([{'kind': 'confirm', 'folder': 'a'}, {'kind': 'form', 'folder': 'b'}, {'kind': 'confirm', 'folder': 'c'}, {'kind': 'form', 'folder': 'd'}])
check([(k, [r['folder'] for r in g]) for k, g in gg] == [('confirm', ['a', 'c']), ('form', ['b', 'd'])], f'JSA-395 grouping: {gg}')
gr = [(r['folder'], r['group']) for r in m]
check(gr[-1] == ('F1', 'stopped') and all(g == 'action' for _, g in gr[:-1]), f'JSA-395 two blocks, actions first: {gr}')
# JSA-397: the dashboard shows only what the company wants Joey to do next
DASH = [app('D1', 'Assessment', 'Take the Acme quantitative challenge by Nov 20', '2026-11-20'),
        app('D2', 'Applied', 'Complete the WOTC questionnaire via the link in the email.'),
        app('D3', 'Applied', 'Book a 15-minute phone screening via the scheduling link'),
        app('D4', 'Offer', 'Accept the offer by Nov 25', '2026-11-25'),
        app('D5', 'Applied', '请确认（Claude 不确定）：Other — a welcome message'),
        app('D6', 'Applied (unconfirmed)', 'Confirm whether the Lumvergal application was submitted'),
        app('D7', 'Applied', 'If a recruiter reaches out, tell them the answer should be No'),
        app('D8', 'Applied', 'Joey: decide whether to check the submitted education blocks'),
        app('D9', 'Rejected', 'Take the Delta assessment')]
q2 = J.parse_queue('- [ ] 2026-11-01T10:00:00 **F9** — CAPTCHA required — https://x')
full = J.merge(q2, [], {}, set(), {}, {}, {'F9': 'J99'}, T, actions=J.tracker_actions(DASH, T))
dash = J.dashboard_rows(full)
check([r['job_id'] for r in dash] == ['D1', 'D4', 'D2', 'D3'], f'dashboard rows: {[r["job_id"] for r in dash]}')
check(not any(r['kind'] in ('captcha', 'sign-in', 'answers', 'materials', 'gate', 'runner error', 'unconfirmed', 'confirm') for r in dash), 'no runner / confirm kinds on the dashboard')
check(any(r['folder'] == 'F9' for r in full), 'the command line list keeps the runner stop')
print(f'joey_todo actions: {len(bad)} failure(s)')
for b in bad: print('FAIL', b)
sys.exit(1 if bad else 0)
