#!/usr/bin/env python3
"""run_oracle.fill_section on conditional rows (JSA-174, Goldman 2026-11-05): a row an earlier answer hides is skipped at
once (no 30 s click timeout) and not read back as missing; a row an answer reveals ("If 'Other' please specify") is
extracted again and filled; the secondary e-mail is never the main address. Headless Chrome on a static page, the
answer rules replaced by a fixed table — no network, no profile.
    ~/.job-agent-venv/bin/python skills/auto-apply/runner/test/t_oracle_conditional.py"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
try:
    import run_oracle as R  # noqa: E402
    from playwright.sync_api import sync_playwright  # noqa: E402
except ImportError as e:                                       # CI / a python without Playwright: nothing to test here
    print(f'skip t_oracle_conditional ({e})'); sys.exit(0)

AUTH = 'Are you legally authorized to work in the United States?'
VISA = 'If you currently hold or can obtain valid work authorization, please indicate your current visa type.'
MONTHS = 'If you indicated F-1 visa as your current visa type, please indicate the number of months (1-36) you have remaining.'
HEARD = 'Please indicate how you heard about Rosostbra'
OTHER = "If 'Other' please specify"
SECOND = 'Please provide a secondary email.'
ALT = 'Alternate email address'
CITIZEN = 'Do you hold citizenship in more than one country?'


def pills(label, opts, rid, hidden=False):
    bs = ''.join(f'<li><button type="button" aria-checked="false" data-r="{rid}">{o}</button></li>' for o in opts)
    return (f'<div id="{rid}" class="input-row"{" style=display:none" if hidden else ""}><label class="input-row__label '
            f'input-row__label--required">{label}</label><ul class="cx-select-pills-container" role="radiogroup">{bs}</ul></div>')


def text(label, rid, req=True, hidden=False, area=False):
    ctl = '<textarea class="input-row__control"></textarea>' if area else '<input class="input-row__control" type="text">'
    return (f'<div id="{rid}" class="input-row input-row--text"{" style=display:none" if hidden else ""}><label class="input-row__label'
            f'{" input-row__label--required" if req else ""}">{label}</label>{ctl}</div>')


PAGE = ('<html><body><div class="apply-flow-block apply-flow-block--disqualification-questions">' +
        pills(AUTH, ['Yes', 'No'], 'a') + pills(VISA, ['F-1', 'H-1B'], 'b2') + text(MONTHS, 'b') +
        pills(HEARD, ['Campus event', 'Other'], 'c') + text(OTHER, 'd', hidden=True, area=True) +
        text(SECOND, 'e', area=True) + text(ALT, 'f', req=False) + pills(CITIZEN, ['Yes', 'No'], 'g') +
        '''</div><script>
document.querySelectorAll('button[data-r]').forEach(b => b.addEventListener('click', () => {
  b.closest('ul').querySelectorAll('button').forEach(x => x.setAttribute('aria-checked', String(x === b)));
  const r = b.dataset.r, v = b.textContent.trim();
  if (r === 'a') ['b', 'b2'].forEach(id => document.getElementById(id).style.display = v === 'Yes' ? '' : 'none');
  if (r === 'c') document.getElementById('d').style.display = v === 'Other' ? '' : 'none';
}));
</script></body></html>''')

TABLE = {AUTH: {'status': 'ok', 'value': 'No', 'rule': 'authorized'},
         VISA: {'status': 'ok', 'value': 'F-1', 'rule': 'immigration_status'},
         MONTHS: {'status': 'ok', 'value': 'F-1', 'rule': 'immigration_status'},       # what the shared rules gave on 11-05
         HEARD: {'status': 'ok', 'value': 'Other', 'rule': 'how_heard'},
         'How did you hear about this job?': {'status': 'ok', 'value': 'Online job board', 'rule': 'how_heard'},
         SECOND: {'status': 'ok', 'value': 'alex.rivera@example.com', 'rule': 'email'},
         ALT: {'status': 'ok', 'value': 'alex.rivera@example.com', 'rule': 'email'}}
R.answer = lambda qs: {q['key']: dict(TABLE.get(q['label'], {'status': 'unknown'}), label=q['label']) for q in qs}
R.SECONDARY_EMAIL = None
R.JOB = {}

bad = 0
def check(ok, msg):
    global bad
    if not ok:
        bad += 1; print('FAIL', msg)


with sync_playwright() as p:
    try:
        b = p.chromium.launch(headless=True, channel='chrome')   # the installed Chrome; never the job Chrome
    except Exception as e:
        try:
            b = p.chromium.launch(headless=True)
        except Exception:
            print(f'skip t_oracle_conditional (no Chrome / Chromium: {type(e).__name__})'); sys.exit(0)
    pg = b.new_page(); pg.set_content(PAGE)
    ox = R.Oracle(pg, print)
    t0 = time.time()
    rows, problems, unknown, st = R.fill_section(ox, {}, None, print)
    took = time.time() - t0
    b.close()

by = {r['label']: r for r in rows}
check(took < 25, f'fill_section took {took:.0f}s (a hidden row waited for a timeout?)')
check(not [r for r in rows if 'Timeout' in str(r.get('error') or '')], 'a row timed out: ' + str([r['label'] for r in rows if r.get('error')]))
check(by.get(AUTH, {}).get('page') == 'No' and by[AUTH].get('ok'), f'authorized: {by.get(AUTH)}')
for lab in (VISA, MONTHS):                                     # hidden by the "No" answer: skipped, not missing
    r = by.get(lab, {})
    check(r.get('gone') and r.get('ok'), f'hidden row not skipped cleanly: {r}')
check(by.get(HEARD, {}).get('page') == 'Other', f'how heard: {by.get(HEARD)}')
r = by.get(OTHER, {})
check(r.get('page') == 'Online job board' and r.get('ok') and r.get('rule') == 'other_followup', f'Other box (revealed in pass 2): {r}')
r = by.get(SECOND, {})
check(r.get('want') is None and r.get('page') == '' and r.get('rule') == 'secondary_email', f'secondary e-mail must not get the main address: {r}')
r = by.get(ALT, {})
check(r.get('want') is None and r.get('page') == '' and r.get('ok'), f'optional alternate e-mail left empty: {r}')
check(len(unknown) == 2 and any(u.startswith(SECOND) for u in unknown) and any(u.startswith(CITIZEN) for u in unknown),
      f'unknown should be the secondary e-mail and the citizenship question: {unknown}')
check(not any(MONTHS in u or VISA in u for u in unknown + problems), f'hidden rows reported: {unknown + problems}')
print(f'fill_section {took:.1f}s · rows {len(rows)} · unknown {len(unknown)} · problems {len(problems)}')
print('ALL PASS' if not bad else f'{bad} FAILED'); sys.exit(1 if bad else 0)
