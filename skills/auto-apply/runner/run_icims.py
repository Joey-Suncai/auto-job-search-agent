#!/usr/bin/env python3
"""iCIMS runner (JSA-093, 2026-11-03; submit path 2026-11-05). Opens an iCIMS posting (`<tenant>.icims.com/jobs/<id>/…`, or
a Jibe / company front end `…/jobs/<id>?icims=1` whose Apply button leads into the tenant's iCIMS) in the job Chrome, enters
the e-mail, parks the hCaptcha that iCIMS shows at the e-mail step for Joey (human_check.py, never answered here), signs in
or creates the tenant profile with the Keychain password, then walks the steps (Candidate Profile → Questions → EEO → …):
every field answered by answer_rules.js (config/profile.json), filled, read back. By default (dry-run) it stops at the
hand-in button (`is_final`) without clicking it. With --folder <application folder> --submit it presses that button only
when `submit_gate` says 'press' (folder in data/runner/approved_batches.json and not already submitted, every step read
back, nothing unknown, no page error, the e-mail-step consent approved) and confirms by the thank-you page
(`after_submit`, screenshot submitted_confirmation.png) or the company's receipt e-mail → tracker row, tabs closed.
A CAPTCHA is always Joey's (skills/ats-icims/SKILL.md).

    ~/.job-agent-venv/bin/python run_icims.py --url <posting url> [--job J01234] [--track Data_Analyst] [--resume <pdf>]
         [--out <dir>] [--wait-captcha 10] [--attach <url text>] [--keep-tab] [--answers <json>]
    ~/.job-agent-venv/bin/python run_icims.py --folder applications/<folder> --submit [--wait-captcha 10]

Writes <out>/run_log.md, form_check.json (every field per step: label, rule, want, page, ok), step_<n>.png; one line in
data/runner/results.jsonl (status dry-run | needs-user | captcha | signin | blocked | submitted | unconfirmed; mode
dry-run | submit). Default out: data/runner/dryrun/icims/<id> (the folder with --folder).
A stop (unknown required answer, wrong-password sign-in, CAPTCHA not solved in time, unexpected page) keeps the tab open.
"""
import argparse, json, os, re, subprocess, sys, time
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
DATA = os.environ.get('CX_DATA') or jpaths.data('runner')
RULES = os.path.join(HERE, '..', 'scripts', 'answer_rules.js')
sys.path.insert(0, HERE)
import human_check  # noqa: E402  (JSA-106)
import job_board  # noqa: E402  (the "Please specify" job-board list, 2026-11-03)
import runner_common as RC  # noqa: E402  (JSA-187: opening checks · submit gate · closing books)

TRACKS = {'Data Engineer': 'Data_Engineer', 'Data Sci / Analytics': 'Data_Analyst', 'Data Analyst': 'Data_Analyst',
          'Product Manager': 'Product_Manager', 'AI Product Manager': 'Product_Manager', 'AI Agentic Eng': 'AI_Agentic_Engineer'}
IFRAME = 'icims_content_iframe'
# iCIMS standard profile fields: the page labels several of them just "Type" / "Address" / "Number"
FIELD_LABELS = {'phonetype': 'Phone Device Type', 'countrycode': 'Phone Country Code', 'phonenumber': 'Phone Number',
                'phoneextension': 'Phone Extension', 'addresstype': 'Address Type', 'addressstreet1': 'Street Address',
                'addressstreet2': 'Address Line 2', 'addresscity': 'City', 'addresszip': 'Zip', 'addresscountry': 'Country',
                'addressstate': 'State', 'addresscounty': 'County', 'login': 'Email', 'email': 'Email',
                'firstname': 'First Name', 'middlename': 'Middle Name', 'lastname': 'Last Name'}
FINAL_RE = re.compile(r'submit (my |your )?application|finish|complete (my |your )?application|^submit$|apply now|send application', re.I)
DONE_RE = re.compile(r'(application|submission) (has been |was )?(successfully )?(submitted|received|complete)|thank you for (applying|your application|submitting)', re.I)
NO_ADVANCE = False                                             # --no-advance: fill + read back this step only
CAPTCHA_SEL = 'iframe[src*="hcaptcha"][src*="frame=challenge"]'


