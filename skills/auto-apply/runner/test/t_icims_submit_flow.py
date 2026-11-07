#!/usr/bin/env python3
"""Offline flow test of the iCIMS submit path (JSA-093): run_icims.steps_loop with a fake tab — no browser, no network.
Checks that the hand-in button is clicked only when submit_gate says 'press', and how each page after the click ends.
    python3 t_icims_submit_flow.py   → ALL PASS"""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import run_icims as R  # noqa: E402

R.time.sleep = lambda s: None
R.hold_for_captcha = lambda ic, out, where, log: True
R.keychain = lambda svc: ''


def bar(cur, names):
    return ' '.join(f'Step {i} of {len(names)}. {n} ({"Current" if i == cur else "Incomplete"} Step)' for i, n in enumerate(names, 1))


class Loc:
    def __init__(self, tab, sel): self.tab, self.sel = tab, sel
    @property
    def first(self): return self
    def click(self): self.tab.clicks.append(self.sel); self.tab.advance()
    def fill(self, v): pass


class Frame:
    def __init__(self, tab): self.tab = tab
    def locator(self, sel): return Loc(self.tab, sel)
    def evaluate(self, js, arg=None): return False          # the button is not busy
    def inner_text(self, sel): return self.tab.pages[self.tab.i]['text']


class Tab:
    """pages: list of {'text', 'buttons', 'errors', 'ok'}; a click moves to the next page."""
    url = 'https://careers-acme.icims.com/jobs/1/x/candidate?mode=apply'
    def __init__(self, pages): self.pages, self.i, self.clicks = pages, 0, []
    def advance(self): self.i = min(self.i + 1, len(self.pages) - 1)
    def screenshot(self, **k): pass
    def inner_text(self, sel): return self.pages[self.i]['text']
    def is_closed(self): return False


class FakeIc:
    def __init__(self, tab): self.page, self.tab = tab, tab
    def frame(self): return Frame(self.tab)
    def state(self):
        p = self.tab.pages[self.tab.i]
        return {'text': p['text'], 'buttons': p.get('buttons', []), 'errors': p.get('errors', []), 'fields': []}
    def captcha_up(self): return False


def fake_fill(ic, over, resume, log, _tried=None):
    p = ic.tab.pages[ic.tab.i]
    rows = [{'id': 'f1', 'label': 'Country', 'kind': 'dropdown', 'required': True, 'want': 'United States', 'page': 'United States', 'ok': p.get('ok', True)}]
    probs = [] if p.get('ok', True) else ['Country: want United States, page ""']
    return rows, probs, p.get('unknown', []), ic.state()


R.fill_step = fake_fill
EMAIL = {'subj': None}


def fake_by_email(res, since, log):
    if EMAIL['subj']:
        res['status'], res['confirmed_by'] = 'submitted', 'email'; return 'done'
    res['status'] = 'unconfirmed'; res['problems'].append('no confirmation'); return 'stop'


R.by_email = fake_by_email
SUBMIT_BTN = [{'id': 'sub', 'text': 'Submit'}]
NEXT_BTN = [{'id': 'nx', 'text': 'Next'}]
THANKS = {'text': 'Thank you for applying! Your application has been submitted.'}


def go(pages, submit, consent='ok', no_advance=False):
    R.SUBMIT, R.NO_ADVANCE = submit, no_advance
    tab = Tab(pages)
    res = {'status': 'blocked', 'problems': [], 'steps': [], 'unknown': [], 'account': None}
    if consent != 'ok':
        res['consent'] = consent
    R.steps_loop(FakeIc(tab), tab, res, None, lambda m: None, tempfile.mkdtemp(), {})
    return res, tab


fails = 0


