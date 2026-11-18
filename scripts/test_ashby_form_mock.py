#!/usr/bin/env python3
"""Offline regression test of run_form.Form on an Ashby mock page (JSA-208 + JSA-209), in its own headless Chrome —
never the job Chrome. skills/auto-apply/runner/test/ashby_school_mock.html (fictional person, made-up org):
  1. a stale plan's "June 14, 2027" is typed as 06/14/2027 and reads back ok (JSA-208, Sevgalkel 11-02 / 11-05);
  2. the School type-ahead is filled by picking the one option that is the school and reads back after focus left it;
  3. no matching school option → the row's error starts with "needs-user" (Joey), nothing guessed;
  4. a pick that never registers → BAD on the read-back / re-read before Submit (the Talkelver 10-31 hole);
  5. Submit with an empty School → submit_errors reads ['School'] from the page (→ status failed, not unconfirmed);
  7. (JSA-330) a form that leaves out Degree and the start date: nothing times out, Major and the end date are filled, the
     read-back does not demand a Degree and the plan's edu_excluded keeps the end pair out of the start boxes;
  6. Submit with the school picked → the thank-you text, no errors.
Run with the venv python (Playwright). Exit 1 on any failure."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUNNER)
import run_form as RF  # noqa: E402
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('SKIP test_ashby_form_mock: Playwright not installed (run with ~/.job-agent-venv/bin/python)'); sys.exit(0)

MOCK = 'file://' + os.path.abspath(os.path.join(RUNNER, 'test', 'ashby_school_mock.html'))
EDU = json.dumps([{'school': 'University of Chicago', 'degree': 'Master of Science', 'major': 'Applied Data Science',
                   'start_month': 'September', 'start_year': '2026', 'end_month': 'December', 'end_year': '2027', 'current': True}])


def plan(*keys):
    fields = {
        'name': {'key': '_systemfield_name', 'label': 'Name', 'type': 'text', 'required': True, 'answer': 'Alex Rivera', 'status': 'ok'},
        'date': {'key': 'd1', 'label': 'When is your earliest availability to start?', 'type': 'date', 'required': True,
                 'answer': 'June 14, 2027', 'status': 'ok', 'source': 'answers.json'},
        'edu': {'key': '_systemfield_education_history', 'label': 'School', 'type': 'education', 'required': True,
                'answer': EDU, 'status': 'ok', 'source': 'profile.education'},
    }
    return {'ats': 'ashby', 'url': MOCK, 'ready': True, 'fields': [dict(fields[k]) for k in keys]}


fails = []
def check(name, cond, detail=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + ('' if cond else f'  ({detail})'))
    if not cond:
        fails.append(name)


with sync_playwright() as pw:
    br = None
    for kw in ({'channel': 'chrome', 'headless': True}, {'headless': True}):
        try:
            br = pw.chromium.launch(**kw); break
        except Exception:
            continue
    if br is None:
        print('SKIP test_ashby_form_mock: no headless Chrome / Chromium to launch'); sys.exit(0)
    logs = []
    def form(q, *keys):
        page = br.new_page(); page.goto(MOCK + q)
        return page, RF.Form(page, plan(*keys), HERE, logs.append)

    page, f = form('', 'name', 'date', 'edu')
    res = {r['key']: r for r in f.run()}
    page.mouse.click(2, 2); f.recheck(('education',))
    check('1 stale "June 14, 2027" typed as 06/14/2027 and read back ok', res['d1']['ok'] and res['d1']['page'] == '06/14/2027', res['d1'])
    check('2 School picked ("The University of Chicago") and read back ok', res['_systemfield_education_history']['ok'],
          res['_systemfield_education_history'])
    page.locator('#submit').click(); page.wait_for_timeout(300)
    txt = page.inner_text('body')
    check('6 school picked → thank-you, no errors', RF.submit_errors(txt) == [] and bool(RF.CONFIRM.search(txt)), txt[:120])
    page.close()

    page, f = form('?nodegree', 'edu')
    f.plan['fields'][0]['edu_excluded'] = ['degree', 'startDate']
    r = f.run()[0]
    page.mouse.click(2, 2); f.recheck(('education',))
    ends = page.eval_on_selector_all('select', 'els => els.map(e => e.options[e.selectedIndex].text)')
    check('7 no Degree box / start date: reads back ok, end date in the end boxes', r['ok'] and ends == ['December', '2027'],
          (r, ends))
    page.close()

    page, f = form('?noschool', 'edu')
    r = f.run()[0]
    check('3 no matching school option → needs-user, not filled', not r['ok'] and str(r['error']).startswith('needs-user'), r)
    page.close()

    page, f = form('?deadclick', 'edu')
    r = f.run()[0]
    page.mouse.click(2, 2); f.recheck(('education',))
    check('4 a pick that never registers → BAD (typed text is not a pick)', not r['ok'], r)
    page.locator('#submit').click(); page.wait_for_timeout(300)
    errs = RF.submit_errors(page.inner_text('body'))
    check('5 Submit with School empty → submit_errors = [School]', errs == ['School'], errs)
    page.close()
    br.close()

print(f'{6 - len(fails)}/6 passed')
sys.exit(1 if fails else 0)