# ---------- pure helpers (tested: scripts/test_icims.py, DeepSeek cases) ----------
def N(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def login_url(url):
    """Posting URL → (kind, url). kind 'icims': `https://<tenant>.icims.com/jobs/<id>/login` (the e-mail step, built
    from the posting). kind 'jibe': a Jibe / company front end (`*.jibeapply.com/jobs/<id>`, or any `/jobs/<id>` URL with
    `icims=1`) — the runner opens it and follows its Apply link. (None, None) when it is not an iCIMS posting."""
    u = str(url or '').strip()
    try:
        p = urlparse(u)
    except ValueError:
        return None, None
    host = (p.hostname or '').lower()
    if p.scheme not in ('http', 'https') or not host:
        return None, None
    m = re.match(r'/jobs/(\d+)(?:/|$)', p.path or '')
    if host.endswith('.icims.com') and host != 'login.icims.com' and m:
        return 'icims', f'https://{host}/jobs/{m.group(1)}/login'
    if m and (host.endswith('.jibeapply.com') or re.search(r'(^|&)icims=1(&|$)', p.query or '')):
        return 'jibe', u
    return None, None


def field_label(fid, label):
    """iCIMS field id + its on-page label → the label the answer rules read. Standard profile fields are named from the id
    (`-1_PersonProfileFields.PhoneType` → 'Phone Device Type'), because the page calls several of them just 'Type';
    anything else keeps its own label without the required star / 'required.' / whitespace noise."""
    m = re.search(r'(?:Person|Portal)ProfileFields\.([A-Za-z0-9]+)', str(fid or ''))
    if m and m.group(1).lower() in FIELD_LABELS:
        return FIELD_LABELS[m.group(1).lower()]
    s = re.sub(r'\brequired\.?\s*$', '', N(label), flags=re.I)
    s = re.sub(r'\s*\*\s*$', '', s).strip()
    return re.sub(r'^\*\s*', '', s).strip()


def parse_steps(text):
    """Step bar text ('Step 1 of 4. Candidate Profile(Current Step) Step 2 of 4. Candidate Questions(Incomplete Step)')
    → {'current': 1, 'total': 4, 'name': 'Candidate Profile', 'steps': ['Candidate Profile', 'Candidate Questions', …]};
    None when the text has no step bar."""
    found = re.findall(r'Step\s+(\d+)\s+of\s+(\d+)\.?\s*(.+?)\s*\((Current|Incomplete|Complete|Completed)\s+Step\)', N(text), re.I)
    if not found:
        return None
    steps, cur, total = {}, None, 0
    for n, t, name, state in found:
        steps[int(n)] = N(name)
        total = max(total, int(t))
        if state.lower() == 'current':
            cur = int(n)
    if cur is None:
        return None
    return {'current': cur, 'total': total, 'name': steps[cur], 'steps': [steps.get(i, '') for i in range(1, total + 1)]}


AFTER_RE = re.compile(r'assessment|review|confirm|submit|e-?sign|signature|complete|thank', re.I)


def is_final(button, steps):
    """True when pressing this button would (or may) hand in the application: the current step is the last one; or it is
    the next-to-last and the last step is one iCIMS shows after or as the hand-in (Assessments, Review, Confirm, Submit,
    e-Signature, Complete); or the button reads like a final submit ('Submit Application', 'Finish', 'Apply Now', bare
    'Submit'). 'Submit Profile' / 'Next' / 'Save & Continue' on an earlier step are not final. No step bar → every
    submit-like button counts as final."""
    b = N(button)
    if steps and steps.get('current') and steps.get('total'):
        if steps['current'] >= steps['total']:
            return True
        names = steps.get('steps') or []
        if steps['current'] == steps['total'] - 1 and len(names) >= steps['total'] and AFTER_RE.search(names[steps['total'] - 1] or ''):
            return True
    if FINAL_RE.search(b):
        return True
    if not steps and re.search(r'submit', b, re.I):
        return True
    return False


NOT_NAV = re.compile(r'log ?in with|sign ?in with|continue with|connect|google|facebook|linked ?in|apple|indeed|microsoft|'
                     r'dropbox|onedrive|replace resume|\bback\b|previous|cancel|withdraw|save (as )?draft|save for later|add more|^search$|'
                     r'\blater\b', re.I)   # "Finish Later" / "Save and Finish Later" = save and leave (Springs EEO 11-04, JSA-143)
NAV = re.compile(r'\bnext\b|continue|submit|save (and|&) continue|^save$|proceed|finish|apply', re.I)


def pick_button(buttons):
    """The step's own forward button from the visible submit-type buttons [{'id', 'text'}]: never a social sign-in
    ('Log in with Apple'), Back / Cancel / Save as draft / Add More / Replace Resume; the first whose text reads like
    Next / Continue / Submit …; None when there is no such button."""
    for b in buttons or []:
        t = N(b.get('text'))
        if t and not NOT_NAV.search(t) and NAV.search(t):
            return b
    return None


def classify(url, text):
    """Where the tab is: 'universal_login' (login.icims.com e-mail box) · 'universal_password' (its password page) ·
    'social_error' (a social sign-in with no linked iCIMS account) · 'bad_password' · 'email' (the tenant's e-mail step) ·
    'done' (a thank-you / submitted page) · 'form' (a step of the application) · 'unknown'."""
    u, t = str(url or ''), N(text)
    if 'login.icims.com' in u:
        if re.search(r'wrong (email|username) or password|incorrect (username|email|password)|用户名或密码错误|密码错误', t, re.I):
            return 'bad_password'
        return 'universal_password' if '/password' in u else 'universal_login'
    if re.search(r'unable to log in with the social account', t, re.I):
        return 'social_error'
    if DONE_RE.search(t) and not re.search(r'Step\s+\d+\s+of\s+\d+', t):
        return 'done'
    if re.search(r'Step\s+\d+\s+of\s+\d+', t) or re.search(r'/candidate\b|mode=apply|/questions?\b', u):
        return 'form'
    if re.search(r'/login\b', u) or re.search(r'enter your (email|information)', t, re.I):
        return 'email'
    return 'unknown'


SUBMITTED_RE = re.compile(r'thank you for (applying|your application|submitting)|application (has been |was )?(successfully )?submitted|'
                          r'application (has been )?received|application is complete|submission (has been received|complete)|'
                          r'you have successfully applied', re.I)
INACTIVITY_RE = re.compile(r'you will be logged out in \d+ seconds? due to inactivity', re.I)


def current_step(text):
    """The step bar's current step → (n, total, name); None without a '(Current Step)' item (parse_steps)."""
    s = parse_steps(text)
    return (s['current'], s['total'], s['name']) if s else None


def real_errors(errors):
    """Page error texts without the inactivity notice and blanks."""
    return [e for e in (errors or []) if N(e) and not INACTIVITY_RE.search(N(e))]


def submit_gate(submit, no_advance, steps, consent):
    """Pure (tested, scripts/test_icims_submit.py). May the runner press the final (hand-in) button now?
    → [decision, reason]: ['dry-run', 'no-advance' | 'not-approved'] · ['needs-user', 'unknown' | 'readback' | 'empty' |
    'page-error' | 'consent'] · ['press', 'ok']. `submit` = --submit AND an approved folder AND not already submitted."""
    if no_advance:
        return ['dry-run', 'no-advance']
    if not submit:
        return ['dry-run', 'not-approved']
    steps = steps or []
    if any(s.get('unknown') for s in steps):
        return ['needs-user', 'unknown']
    if any(s.get('problems') for s in steps) or any(f.get('ok') is not True for s in steps for f in s.get('fields') or []):
        return ['needs-user', 'readback']
    if not any(s.get('fields') for s in steps):
        return ['needs-user', 'empty']
    if real_errors(steps[-1].get('errors')):
        return ['needs-user', 'page-error']
    if consent != 'ok':
        return ['needs-user', 'consent']
    return ['press', 'ok']


def after_submit(url, text, before):
    """Pure (tested). The page after the final button: 'done' (a thank-you / submitted sentence, and no step bar or a
    last / Thank-you / Confirmation step) · 'next' (a later step) · 'refused' (the same or an earlier step; no bar but error
    words) · 'pending' (anything else → wait, then the receipt e-mail)."""
    t = N(text)
    cur = current_step(t)
    if SUBMITTED_RE.search(t) and (not cur or cur[0] >= cur[1] or re.search(r'thank|confirm|complete|submitted|success', cur[2], re.I)):
        return 'done'
    if cur:
        if before is None or cur[0] > before:
            return 'next'
        return 'refused'
    if before is not None and re.search(r'required|please correct|please check|invalid|error', t, re.I):
        return 'refused'
    return 'pending'


BEYOND_RE = re.compile(r'arbitration|class action|jury|waive|automated (telephone )?dial|prerecorded|artificial voice|marketing|'
                       r'promotional|newsletter|recruiting related messages|talent community|be bound by|'
                       r'(calls?|text messages?|texts|sms)\b.{0,40}\b(consent|agree)|(consent|agree)\w*\b.{0,60}\b(calls?|text messages?|texts|sms)\b', re.I)


def consent_gate(text, approved=()):
    """Pure (tested). The e-mail step's required consent text → 'ok' | 'ask'. 'ask' when it goes beyond the application
    (arbitration / waiver / automated calls / texts / marketing / talent community …) and none of the candidate's approved
    snippets (`config/profile.json → consents_approved[].contains`) is in it. A privacy notice and the interview terms Joey
    accepted 2026-11-03 (no AI tools in interviews, photos, background check) are 'ok'; no text (no box) is 'ok'."""
    t = N(text)
    if not t or not BEYOND_RE.search(t):
        return 'ok'
    low = t.lower()
    snips = [(x or {}).get('contains', '') if isinstance(x, dict) else str(x or '') for x in (approved or [])]
    return 'ok' if any(N(s) and N(s).lower() in low for s in snips) else 'ask'


def same(want, got):
    """Read-back comparison: case / space-insensitive; phones by the last 10 digits; a file field passes on any file name."""
    w, g = N(want).lower(), N(got).lower()
    if re.fullmatch(r'[\d\s()+.-]{7,}', w):
        return re.sub(r'\D', '', g)[-10:] == re.sub(r'\D', '', w)[-10:]
    return w == g


# ---------- answers ----------
def answer(questions):
    """[{key, label, type, options}] → {key: answerFor result} through rules_bridge.js (the shared answer rules)."""
    r = subprocess.run(['node', os.path.join(HERE, 'rules_bridge.js'), RULES], input=json.dumps({'fields': questions, 'jd': '', 'company': (JOB or {}).get('company') or ''}),   # company: referrer pool (JSA-195)
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout or '{}')


def keychain(service):
    r = subprocess.run(['security', 'find-generic-password', '-s', service, '-a', 'alex.rivera@example.com', '-w'],
                       capture_output=True, text=True)
    return r.stdout.rstrip('\n') if r.returncode == 0 else ''


def now():
    return datetime.now().isoformat(timespec='seconds')


# ---------- page ----------
EXTRACT = r"""() => {
  const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const txt = e => (e ? e.innerText || e.textContent || '' : '').replace(/\s+/g, ' ').trim();
  const labelOf = e => { let l = '';
    if (e.id) { const x = document.querySelector('label[for="' + CSS.escape(e.id) + '"]'); if (x) l = txt(x); }
    if (!l && e.id) { const x = document.getElementById('label_' + e.id); if (x) l = txt(x); }
    if (!l && e.closest('label')) l = txt(e.closest('label'));
    if (!l) l = e.getAttribute('data-label') || e.getAttribute('aria-label') || e.placeholder || '';
    return l; };
  const out = [], seen = new Set();
  for (const e of document.querySelectorAll('input, select, textarea')) {
    const ty = (e.type || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'image', 'reset', 'search'].includes(ty) || e.classList.contains('dropdown-search')) continue;
    const dd = e.tagName === 'SELECT' && e.getAttribute('icimsdropdown-enabled') === '1';
    const shown = dd ? vis(document.getElementById(e.id + '_icimsDropdown') || e) : (ty === 'file' ? true : vis(e));
    if (!shown || e.disabled) continue;
    const req = e.getAttribute('i_required') === 'true' || e.required || e.getAttribute('aria-required') === 'true';
    if (ty === 'radio') {
      if (seen.has(e.name)) continue; seen.add(e.name);
      const group = [...document.querySelectorAll('input[type=radio][name="' + CSS.escape(e.name) + '"]')];
      const fs = e.closest('fieldset'); const q = fs ? txt(fs.querySelector('legend')) : '';
      const lab = q || (document.getElementById('label_' + e.name) ? txt(document.getElementById('label_' + e.name)) : '') || e.name;
      out.push({ id: e.name, name: e.name, kind: 'radio', label: lab, required: group.some(g => g.getAttribute('i_required') === 'true' || g.required),
                 options: group.map(g => labelOf(g)), value: (group.find(g => g.checked) ? labelOf(group.find(g => g.checked)) : '') });
      continue;
    }
    const f = { id: e.id || e.name, name: e.name, label: labelOf(e), required: !!req };
    if (e.tagName === 'SELECT') {
      f.kind = dd ? 'dropdown' : 'select'; f.ajax = e.getAttribute('icimsdropdown-ajax') === '1';
      f.typeahead = /TypeToSearchText/.test(e.className);
      f.options = [...e.options].map(o => txt(o)).filter(t => t && !/make a selection|作出选择|please select/i.test(t));
      const fake = document.getElementById(e.id + '_fakeSelected_icimsDropdown');
      f.value = dd ? (fake && !fake.querySelector('.dropdown-placeholder') ? txt(fake) : '') : (e.selectedIndex > 0 || (e.options[e.selectedIndex] && e.options[e.selectedIndex].value) ? txt(e.options[e.selectedIndex]) : '');
    } else if (ty === 'checkbox') { f.kind = 'checkbox'; f.value = e.checked; }
    else if (ty === 'file') { f.kind = 'file'; f.value = (e.files && e.files[0] && e.files[0].name) || ''; }
    else if (ty === 'password') { f.kind = 'password'; f.value = e.value ? '(set)' : ''; }
    else { f.kind = e.tagName === 'TEXTAREA' ? 'textarea' : 'text'; f.value = e.value || ''; }
    out.push(f);
  }
  const btns = [...document.querySelectorAll('input[type=submit], button[type=submit], a.iCIMS_Action_Button, button.iCIMS_Action_Button')]
     .filter(vis).map(b => ({ id: b.id, text: (b.value || txt(b)).slice(0, 60) }));
  const uploaded = txt(document.querySelector('.iCIMS_ResumeFileName, .resumeFileName, [id*=ResumeFileName]'));
  const errors = [...document.querySelectorAll('.iCIMS_ErrorMessage, .iCIMS_Error, .error, [id$=_error]')].filter(vis).map(txt).filter(Boolean).slice(0, 12);
  return { fields: out, buttons: btns, uploaded, errors, text: txt(document.body).slice(0, 6000) };
}"""


class Icims:
    def __init__(self, page, log, out):
        self.page, self.log, self.out = page, log, out

    def frame(self):
        return next((f for f in self.page.frames if f.name == IFRAME), None) or self.page.main_frame

    def state(self):
        return self.frame().evaluate(EXTRACT)

    def captcha_up(self):
        for fr in self.page.frames:
            if 'hcaptcha' in fr.url and 'frame=challenge' in fr.url:
                try:
                    el = fr.frame_element()
                    box = el.bounding_box()
                    if box and box['width'] > 50 and box['height'] > 50 and el.is_visible():
                        return True
                except Exception:
                    pass
        return False

    # --- widgets
    def fill_text(self, fid, value):
        loc = self.frame().locator(f'[id="{fid}"]')
        loc.fill(str(value)); loc.dispatch_event('change'); loc.dispatch_event('blur')

    def pick_dropdown(self, fid, value, search=None):
        """Open an iCIMS dropdown, type `search` (default: the value without a leading '(+1)'-style code) into its search
        box, wait until the list has settled, click the option whose title equals `value` (else starts with it).
        Returns None on success, else the titles seen."""
        fr = self.frame()
        a = fr.locator(f'[id="{fid}_icimsDropdown"]')
        a.scroll_into_view_if_needed(); a.click(); time.sleep(0.6)
        box = fr.locator(f'[id="{fid}_icimsDropdown_ctnr"] input.dropdown-search')
        if box.count() and box.first.is_visible():                 # short lists have no (visible) search box
            q = search or re.sub(r'^\(\+?\d+\)\s*', '', str(value))
            box.fill(''); box.press_sequentially(q[:40], delay=25)
        opts = fr.locator(f'[id="{fid}_dropdown-results"] li[role=option]')
        titles, last = [], None
        for _ in range(8):                                      # ajax search: wait until two reads agree
            time.sleep(0.8)
            titles = [N(opts.nth(i).get_attribute('title') or '') for i in range(min(opts.count(), 80))]
            if titles == last:
                break
            last = titles
        want = N(value).lower()
        idx = next((i for i, t in enumerate(titles) if t.lower() == want), None)
        if idx is None:
            idx = next((i for i, t in enumerate(titles) if want and t.lower().startswith(want)), None)
        if idx is None:
            self.page.keyboard.press('Escape')
            return titles
        li = opts.nth(idx)
        try:
            li.scroll_into_view_if_needed(timeout=3000); li.click(timeout=5000)
        except Exception:
            li.evaluate("e => { e.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})); e.dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); e.click(); }")
        time.sleep(0.8)
        return None

    def enter_manually(self, fid, value):
        """iCIMS type-to-search text field (street address with geolocation suggestions): choose '— Enter Manually —',
        which turns it into a plain text box, then type the profile value — a suggestion could rewrite city / ZIP."""
        fr = self.frame()
        a = fr.locator(f'[id="{fid}_icimsDropdown"]')
        if a.count():
            a.scroll_into_view_if_needed(); a.click(); time.sleep(0.6)
            box = fr.locator(f'[id="{fid}_icimsDropdown_ctnr"] input.dropdown-search')
            if box.count() and box.first.is_visible():
                box.press_sequentially(str(value)[:20], delay=25); time.sleep(1.5)
            man = fr.locator(f'[id="{fid}_dropdown-results"] li[role=option]').filter(has_text=re.compile('enter manually|手动输入', re.I))
            if not man.count():
                self.page.keyboard.press('Escape')
                return 'no "Enter Manually" option'
            man.first.scroll_into_view_if_needed(); man.first.click(); time.sleep(1.0)
        self.fill_text(fid, value)
        return None

    def read_dropdown(self, fid):
        fr = self.frame()
        return fr.evaluate("""(id) => { const f = document.getElementById(id + '_fakeSelected_icimsDropdown');
            const s = document.getElementById(id);
            if (s && s.tagName !== 'SELECT') return s.value || '';
            if (f && !f.querySelector('.dropdown-placeholder')) return (f.innerText || '').trim();
            return s && s.selectedIndex >= 0 && s.options[s.selectedIndex] && s.options[s.selectedIndex].value ? s.options[s.selectedIndex].text.trim() : ''; }""", fid)

    def dropdown_options(self, fid):
        """Open an iCIMS dropdown once and read its option titles (ajax lists load on open)."""
        fr = self.frame()
        a = fr.locator(f'[id="{fid}_icimsDropdown"]')
        try:
            a.scroll_into_view_if_needed(); a.click(); time.sleep(1.2)
            opts = fr.locator(f'[id="{fid}_dropdown-results"] li[role=option]')
            titles = [N(opts.nth(i).get_attribute('title') or '') for i in range(min(opts.count(), 400))]
        finally:
            self.page.keyboard.press('Escape'); time.sleep(0.3)
        return [t for t in titles if t and not re.search(r'make a selection|作出选择|please select', t, re.I)]

    def set_radio(self, name, option):
        fr = self.frame()
        ok = fr.evaluate("""([name, opt]) => { const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            for (const r of document.querySelectorAll('input[type=radio][name="' + CSS.escape(name) + '"]')) {
              const l = document.querySelector('label[for="' + CSS.escape(r.id) + '"]') || r.closest('label');
              if (l && norm(l.innerText) === norm(opt)) { r.click(); return true; } } return false; }""", [name, option])
        return ok


def uploaded_name(ic, fid):
    """The file name iCIMS holds for an upload slot (`<base>_FileName`, base = the input id without `_File`)."""
    base = re.sub(r'_File$', '', fid)
    return ic.frame().evaluate("(b) => { const e = document.getElementById(b + '_FileName'); return e ? e.value : ''; }", base)


COVER_RE = re.compile(r'cover\s*letter|\bcover\b|motivation letter', re.I)


def cover_slot(label):
    """A file slot for the cover letter only ('Cover Letter'); 'Resume or cover letter' stays the resume slot."""
    return bool(COVER_RE.search(label or '')) and not re.search(r'resume|\bcv\b', label or '', re.I)


def fill_step(ic, answers_override, resume, log, _tried=None):
    """Answer, fill and read back every field of the current step. Returns (fields, problems, unknown_required)."""
    _tried = set() if _tried is None else _tried
    st = ic.state()
    fields = st['fields']
    qs = []
    for f in fields:
        if f['kind'] in ('file', 'password'):
            continue
        if f['kind'] == 'dropdown' and not f['options'] and not f.get('typeahead'):
            f['options'] = ic.dropdown_options(f['id'])
        f['rlabel'] = field_label(f['id'], f['label'])
        t = {'text': 'text', 'textarea': 'textarea', 'select': 'select', 'dropdown': 'select', 'radio': 'radio', 'checkbox': 'checkbox'}[f['kind']]
        if f.get('typeahead'):
            t = 'text'
        qs.append({'key': f['id'], 'label': f['rlabel'], 'type': t, 'options': f.get('options') or []})
    rows, problems, unknown = [], [], []
    for f in fields:                                            # the resume first: its upload posts the form and reloads it
        is_cover = f['kind'] == 'file' and cover_slot(f['label'])
        doc = COVER if is_cover else (resume if f['kind'] == 'file' and re.search(r'resume|cv', f['label'], re.I) else None)
        if doc and f['id'] not in _tried and not uploaded_name(ic, f['id']):
            _tried.add(f['id'])                                 # one upload per slot: no loop when the name never shows
            ic.frame().locator(f'[id="{f["id"]}"]').set_input_files(doc)
            log(('cover letter' if is_cover else 'resume') + ' uploaded (iCIMS may post the form) — waiting for the reload')
            time.sleep(4)
            for _ in range(20):
                try:
                    if uploaded_name(ic, f['id']) and not ic.frame().evaluate("() => { const l = document.querySelector('[id$=Resume_Loading]'); return !!(l && (l.offsetWidth || l.offsetHeight)); }"):
                        break
                except Exception:
                    pass
                time.sleep(1.5)
            time.sleep(2)
            return fill_step(ic, answers_override, resume, log, _tried)
    ans = answer(qs) if qs else {}
    for f in fields:
        lab = f.get('rlabel') or field_label(f['id'], f['label'])
        row = {'id': f['id'], 'label': lab, 'kind': f['kind'], 'required': f['required']}
        if f['kind'] == 'password':
            continue
        if f['kind'] == 'file':
            if cover_slot(lab):                                 # Joey 2026-11-03: optional cover-letter slots get the letter too
                if COVER:
                    row.update(want=os.path.basename(COVER), rule='cover_letter')
                elif f['required']:
                    unknown.append(lab); row.update(want=None, rule=None)
                else:
                    row.update(want=None, rule='cover_letter', note='cover letter slot (optional) — no *Cover_Letter*.pdf in the folder')
            elif re.search(r'resume|cv', lab, re.I) and resume:
                row.update(want=os.path.basename(resume), rule='resume')
            elif f['required']:
                unknown.append(lab); row.update(want=None, rule=None)
            rows.append(row); continue
        a = answers_override.get(f['id']) or answers_override.get(lab) or ans.get(f['id']) or {}
        if f['kind'] == 'checkbox' and f.get('name') == 'override' and str(f['id']).startswith('address_'):
            # "City, Zip Code and State combination was not able to be verified. Use this address anyway? Yes": the
            # address is the profile's own (config/profile.json answers.address / zip / city / state) → keep it
            a = {'status': 'ok', 'value': True, 'rule': 'address_override'}
            row['label'] = lab = 'Use this address anyway (address check)'
        if a.get('status') != 'ok' or (a.get('rule') == 'middle_initial' and not f['required']):
            row.update(want=None, rule=a.get('rule'), page=f['value'])
            if f['required'] and not f['value']:
                unknown.append(lab)
            elif f['required'] and f['value']:
                row['note'] = 'prefilled by the site, no rule — kept'
            rows.append(row); continue
        want = a.get('value')
        if f['kind'] == 'checkbox':
            want = bool(want) if isinstance(want, bool) else bool(re.match(r'^(yes|true|i agree|i accept|i consent)', str(want), re.I))
        row.update(want=want, rule=a.get('rule'))
        try:
            if f['kind'] in ('text', 'textarea') or f.get('typeahead'):
                if f.get('typeahead'):
                    err = ic.enter_manually(f['id'], want) if N(f['value']).lower() != N(want).lower() else None
                    if err:
                        row['error'] = err
                elif N(f['value']).lower() != N(want).lower():
                    ic.fill_text(f['id'], want)
            elif f['kind'] == 'select':
                ic.frame().locator(f'[id="{f["id"]}"]').select_option(label=str(want))
            elif f['kind'] == 'dropdown':
                if N(f['value']).lower() != N(want).lower():
                    miss = ic.pick_dropdown(f['id'], want, a.get('combo'))
                    if miss is not None:
                        row['error'] = 'option not found: ' + ' / '.join(miss[:5])
            elif f['kind'] == 'radio':
                if not ic.set_radio(f['id'], want):
                    row['error'] = 'radio option not found'
            elif f['kind'] == 'checkbox':
                loc = ic.frame().locator(f'[id="{f["id"]}"]')
                (loc.check if want else loc.uncheck)()
        except Exception as e:
            row['error'] = f'{type(e).__name__}: {str(e)[:120]}'
        rows.append(row)
    time.sleep(1.0)
    # a list that appears only after "How did you hear about us? = Job Board" ("Please specify": Indeed / LinkedIn …):
    # the row's own board when listed, else the profile's default (Joey 2026-11-03; job_board.py)
    heard = next((r for r in rows if r.get('rule') == 'how_heard' and re.search(r'job\s*board', str(r.get('want') or ''), re.I)), None)
    if heard:
        done = {r['id'] for r in rows if r.get('want') is not None}
        for g in ic.state()['fields']:                         # new lists, and ones already shown but left unanswered
            if g['id'] in done or g['kind'] not in ('select', 'dropdown') or N(g.get('value')):
                continue
            rows[:] = [r for r in rows if r['id'] != g['id']]   # replace its "no rule" row
            opts = g.get('options') or (ic.dropdown_options(g['id']) if g['kind'] == 'dropdown' else [])
            pick = job_board.board_pick(opts, JOB.get('source'), JOB.get('url'), BOARD_DEFAULT)
            if not pick:
                continue
            row = {'id': g['id'], 'label': re.sub(r'^error:\s*', '', field_label(g['id'], g['label']), flags=re.I), 'kind': g['kind'], 'required': g['required'],
                   'want': pick, 'rule': 'how_heard_board'}
            try:
                if g['kind'] == 'select':
                    ic.frame().locator(f'[id="{g["id"]}"]').select_option(label=pick)
                else:
                    miss = ic.pick_dropdown(g['id'], pick, None)
                    if miss is not None:
                        row['error'] = 'option not found: ' + ' / '.join(miss[:5])
            except Exception as e:
                row['error'] = f'{type(e).__name__}: {str(e)[:120]}'
            unknown[:] = [u for u in unknown if N(re.sub(r'^error:\s*', '', u, flags=re.I)).lower() != N(row['label']).lower()]
            log(f'job-board follow-up "{row["label"]}" → {pick}')
            rows.append(row)
        time.sleep(1.0)
    # read back
    st2 = ic.state()
    by = {f['id']: f for f in st2['fields']}
    for row in rows:
        g = by.get(row['id'], {})
        got = g.get('value', '')
        if row['kind'] == 'dropdown':
            got = ic.read_dropdown(row['id'])
        if row['kind'] == 'file':
            got = uploaded_name(ic, row['id']) or ''
            row['page'] = got
            row['ok'] = bool(got) if row.get('want') else not row['required']
            continue
        row['page'] = got
        if row.get('want') is None:
            row['ok'] = not (row['required'] and not got)
        elif row['kind'] == 'checkbox':
            row['ok'] = bool(got) == bool(row['want'])
        else:
            row['ok'] = same(row['want'], got) or (row['kind'] in ('dropdown', 'select') and N(got).lower().startswith(N(row['want']).lower()))
        if not row['ok']:
            problems.append(f"{row['label']}: want {row.get('want')!r}, page {got!r}" + (f" ({row['error']})" if row.get('error') else ''))
    return rows, problems, unknown, st2


JOB = {}                                                       # the store row (--job): its source / url pick the job board
COVER = None                                                   # the --folder's *Cover_Letter*.pdf
SUBMIT = False                                                 # set by main() only after the approval / not-yet-submitted gates
RUN = None                                                     # runner_common.Run of this run (JSA-187)
RES = None                                                     # the current run's result (survives a runner error)
try:
    BOARD_DEFAULT = (json.load(open(jpaths.config('profile.json'), encoding='utf-8'))
                     .get('answers', {}).get('how_heard_board', {}))
    BOARD_DEFAULT = [BOARD_DEFAULT.get('default') or 'LinkedIn'] + list(BOARD_DEFAULT.get('fallback') or [])
except (OSError, ValueError):
    BOARD_DEFAULT = ['LinkedIn', 'Indeed']


WAIT_CAPTCHA = 0.0                                             # --wait-captcha minutes
try:                                                           # e-mail-step consents Joey approved once (shared with Oracle)
    PROFILE_CONSENTS = json.load(open(jpaths.config('profile.json'), encoding='utf-8')).get('consents_approved') or []
except (OSError, ValueError):
    PROFILE_CONSENTS = []


def hold_for_captcha(ic, out, where, log):
    """A visible hCaptcha challenge → park it for Joey (human_check: push + open list) and wait up to WAIT_CAPTCHA minutes
    for it to go away. Never answered by the runner. True = no challenge (any more)."""
    if not ic.captcha_up():
        return True
    log(f'hCaptcha challenge at {where} → Joey (never answered by the runner)')
    human_check.park(out, 'icims', ic.page.url, [{'question': f'iCIMS hCaptcha at {where}'}], notify=True)
    end = time.time() + WAIT_CAPTCHA * 60
    while time.time() < end and ic.captcha_up():
        time.sleep(5)
    if ic.captcha_up():
        return False
    human_check.resolve(out, 'solved by Joey')
    log('hCaptcha gone (solved in the tab) — continuing'); time.sleep(6)
    return True


def signin(ic, log, created=False):
    """login.icims.com: e-mail → password from the Keychain (Joey's own `jobagent-icims`, then the agent's regular / long). Returns 'ok' | 'bad_password' | page kind."""
    pg = ic.page
    k = classify(pg.url, pg.inner_text('body'))
    if k == 'universal_login':
        pg.locator('#username').click(); pg.keyboard.press('Escape')
        pg.locator('#username').press_sequentially('alex.rivera@example.com', delay=25)
        pg.locator('button[name=action]').first.click(); time.sleep(5)
        k = classify(pg.url, pg.inner_text('body'))
    if k != 'universal_password':
        return k
    for svc in ('jobagent-icims', 'jobagent-workday', 'jobagent-workday-long'):   # jobagent-icims = Joey's own password (2026-11-03)
        pw = keychain(svc)
        if not pw:
            continue
        pg.locator('#password').fill(pw); pg.locator('button[name=action]').first.click(); time.sleep(8)
        k = classify(pg.url, pg.inner_text('body'))
        log(f'universal sign-in with Keychain item {svc}: {k}')
        if k not in ('bad_password', 'universal_password', 'universal_login'):   # back on the e-mail box = not signed in (West Bend 11-03)
            return 'ok'
        if k == 'universal_login':
            return 'bad_password'                              # stop: every further try counts toward a lockout
    return 'bad_password'


def run(page, posting, resume, log, out, wait_captcha=0, answers_override=None):
    global RES
    ic = Icims(page, log, out)
    res = RES = {'status': 'blocked', 'problems': [], 'steps': [], 'unknown': [], 'account': None}   # kept on a runner error
    kind, url = login_url(posting)
    if not kind:
        res['problems'].append(f'not an iCIMS posting: {posting}'); return res
    attached = page.url.startswith('http') and classify(page.url, ic.frame().inner_text('body')) == 'form'
    if attached:
        log(f'attached tab is already on an application step: {page.url[:100]}')
        try:                                                    # the e-mail step ran earlier: its consent text is in the last form_check
            prev = json.load(open(os.path.join(out, 'form_check.json'))).get('consent_text')
        except (OSError, ValueError):
            prev = None
        if prev:
            res['consent_text'], res['consent'] = prev, consent_gate(prev, PROFILE_CONSENTS)
        return steps_loop(ic, page, res, resume, log, out, answers_override)
    if kind == 'jibe':
        page.goto(url, wait_until='domcontentloaded', timeout=60000); time.sleep(4)
        href = page.evaluate("""() => { const a = document.querySelector('a#link-apply, a[href*=".icims.com/jobs/"][href*="login"], a[href*="mode=apply"]');
                                       return a ? a.href : ''; }""")
        log(f'jibe front end → apply link {href}')
        k2, url = login_url(href)
        res['icims_url'] = url                                  # the tenant's own pages of this job (tabs closed after a submit)
        if not k2:
            res['problems'].append(f'jibe page has no iCIMS apply link ({href!r})'); return res
    if True:                                                    # always a fresh e-mail page (a stale one keeps Next disabled)
        page.goto(url, wait_until='domcontentloaded', timeout=60000); time.sleep(5)
    # e-mail step — the tenant page often redirects once (adds mobile / width params) and reloads the iframe: wait for it
    last = None
    for _ in range(10):
        time.sleep(1.5)
        fr = ic.frame()
        cur = fr.url
        if cur == last and fr.locator('#email').count():
            break
        last = cur
    for attempt in range(2):
        fr = ic.frame()
        if not fr.locator('#email').count():
            break
        fr.locator('#email').fill('alex.rivera@example.com')
        if fr.locator('#accept_gdpr').count():
            res['consent_text'] = N(fr.inner_text('body'))[:1500]
            res['consent'] = consent_gate(res['consent_text'], PROFILE_CONSENTS)
            fr.locator('#accept_gdpr').check()
            log('privacy consent ticked (required to continue; text saved in form_check.json → consent_text)'
                + ('' if res['consent'] == 'ok' else ' — wording beyond the application: NO submit until Joey approves it'))
        if fr.locator('#email').input_value() != 'alex.rivera@example.com':
            continue                                            # the iframe reloaded under us: fill again
        fr.wait_for_selector('#enterEmailSubmitButton:enabled', timeout=30000); fr.locator('#enterEmailSubmitButton').click()   # disabled while hCaptcha loads
        for _ in range(12):                                     # a challenge, or the next page
            time.sleep(1.5)
            if ic.captcha_up() or 'login.icims.com' in page.url:
                break
            try:
                if not ic.frame().locator('#email').count():
                    break
            except Exception:
                pass
        break
    if not hold_for_captcha(ic, out, 'the e-mail step', log):
        res['status'] = 'captcha'; res['problems'].append('hCaptcha at the e-mail step not solved'); return res
    pressed_again = False
    for _ in range(10):                                         # wait for the next page
        k = classify(page.url, ic.frame().inner_text('body') if 'login.icims.com' not in page.url else page.inner_text('body'))
        if k not in ('email',):
            break
        time.sleep(3)
        if not pressed_again and 'login.icims.com' not in page.url and ic.frame().locator('#enterEmailSubmitButton').count() \
                and not ic.captcha_up():                        # challenge solved but the page stayed: press Next once more
            pressed_again = True
            log('still on the e-mail step after the challenge — pressing Next once more')
            ic.frame().wait_for_selector('#enterEmailSubmitButton:enabled', timeout=30000); ic.frame().locator('#enterEmailSubmitButton').click(); time.sleep(4)
            if not hold_for_captcha(ic, out, 'the e-mail step (again)', log):
                res['status'] = 'captcha'; res['problems'].append('hCaptcha at the e-mail step not solved'); return res
    if k in ('universal_login', 'universal_password'):
        r = signin(ic, log)
        if r != 'ok':
            res['status'] = 'signin'; res['account'] = 'universal login (login.icims.com): Keychain password rejected'
            res['problems'].append('iCIMS universal login rejected both Keychain passwords — Joey signs in (or resets the password to the Keychain one)')
            return res
        time.sleep(6)
    k = classify(page.url, ic.frame().inner_text('body'))
    if k == 'social_error':
        res['status'] = 'signin'; res['problems'].append('social sign-in has no linked iCIMS account'); return res
    if k != 'form':
        res['problems'].append(f'unexpected page after sign-in: {k} {page.url[:120]}'); return res
    return steps_loop(ic, page, res, resume, log, out, answers_override)


def button_sel(btn):
    return f'[id="{btn["id"]}"]' if btn['id'] else f'input[type=submit][value="{btn["text"]}"], button:has-text("{btn["text"]}")'


def page_text(ic):
    """The tab's text: the top page and the iCIMS iframe (a Jibe front end may show its own thank-you page on top)."""
    parts = []
    for get in (lambda: ic.page.inner_text('body'), lambda: ic.frame().inner_text('body')):
        try:
            parts.append(get())
        except Exception:
            pass
    return ' '.join(parts)[:30000]


def confirmed(page, res, out, log, how):
    res['status'], res['confirmed_by'] = 'submitted', 'page'
    log(f'CONFIRMED by the page: {how}')
    try:
        page.screenshot(path=os.path.join(out, 'submitted_confirmation.png'), full_page=True)
    except Exception:
        pass
    return res


def submit_final(ic, page, res, btn, n, steps, log, out):
    """Press the hand-in button (JSA-093; only after submit_gate said 'press') and judge the page with after_submit:
    'done' → submitted (screenshot) · 'next' → a further step, the caller fills it · 'refused' → needs-user, nothing sent ·
    'pending' → the receipt e-mail (Gmail read-only, 180 s) → submitted, else unconfirmed. A hCaptcha → Joey."""
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    before = steps['current'] if steps else None
    ic.frame().locator(button_sel(btn)).first.click()
    res['pressed'] = res.get('pressed', 0) + 1
    res.setdefault('pressed_at', since.isoformat())
    log(f'step {n}: "{btn["text"]}" clicked (submit)')
    k = 'pending'
    for i in range(30):                                         # up to ~60 s (+ the CAPTCHA wait)
        time.sleep(2)
        if ic.captcha_up() and not hold_for_captcha(ic, out, f'the submit ("{btn["text"]}", step {n})', log):
            res['status'] = 'captcha'; res['problems'].append(f'step {n}: hCaptcha after "{btn["text"]}" not solved — not submitted')
            return 'stop'
        k = after_submit(page.url, page_text(ic), before)
        if k == 'done':
            confirmed(page, res, out, log, f'"{btn["text"]}" (step {n})'); return 'done'
        if k == 'next':
            res['maybe_in'] = True                              # a hand-in-like button moved on: the application may be in already
            log(f'step {n}: "{btn["text"]}" led to a further step — continuing'); return 'next'
        if k == 'refused' and i >= 5:
            try:
                busy = ic.frame().evaluate("(id) => { const b = id && document.getElementById(id); return !!(b && b.disabled); }", btn['id'])
            except Exception:
                busy = True
            if not busy:                                        # the post is over and the same step is still there
                break
    if k == 'refused':
        try:
            errs = real_errors(ic.state()['errors'])
        except Exception:
            errs = []
        res['status'] = 'needs-user'; res['problems'].append(f'step {n}: "{btn["text"]}" did not go through (nothing sent): ' + ' | '.join(errs[:4]))
        return 'stop'
    return by_email(res, since, log)


def by_email(res, since, log):
    """No thank-you page: the company's receipt e-mail (gmail_code, read-only) → submitted, else unconfirmed."""
    company = (JOB or {}).get('company') or ''
    subj = None
    if company:
        log('no thank-you page — waiting up to 180 s for the receipt e-mail (Gmail read-only)')
        try:
            import gmail_code
            subj = gmail_code.wait_for_mail(since, company, timeout=180)
        except Exception as e:
            log(f'receipt e-mail check failed: {type(e).__name__}')
    if subj:
        res['status'], res['confirmed_by'] = 'submitted', 'email'; log(f'company e-mail: {subj[:100]}')
        return 'done'
    res['status'] = 'unconfirmed'
    res['problems'].append('pressed the hand-in button but no confirmation page and no company e-mail — check Gmail')
    return 'stop'


def steps_loop(ic, page, res, resume, log, out, answers_override):
    for _ in range(10):
        st = ic.state()
        steps = parse_steps(st['text'])
        n = steps['current'] if steps else len(res['steps']) + 1
        rows, problems, unknown, st2 = fill_step(ic, answers_override or {}, resume, log)
        pw_fields = [f for f in st2['fields'] if f['kind'] == 'password']
        if pw_fields:                                           # classic portal: new tenant profile → Keychain password
            pw = keychain('jobagent-workday')
            if re.search(r'minimum of (1[2-9]|2\d) characters|at least (1[2-9]|2\d) characters', st2['text'], re.I):
                pw = keychain('jobagent-workday-long') or pw
            if not pw:
                problems.append('no Keychain password for the new profile')
            for f in pw_fields:
                ic.frame().locator(f'[id="{f["id"]}"]').fill(pw)
            res['account'] = f'tenant profile created with the Keychain password ({urlparse(page.url).hostname})'
        try:
            page.screenshot(path=os.path.join(out, f'step_{n}.png'), full_page=True)
        except Exception:
            pass
        btn = pick_button(st2['buttons'])
        res['steps'].append({'step': n, 'name': steps['name'] if steps else '', 'fields': rows, 'problems': problems,
                             'unknown': unknown, 'button': btn and btn['text'], 'errors': st2['errors']})
        for r in rows:
            log(f"  [{n}] {'ok ' if r.get('ok') else 'BAD'} {r['label'][:48]:48s} → {str(r.get('page'))[:40]}" + (f"  ({r['error']})" if r.get('error') else ''))
        if unknown:
            res['unknown'] += [f'step {n}: {u}' for u in unknown]
        if problems or unknown:
            res['status'] = 'needs-user'; res['problems'] += [f'step {n}: {p}' for p in problems]
            return res
        if not btn:
            res['problems'].append(f'step {n}: no button'); return res
        if NO_ADVANCE or is_final(btn['text'], steps):
            decision, why = submit_gate(SUBMIT, NO_ADVANCE, res['steps'], res.get('consent', 'ok'))
            if decision == 'dry-run':
                res['status'] = 'dry-run'
                log(f'step {n}/{steps and steps["total"]}: last step filled and read back — stop BEFORE "{btn["text"]}" (dry-run)')
                return res
            if decision != 'press':
                res['status'] = 'needs-user'
                res['problems'].append(f'step {n}: not submitted — gate {why}'
                                       + (': ' + ' | '.join(real_errors(st2['errors'])[:4]) if why == 'page-error' else '')
                                       + (' (e-mail-step consent wording beyond the application — Joey approves it once)' if why == 'consent' else ''))
                return res
            if RUN is not None and not RUN.gate_inside(res):  # JSA-186/187: canon + approval, right before the hand-in
                log(f'step {n}: common gate — NOT submitted'); return res
            if RUN is not None:
                RUN.mark('submit')
            if submit_final(ic, page, res, btn, n, steps, log, out) == 'next':
                continue                                        # the hand-in button led to a further step: fill it too
            return res
        log(f'step {n} → "{btn["text"]}"')
        ic.frame().locator(button_sel(btn)).first.click(); time.sleep(8)
        if not hold_for_captcha(ic, out, f'"{btn["text"]}" (step {n})', log):
            res['status'] = 'captcha'; res['problems'].append(f'hCaptcha after step {n} not solved'); return res
        for _ in range(20):                                     # the post is in flight while the button stays disabled
            try:
                st3 = ic.state()
                busy = ic.frame().evaluate("(id) => { const b = id && document.getElementById(id); return !!(b && b.disabled); }", btn['id'])
            except Exception:
                st3, busy = None, True                          # the iframe is navigating
            s3 = parse_steps(st3['text']) if st3 else None
            if st3 and not busy or (s3 and steps and s3['current'] != steps['current']):
                break
            time.sleep(2)
        if st3 is None:
            st3 = ic.state()
        s3 = parse_steps(st3['text'])
        if classify(page.url, st3['text']) == 'done':
            if SUBMIT:                                          # approved batch, every step read back: record what happened
                return confirmed(page, res, out, log, f'thank-you page after "{btn["text"]}" (step {n})')
            res['problems'].append('a thank-you page appeared — the application may have been submitted'); return res
        if s3 and steps and s3['current'] == steps['current']:
            res['status'] = 'needs-user'; res['problems'].append(f'step {n} did not advance: ' + ' | '.join(st3['errors'][:5]))
            return res
    res['problems'].append('more than 10 steps'); return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url'); ap.add_argument('--job'); ap.add_argument('--resume'); ap.add_argument('--track'); ap.add_argument('--out')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222')
    ap.add_argument('--wait-captcha', type=float, default=None, help='minutes to wait for Joey to clear a hCaptcha (default 0; 10 with --submit)')
    ap.add_argument('--attach', help='reuse the open tab whose URL contains this text'); ap.add_argument('--keep-tab', action='store_true')
    ap.add_argument('--no-advance', action='store_true', help='fill and read back the current step, press nothing')
    ap.add_argument('--answers', help='JSON file {field id or label: {"status": "ok", "value": …}} for answers Joey gave')
    ap.add_argument('--folder', help='application folder (job.json, tailored resume, *Cover_Letter*.pdf); out = the folder')
    ap.add_argument('--submit', action='store_true', help='press the hand-in button when every gate passes (needs --folder in an approved batch)')
    a = ap.parse_args()
    import run_form as RF                                       # shared gates and tab cleanup (approved_for / already_submitted / queue / push)
    folder = jpaths.folder(a.folder) if a.folder else None   # as typed, else under the data home (ADR-0008)
    if folder and os.path.exists(os.path.join(folder, 'job.json')):
        fj = json.load(open(os.path.join(folder, 'job.json')))
        a.job = a.job or fj.get('id'); a.url = a.url or fj.get('ats_url') or fj.get('url'); a.track = a.track or fj.get('track')
        pdfs = sorted(x for x in os.listdir(folder) if x.lower().endswith('.pdf') and 'resume' in x.lower())
        a.resume = a.resume or (os.path.join(folder, pdfs[0]) if pdfs else None); a.out = a.out or folder
        if RF.already_submitted(folder):
            print(f'{os.path.basename(folder)}: already submitted — nothing to do'); print('STATUS already-submitted'); return
    else:
        fj = {}
    if a.submit and not fj:
        sys.exit('--submit needs --folder with job.json (approval, tailored resume and the tracker row come from it)')
    job = {}
    if a.job:
        for line in open(jpaths.data('store', 'jobs.jsonl'), encoding='utf-8'):
            r = json.loads(line)
            if r.get('id') == a.job:
                job = r; break
    posting = a.url or job.get('ats_url') or job.get('url')
    if not login_url(posting)[0]:
        sys.exit(f'not an iCIMS posting: {posting}')
    track = a.track or TRACKS.get(job.get('track'), 'Data_Analyst')
    resume = a.resume or jpaths.resume('2026-10', f'Alex_Rivera_Resume_{track}_A-Classic.pdf')
    m = re.search(r'/jobs/(\d+)', posting)
    out = os.path.abspath(a.out or os.path.join(DATA, 'dryrun', 'icims', (urlparse(posting).hostname or 'x').split('.')[0] + '_' + (m.group(1) if m else 'job')))
    os.makedirs(out, exist_ok=True)
    over = json.load(open(a.answers)) if a.answers else {}
    global NO_ADVANCE, WAIT_CAPTCHA, JOB, COVER, SUBMIT, RUN
    JOB = job or {}
    if fj.get('company') and not JOB.get('company'):
        JOB = dict(JOB, company=fj['company'])                 # the receipt e-mail is matched by company
    SUBMIT = bool(a.submit and RF.approved_for(folder))
    if a.submit and not SUBMIT:
        print('NOT submitting: batch not approved (data/runner/approved_batches.json) — dry-run only')
    COVER = find_cover(folder)
    wait = a.wait_captcha if a.wait_captcha is not None else (10 if SUBMIT else 0)
    NO_ADVANCE, WAIT_CAPTCHA = a.no_advance, wait
    t0 = time.time()
    logf = open(os.path.join(out, 'run_log.md'), 'a', encoding='utf-8')
    def log(msg): logf.write(f'- {now()} {msg}\n'); logf.flush(); print(msg)
    log(f'start icims {"submit" if SUBMIT else "dry-run"} {posting} (resume {os.path.basename(resume)}'
        + (f', cover {os.path.basename(COVER)}' if COVER else '') + ')')
    RUN = R = RC.Run('icims', posting, folder, out, submit=bool(a.submit), log=log, label='iCIMS', data_dir=DATA)
    if not R.opening(resume):                                    # submit + materials problem: stopped before filling
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp(a.cdp).contexts[0]
        page = next((p for p in ctx.pages if a.attach and a.attach in p.url), None) or ctx.new_page()
        R.mark('page')
        try:
            r = run(page, posting, resume if os.path.exists(resume) else None, log, out, wait, over)
        except Exception as e:
            r = RES or {'problems': [], 'steps': [], 'unknown': []}  # keeps 'pressed' / 'maybe_in' of a hand-in already pressed
            r['status'] = 'blocked'; r['problems'].append(f'runner error {type(e).__name__}: {str(e)[:200]}')
        if r.get('pressed') and r['status'] == 'blocked' and not r.get('maybe_in'):
            r['maybe_in'] = True                                # a runner error right after the hand-in click: it may be in
        if r.get('maybe_in') and r['status'] not in ('submitted', 'unconfirmed'):
            # a hand-in-like button already moved the application on, then a later step stopped: it may be in → receipt e-mail
            r['problems'].append(f'stopped after a hand-in button was pressed ({r["status"]})')
            try:
                since = datetime.fromisoformat(r['pressed_at'])
            except (KeyError, ValueError):
                since = datetime.now(timezone.utc) - timedelta(minutes=10)
            by_email(r, since, log)
        R.report(r)                                              # dry run / stopped early: the common checks, for the record
        fields = [f for s in r['steps'] for f in s['fields']]
        n, ok = len(fields), len([f for f in fields if f.get('ok')])
        json.dump({'at': now(), 'posting': posting, 'job': a.job, 'resume': os.path.basename(resume), **r, 'readback': f'{ok}/{n}'},
                  open(os.path.join(out, 'form_check.json'), 'w'), indent=1, ensure_ascii=False)
        log(('problems: ' + ' | '.join(r['problems'] + r.get('unknown', []))) if (r['problems'] or r.get('unknown'))
            else ('CONFIRMED by ' + r.get('confirmed_by', '') if r['status'] == 'submitted' else 'all steps read back — dry-run, NOT submitted'))
        R.finish(r, ctx=ctx, page=page, confirmed_by=r.get('confirmed_by'), extra_urls=[r.get('icims_url')], keep_tab=a.keep_tab)
        if r['status'] == 'dry-run' and not a.keep_tab and not page.is_closed():
            page.close()


def find_cover(folder):
    """The application folder's cover letter: the first `*Cover_Letter*.pdf` (sorted), else None."""
    if not folder or not os.path.isdir(folder):
        return None
    hits = sorted(x for x in os.listdir(folder) if x.lower().endswith('.pdf') and 'cover_letter' in x.lower())
    return os.path.join(folder, hits[0]) if hits else None


if __name__ == '__main__':
    main()