def check(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  {info}'))
    fails += 0 if cond else 1


last2 = [{'text': bar(1, ['Profile', 'EEO']), 'buttons': NEXT_BTN}, {'text': bar(2, ['Profile', 'EEO']), 'buttons': SUBMIT_BTN}, THANKS]
r, t = go(last2, submit=False)
check('dry-run default: stops before Submit, no hand-in click', r['status'] == 'dry-run' and t.clicks == ['[id="nx"]'], (r['status'], t.clicks))
r, t = go(last2, submit=True, no_advance=True)
check('--no-advance never presses (first step stops)', r['status'] == 'dry-run' and t.clicks == [], (r['status'], t.clicks))
r, t = go(last2, submit=True)
check('submit: Submit pressed once, thank-you page → submitted (page)', r['status'] == 'submitted' and r.get('confirmed_by') == 'page'
      and t.clicks == ['[id="nx"]', '[id="sub"]'], (r, t.clicks))
mid = [{'text': bar(2, ['Profile', 'EEO', 'Assessments', 'Review']), 'buttons': [{'id': 'fl', 'text': 'Finish Later'}] + SUBMIT_BTN},
       {'text': bar(3, ['Profile', 'EEO', 'Assessments', 'Review']), 'buttons': SUBMIT_BTN}, THANKS]
r, t = go(mid, submit=True)
check('Submit on a middle step → next step filled → Submit again → submitted', r['status'] == 'submitted' and t.clicks == ['[id="sub"]', '[id="sub"]']
      and r.get('maybe_in'), (r['status'], t.clicks))
bad = [{'text': bar(2, ['Profile', 'EEO']), 'buttons': SUBMIT_BTN, 'ok': False}, THANKS]
r, t = go(bad, submit=True)
check('read-back mismatch → needs-user, nothing pressed', r['status'] == 'needs-user' and t.clicks == [], (r['status'], t.clicks))
unk = [{'text': bar(2, ['Profile', 'EEO']), 'buttons': SUBMIT_BTN, 'unknown': ['Veteran status']}, THANKS]
r, t = go(unk, submit=True)
check('unknown required answer → needs-user, nothing pressed', r['status'] == 'needs-user' and t.clicks == [], (r['status'], t.clicks))
r, t = go(last2[1:], submit=True, consent='ask')
check('consent wording not approved → needs-user (gate consent), nothing pressed', r['status'] == 'needs-user' and t.clicks == []
      and any('gate consent' in p for p in r['problems']), (r, t.clicks))
err = [{'text': bar(2, ['Profile', 'EEO']), 'buttons': SUBMIT_BTN, 'errors': ['Please answer all required questions']}, THANKS]
r, t = go(err, submit=True)
check('error on the page before the hand-in → needs-user (page-error)', r['status'] == 'needs-user' and t.clicks == [], (r, t.clicks))
idle = [{'text': bar(2, ['Profile', 'EEO']), 'buttons': SUBMIT_BTN, 'errors': ['You will be logged out in 60 seconds due to inactivity.']}, THANKS]
r, t = go(idle, submit=True)
check('the inactivity notice does not block the hand-in', r['status'] == 'submitted', (r['status'], t.clicks))
refused = [{'text': bar(2, ['Profile', 'EEO']), 'buttons': SUBMIT_BTN},
           {'text': bar(2, ['Profile', 'EEO']) + ' Error: Gender is required', 'buttons': SUBMIT_BTN, 'errors': ['Gender is required']}]
r, t = go(refused, submit=True)
check('the step stays after Submit → needs-user, "did not go through"', r['status'] == 'needs-user' and len(t.clicks) == 1
      and any('did not go through' in p for p in r['problems']), (r, t.clicks))
blank = [{'text': bar(2, ['Profile', 'EEO']), 'buttons': SUBMIT_BTN}, {'text': ''}]
EMAIL['subj'] = None
r, t = go(blank, submit=True)
check('no page confirmation, no e-mail → unconfirmed', r['status'] == 'unconfirmed', r)
EMAIL['subj'] = 'Thank you for applying to Acme'
r, t = go(blank, submit=True)
check('no page confirmation, receipt e-mail → submitted (email)', r['status'] == 'submitted' and r.get('confirmed_by') == 'email', r)
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
