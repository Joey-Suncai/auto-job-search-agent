#!/usr/bin/env python3
"""Lever + Ashby runner (2026-10-30): plan.json → fill the live form in the job Chrome → read every field back →
gates → submit only inside an approved batch. Same contract as run.py (Greenhouse) and run_wd.py (Workday).

    ~/.job-agent-venv/bin/python run_form.py "<app folder>"                 # fill + check, no submit (dry-run)
    ~/.job-agent-venv/bin/python run_form.py "<app folder>" --submit       # submit when every gate passes
         [--attach <url text>]  reuse the open tab · [--wait-captcha 15] wait for Joey to solve a CAPTCHA, then submit

First the plan is rebuilt from the live posting with today's rules, profile qa and answers.json (JSA-213; --no-replan off).
Gates (all must pass): plan.ready · every planned field filled AND read back from the page · required file fields have a
file · canonical audit of the answers (canon.py) · batch approved (data/runner/approved_batches.json) · no visible CAPTCHA
challenge (Lever's hCaptcha box, Ashby's reCAPTCHA challenge frame) — a CAPTCHA is never answered by the runner: it
pushes a notification and, with --wait-captcha, waits until Joey has solved it in the tab, then submits.
Ashby after Submit (JSA-209): the page's validation errors are read first — any ("Missing entry for required field: School")
→ status failed with the field names (nothing was sent), never unconfirmed. A field only Joey can settle (no single School
option, a date answer that is not a date) → status needs-user.
Writes <folder>/run_log.md, form_check.json, filled_check.png, submitted_confirmation.png, application_record.md;
data/runner/results.jsonl + queue.md; after a confirmed submit the tracker row (scripts/store/sync_results.py).
Lever: when every check passed but nothing was confirmed (dry-run, CAPTCHA, "error verifying"), manual_submit.md for Joey
(manual_submit.py, JSA-042); he records his own submit with `sync_results.py --manual <folder>`.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
DATA = os.environ.get('CX_DATA') or jpaths.data('runner')
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import canon  # noqa: E402
import human_check  # noqa: E402  (JSA-106)

sys.path.insert(0, os.path.join(ROOT, 'config'))
import jsa_profile  # noqa: E402  (JSA-077)
TRANSCRIPT = jsa_profile.repo_path('transcript.path') or ''   # the user's official transcript (profile transcript.path)
TRANSCRIPT_NAME = jsa_profile.get('transcript.file_name') or 'Transcript.pdf'
CAPTCHA = {'lever': 'div.h-captcha iframe, iframe[src*="hcaptcha"][src*="frame=checkbox"], iframe[src*="hcaptcha"][title*="challenge" i]',
           'ashby': 'iframe[src*="recaptcha"][src*="bframe"], iframe[title*="challenge" i]'}
SOLVED = {'lever': 'textarea[name="h-captcha-response"], textarea[name="g-recaptcha-response"]',
          'ashby': 'textarea[name="g-recaptcha-response"]'}
SUBMIT = {'lever': '#btn-submit, button[type="submit"]:has-text("Submit")', 'ashby': 'button:has-text("Submit Application")'}
VERIFY_ERR = re.compile(r'error verifying your application', re.I)   # Lever: hCaptcha token rejected → form reset, re-attach + resubmit
CONFIRM = re.compile(r'application (has been |was )?(successfully )?(submitted|received)|thank(s| you) for (applying|your (application|interest)|submitting your application)|we.ve received your application', re.I)


def now():
    return datetime.now().isoformat(timespec='seconds')


def N(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def queue(folder, msg, url):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, 'queue.md'), 'a', encoding='utf-8') as q:
        q.write(f'- [ ] {now()} **{os.path.basename(folder)}** — {msg} — {url}\n')


def push(title, body):
    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts', 'daily'))
        from notify import notify
        notify(title, body)
    except Exception:
        pass


def plan_changes(old, new):
    """Pure (tested, JSA-213). Two plan.json dicts → one line per field whose planned outcome changed, in the new plan's
    field order then removed fields: '<label>: <before> → <after>', where an outcome is the answer when status is 'ok',
    else the status ('skip_optional', 'needs_user', 'file' …); a field only in the new plan has before 'new', a field only
    in the old plan has after 'gone'. Labels are cut to 60 characters, answers to 40. Fields are matched by key."""
    def out(f):
        return str(f.get('answer'))[:40] if f.get('status') == 'ok' else str(f.get('status'))
    was = {f.get('key'): f for f in (old or {}).get('fields') or []}
    now_keys, lines = set(), []
    for f in (new or {}).get('fields') or []:
        now_keys.add(f.get('key'))
        before = out(was[f.get('key')]) if f.get('key') in was else 'new'
        if before != out(f):
            lines.append(f"{N(f.get('label'))[:60]}: {before} → {out(f)}")
    for k, f in was.items():
        if k not in now_keys:
            lines.append(f"{N(f.get('label'))[:60]}: {out(f)} → gone")
    return lines


def replan(folder, plan, log):
    """JSA-213: plan.json is written at prep, but answers.json, the profile's qa table and the rules change after that
    (Dyna 11-05: an answers.json age and a qa answer never reached the form). Rebuild the plan from the live posting with
    today's rules and answers (Ashby: the saved ashby_job.json when the posting cannot be read), log what changed, save it.
    Any failure → the prep plan is kept and the run goes on with it."""
    import plan_build as PB
    ats, url = plan.get('ats'), plan.get('url')
    try:
        if ats == 'lever':
            fields = PB.lever_fields(PB.lever_fetch(*PB.lever_parse_url(url)))
        elif ats == 'ashby':
            try:
                fields = PB.ashby_fields(PB.ashby_fetch(*PB.ashby_parse_url(url)))
            except BaseException as e:
                saved = os.path.join(folder, 'ashby_job.json')
                if not os.path.exists(saved):
                    raise
                log(f'replan: live Ashby posting unreadable ({str(e)[:80]}) — using the saved ashby_job.json')
                fields = PB.ashby_fields(json.load(open(saved, encoding='utf-8')))
        else:
            return plan
        new = PB.build(folder, fields, url, ats)
    except BaseException as e:                         # SystemExit from the parsers / rules bridge included
        log(f'replan failed ({str(e)[:120]}) — the prep plan is used')
        return plan
    ch = plan_changes(plan, new)
    log(f'replan: {len(ch)} planned answer(s) changed since prep' + (': ' + ' | '.join(ch[:12]) if ch else ''))
    json.dump(new, open(os.path.join(folder, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return new


def approved_for(folder):
    p = os.path.join(DATA, 'approved_batches.json')
    try:
        return any(os.path.basename(folder) in b.get('folders', []) for b in json.load(open(p)).get('batches', []))
    except Exception:
        return False


def already_submitted(folder, results_path=None):
    """Pure-ish (tested). True when data/runner/results.jsonl has a `status: submitted` line for this folder (by the runner,
    by Joey from the Edge / a job-Chrome tab, or recorded by hand). A second submit is refused before the form is even
    opened: ShopBack 11-04 was submitted by Joey from a dry-run tab at 02:00, then the runner submitted again at 02:01 and
    Lever answered "already received" (JSA-145)."""
    name = os.path.basename(os.path.normpath(folder))
    try:
        for line in open(results_path or os.path.join(DATA, 'results.jsonl'), encoding='utf-8'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get('folder') == name and d.get('status') == 'submitted':
                return True
    except OSError:
        pass
    return False


def posting_key(url):
    """Pure (tested). The part of a form URL that names the posting, so every tab of it matches (apply / thanks /
    already-received / dry-run copies): Lever site/uuid, Ashby org/uuid, Workable account/j/SHORTCODE (JSA-146), Greenhouse token, Oracle host/job/id, iCIMS host/jobs/id (JSA-093), else the URL without query."""
    u = str(url or '')
    m = (re.search(r'jobs\.(?:eu\.)?lever\.co/([\w.-]+/[0-9a-f-]{36})', u) or re.search(r'jobs\.ashbyhq\.com/([\w.-]+/[0-9a-f-]{36})', u)
         or re.search(r'apply\.workable\.com/([\w-]+/j/[0-9A-Fa-f]{6,12})', u) or re.search(r'[?&](?:token|gh_jid)=(\d+)', u))
    if m:
        return m.group(1)
    o = re.search(r'//([\w.-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[^/]+/sites/[^/]+/(?:job|requisitions/preview)/(\d+)', u, re.I)
    if o:                                                     # Oracle: every apply section of one job (JSA-147)
        return f'{o.group(1).lower()}/job/{o.group(2)}'
    i = re.search(r'//([\w.-]+\.icims\.com)/jobs/(\d+)(?:[/?#]|$)', u, re.I)
    if i and i.group(1).lower() != 'login.icims.com':         # iCIMS: every step / login page of one job (JSA-093)
        return f'{i.group(1).lower()}/jobs/{i.group(2)}'
    return u.split('?')[0].split('#')[0]


def close_posting_tabs(ctx, url):
    """After a confirmed submit: close every other tab of the same posting (dry-run copies, a /thanks page). Joey 2026-11-04:
    「刚跑结束后不用关掉标签，是要成功提交之后关掉。」"""
    key, n = posting_key(url), 0
    for p in list(ctx.pages):
        try:
            if key and posting_key(p.url) == key:            # same posting, whatever page of it (apply / thanks / a section)
                p.close(); n += 1
        except Exception:
            pass
    return n


def pick_file(folder, f):
    """Which file a file field gets: resume · transcript (the profile's official transcript) · cover letter (only if built)."""
    lab = f['label'].lower()
    pdfs = sorted(x for x in os.listdir(folder) if x.lower().endswith('.pdf'))
    if re.search(r'resume|\bcv\b', lab) or f['key'] in ('resume', '_systemfield_resume'):
        return next((os.path.join(folder, x) for x in pdfs if 'resume' in x.lower()), None)
    if re.search(r'transcript', lab):
        dst = os.path.join(folder, TRANSCRIPT_NAME)
        if not os.path.exists(dst) and TRANSCRIPT and os.path.exists(TRANSCRIPT):
            shutil.copyfile(TRANSCRIPT, dst)
        return dst if os.path.exists(dst) else None
    if re.search(r'cover letter|letter', lab):
        return next((os.path.join(folder, x) for x in pdfs if 'cover' in x.lower()), None)
    return None


def mail_receipt(folder, since, wait, log):
    """After a submit with no thank-you page: wait up to `wait` seconds for the company's application-received e-mail
    (Gmail read-only, gmail_code.wait_for_mail). Returns its subject or None; any mail error → None (logged)."""
    if not wait:
        return None
    try:
        company = json.load(open(os.path.join(folder, 'job.json'), encoding='utf-8')).get('company')
        import gmail_code
        log(f'no thank-you page — waiting up to {wait}s for the {company} receipt e-mail (Gmail read-only)')
        return gmail_code.wait_for_mail(since - __import__('datetime').timedelta(seconds=30), company, timeout=wait)
    except BaseException as e:
        log(f'e-mail check failed: {type(e).__name__} {str(e)[:100]}')
        return None

HANDOFF_BROWSER = os.environ.get('JSA_HANDOFF_BROWSER', 'Microsoft Edge')   # Joey 2026-11-02: Lever hand-offs open in Edge
LEVER_APPLY = re.compile(r'^https://jobs\.(?:eu\.)?lever\.co/[\w.-]+/[0-9a-f-]{36}/apply/?$', re.I)


def handoff_cmd(ats, status, problems, url, browser=HANDOFF_BROWSER):
    """Pure (tested, JSA-072). Every check passed and Submit was clicked, but hCaptcha stopped it (status 'unconfirmed',
    no problems) → the command that opens the Lever apply page in Joey's own browser, which no program controls (the job
    Chrome has the debugging port, so hCaptcha rejects even his own clicks there — 2026-11-02). Otherwise None.
    The lever_fill extension in that browser fills the page; Joey only clicks Submit."""
    if ats != 'lever' or status != 'unconfirmed' or problems or not browser or not LEVER_APPLY.match(str(url or '')):
        return None
    return ['open', '-a', browser, url]


def is_phone(f):
    """A phone-NUMBER box only (same rule as verify.js isPhone): key phone, or a text/tel box whose label says "phone" as a
    word and has no options. "…via SMS … telephone calls" on a Yes/No question is not one (Xaira 2026-10-31)."""
    return f.get('key') == 'phone' or (f.get('type', 'text') in ('text', 'tel') and bool(re.search(r'\bphone\b', f.get('label') or '', re.I))
                                        and not f.get('options'))

def system_fields(plan):
    """Pure (tested, JSA-073): the Ashby system fields (key _systemfield_*: name, e-mail, phone, resume ...) the runner will
    fill — the ones it must see on the page before it fills anything (Bedrock 11-02: they rendered late on the first open)."""
    if plan.get('ats') != 'ashby':
        return []
    return [f for f in plan.get('fields', []) if str(f.get('key', '')).startswith('_systemfield_') and f.get('status') in ('ok', 'file')]


def edu_same(want, got):
    """Pure (tested). Education History read-back: `want` = the plan's JSON list of entries (the first is filled), `got`
    = the page's JSON {school, degree, major}. True when the page's school contains the wanted school (case-insensitive,
    whitespace collapsed; the page may show a longer official name) and degree / major equal the wanted ones when the
    entry has them (empty wanted parts are not checked). Unreadable JSON → False."""
    try:
        w = (json.loads(want) if isinstance(want, str) else want or [{}])[0]
        g = json.loads(got) if isinstance(got, str) else got or {}
    except (ValueError, TypeError, IndexError):
        return False
    norm_ = lambda x: re.sub(r'\s+', ' ', str(x or '')).strip().lower()
    if not norm_(w.get('school')) or norm_(w.get('school')) not in norm_(g.get('school')):
        return False
    return all(not norm_(w.get(k)) or norm_(w.get(k)) == norm_(g.get(k)) for k in ('degree', 'major'))


def date_value(want):
    """Pure (tested, JSA-208). What the runner types into an Ashby date box for the planned answer → [value, reason].
    The prep-time check (plan_build.date_answer, JSA-073) only reaches plans written after it: Creatify's plan.json was
    written 11-02 with "June 14, 2027", before that fix, and every run since typed it as is → the box showed 06/14/2027 and
    the read-back blocked. So the runner checks every date again: a full date → MM/DD/YYYY, "December 2027" kept,
    anything else → [None, reason] (the field is reported, nothing is guessed)."""
    import plan_build as PB
    v, why = PB.date_answer(want)
    return [v, None] if v is not None else [None, why or f'"{want}" is not a date']


def date_same(want, got):
    """Pure (tested). Date box read-back: the same numbers in any order (06/14/2027 = 2027-06-14 = 14/06/2027); a want with
    the month as a word and a day ("June 14, 2027") is compared as its MM/DD/YYYY form (JSA-208); "December 2027" matches
    any day of that month and year (an Ashby employer, an Ashby employer 10-31); an empty page value never matches; a want that is not
    a date matches only the same text."""
    g, w = N(got).lower(), N(want).lower()
    if not g:
        return False
    if g == w:                                                  # typed and shown as is (a Lever text date box)
        return True
    d = lambda s: [int(x) for x in re.findall(r'\d+', s)]
    mon = re.match(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{4})$', w)
    if mon and len(d(g)) == 3:
        m = 'jan feb mar apr may jun jul aug sep oct nov dec'.split().index(mon.group(1)) + 1
        y = [x for x in d(g) if x > 31]
        return len(y) == 1 and y[0] == int(mon.group(2)) and m in [x for x in d(g) if x <= 31][:2]
    try:
        full = date_value(want)[0]
    except Exception:
        full = None
    if full and re.fullmatch(r'\d{2}/\d{2}/\d{4}', full):
        w = full.lower()
    elif not re.search(r'\d', w) or re.search(r'[a-z]', w):     # not a date ("Summer 2027", "ASAP"): the same text only
        return g == w
    return d(g) == d(w) or sorted(d(g)) == sorted(d(w))


def _school_norm(s):
    s = str(s or '').lower().replace('&', ' and ')
    s = re.sub(r'[^\w\s]|_', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'^the ', '', s)


def pick_school(options, school):
    """Pure (tested, JSA-209). The Ashby education School type-ahead: which option (0-based index) is the profile's
    school, or None (→ Joey; never a guess). Compared lower-case, & = and, punctuation → spaces, a leading "the" dropped.
    An option equal to the school wins (the first when several); else the one option holding the whole name as whole
    words ("University of Chicago (Chicago, IL)"); two such options, none, or an empty school → None."""
    want = _school_norm(school)
    if not want or not options:
        return None
    norms = [_school_norm(o) for o in options]
    for i, o in enumerate(norms):
        if o == want:
            return i
    part = [i for i, o in enumerate(norms) if re.search(r'(?:^| )' + re.escape(want) + r'(?: |$)', o)]
    return part[0] if len(part) == 1 else None


ERR_HEAD = re.compile(r'your form needs corrections', re.I)
ERR_LINE = re.compile(r'required|invalid|must|please enter|please select|not valid|missing', re.I)
MISSING_FIELD = re.compile(r'missing entry for required field\s*:?\s*(.+)', re.I)


def submit_errors(text):
    """Pure (tested, JSA-209). The Ashby page text read after pressing Submit → the problems its red "Your form needs
    corrections" box lists, in order ([] = none). "Missing entry for required field: School" anywhere → "School"; after
    the heading, each following error-looking line (required / invalid / must / please enter / please select / not valid /
    missing) until the first other non-empty line; a field label ending in "*" is not an error. The heading alone →
    ["form needs corrections"]. Ramp 10-31: the box named School while the run was logged "unconfirmed"."""
    out = []
    def add(x):
        x = N(x)
        if x and x not in out:
            out.append(x)
    lines = [N(l) for l in str(text or '').split('\n')]
    head = None
    for i, l in enumerate(lines):
        if head is None and ERR_HEAD.search(l):
            head = i
            rest = ERR_HEAD.sub('', l).strip(' :-•')
            if rest and ERR_LINE.search(rest):
                m = MISSING_FIELD.search(rest); add(m.group(1) if m else rest)
            for nxt in lines[i + 1:]:
                if not nxt:
                    continue
                if nxt.endswith('*') or not ERR_LINE.search(nxt):
                    break
                m = MISSING_FIELD.search(nxt)
                add(m.group(1) if m else nxt.lstrip('•- ').strip())
    for l in lines:
        m = MISSING_FIELD.search(l)
        if m:
            add(m.group(1))
    if head is not None and not out:
        out.append('form needs corrections')
    return out


def wait_until(present, keys, timeout, step=0.5, clock=time.monotonic, sleep=time.sleep):
    """Pure loop (tested): poll present(key) for every key until all are there or `timeout` seconds pass.
    Returns the keys still missing ([] = all present). Checks once even with timeout 0."""
    end = clock() + timeout
    while True:
        missing = [k for k in keys if not present(k)]
        if not missing or clock() >= end:
            return missing
        sleep(step)


RUNNER_MARK = 'runner_active.json'   # JSA-083: lever_fill/server.py leaves a folder alone while this runner owns it


def mark_runner(folder, phase, url):
    try:
        json.dump({'at': now(), 'ts': time.time(), 'pid': os.getpid(), 'phase': phase, 'url': url},
                  open(os.path.join(folder, RUNNER_MARK), 'w'))
    except OSError:
        pass


def clear_runner(folder):
    try:
        os.remove(os.path.join(folder, RUNNER_MARK))
    except OSError:
        pass


class Form:
    def __init__(self, page, plan, folder, log):
        self.page, self.plan, self.folder, self.log = page, plan, folder, log
        self.ats = plan['ats']
        self.results = []

    # ---------- locating ----------
    def entry(self, f):
        """Ashby: the field's own container (label text); Lever: the <li> around the named input."""
        if self.ats == 'ashby':
            return self.page.locator('div[class*="_fieldEntry"], fieldset[class*="_fieldEntry"]').filter(
                has=self.page.locator('label', has_text=f['label'][:60])).first
        return self.page.locator('li.application-question, li.application-additional, div.application-question').filter(
            has=self.page.locator(f'[name="{f["key"]}"]')).first

    # ---------- filling ----------
    def fill(self, f):
        t, a, p = f['type'], f.get('answer'), self.page
        if t == 'file':
            path = pick_file(self.folder, f)
            if not path:
                return 'no file'
            inp = p.locator(f'input[type=file][name="{f["key"]}"], input[type=file][id="{f["key"]}"]').first
            if not inp.count():
                inp = self.entry(f).locator('input[type=file]').first
            inp.set_input_files(path); time.sleep(2.5)
            f['file'] = os.path.basename(path)
            return None
        if a is None:
            return None
        if self.ats == 'lever':
            return self.fill_lever(f, t, str(a))
        return self.fill_ashby(f, t, str(a))

    def fill_lever(self, f, t, a):
        p, sel = self.page, f'[name="{f["key"]}"]'
        if f.get('css'):                                   # name-less survey country select (JSA-075): pick it, the survey section opens
            p.locator(f['css']).first.select_option(label=a); time.sleep(1.2)
            return None
        if t in ('text', 'textarea', 'date'):
            p.locator(f'input{sel}, textarea{sel}').first.fill(a)
        elif t == 'combo':                                  # location: type, then take the matching suggestion
            box = p.locator(f'input{sel}').first; box.fill(''); box.type(a.split(',')[0], delay=50); time.sleep(1.8)
            opt = p.locator('.dropdown-location, .location-dropdown li, [role=option]').filter(has_text=a.split(',')[0]).first
            if opt.count():
                opt.click()
            else:
                box.fill(a)
        elif t == 'radio':
            p.locator(f'input[type=radio]{sel}[value="{a}"]').first.check()
        elif t == 'multi':
            for part in [x.strip() for x in a.split(' | ')]:
                p.locator(f'input[type=checkbox]{sel}[value="{part}"]').first.check()
        elif t == 'select':
            p.locator(f'select{sel}').first.select_option(label=a)
        elif t == 'checkbox':
            box = p.locator(f'input[type=checkbox]{sel}').first
            box.check() if a.lower() in ('yes', 'true', 'checked') else box.uncheck()
        return None

    def fill_ashby(self, f, t, a):
        e = self.entry(f)
        if not e.count():
            return 'field not on the page'
        if f.get('key') == '_systemfield_education_history' and t != 'education':   # a plan from before JSA-056 (Ramp 10-31):
            return 'needs-user: School is an Education History type-ahead but the plan has it as ' + t + ' — re-plan / re-run prep'
        if t == 'education':                               # structured Education History (JSA-056): the first entry block
            ent = (json.loads(a) or [{}])[0]
            k = f['key']
            sch = e.locator('input[placeholder*="school" i]').first
            if not sch.count():
                sch = e.locator('input[role=combobox], input').first
            sch.click(); sch.fill(''); sch.type(ent['school'][:24], delay=40); time.sleep(2)
            opts = [o for o in self.page.locator('[role=option]').all() if o.is_visible()]
            texts = [N(o.inner_text()) for o in opts]
            i = pick_school(texts, ent['school'])          # JSA-209: the one option that IS the school, else Joey — never a guess
            if i is None:
                sch.fill(''); sch.press('Escape')
                return (f'needs-user: school "{ent["school"]}" — no single matching option in the School list'
                        + (f' (shown: {" | ".join(texts[:5])})' if texts else ' (no options shown)'))
            opts[i].click(); time.sleep(0.6)
            sch.evaluate('el => el.blur()'); time.sleep(0.3)   # a type-ahead keeps only a picked option once it loses focus
            for part in ('degree', 'major'):
                if ent.get(part):
                    e.locator(f'[id="{k}-{part}"]').first.fill(ent[part])
            sels = e.locator('select').all()               # start month, start year, end month, end year
            for sel, v in zip(sels, [ent.get('start_month'), ent.get('start_year'), ent.get('end_month'), ent.get('end_year')]):
                if v:
                    try:
                        sel.select_option(label=v)
                    except Exception:
                        pass                               # an end date hidden by "current" / a year outside the list
            cur = e.locator(f'[id="{k}-isCurrent"]').first
            if cur.count() and ent.get('current') and not cur.is_checked():
                cur.check()
            return None
        if t == 'date':                                    # JSA-208: re-check the format here too — a plan written before
            v, why = date_value(a)                         # the prep-time check (Creatify 11-02) still holds "June 14, 2027"
            if v is None:
                return f'needs-user: date answer {why}'
            if v != a:
                self.log(f'  date "{a}" typed as {v} (the box takes MM/DD/YYYY)')
            box = e.locator('input:not([type=checkbox]):not([type=file])').first
            box.fill(v); box.press('Escape')
            return None
        if t in ('text', 'textarea'):
            box = e.locator('input:not([type=checkbox]):not([type=file]), textarea').first
            box.fill(a)
        elif t == 'combo':
            box = e.locator('input[role=combobox], input').first; box.click(); box.fill(''); box.type(a.split(',')[0], delay=50); time.sleep(2)
            opt = self.page.locator('[role=option]').filter(has_text=a).first
            if not opt.count():
                opt = self.page.locator('[role=option]').filter(has_text=a.split(',')[0]).first
            opt.click(); time.sleep(0.5)
        elif t == 'radio' and e.locator('input[type=radio]').count():   # radio group (Ashby, 2026-10-31): click the option's label
            e.locator('label', has_text=re.compile(rf'^\s*{re.escape(a)}\s*$')).first.click()
        elif t == 'radio':                                  # Yes / No buttons (Boolean) or radio-like option buttons
            cur = e.locator('button[aria-pressed="true"], button[class*="_active"]').first
            if cur.count() and N(cur.inner_text()).lower() == a.lower():
                return None                                 # already chosen: a second click TOGGLES it off (an Ashby employer rerun 2026-10-30)
            btn = e.locator(f'button[data-option="{a.lower()}"]').first
            if not btn.count():
                btn = e.locator('button, label', has_text=re.compile(rf'^\s*{re.escape(a)}\s*$')).first
            btn.click()
        elif t == 'multi':                                  # by the normalised name: Scientech 11-02 had name="On-Cycle Internship " (trailing space)
            boxes = e.locator('input[type=checkbox]').all()
            for part in [N(x) for x in a.split(' | ')]:
                box = next((b for b in boxes if N(b.get_attribute('name')).lower() == part.lower()), None)
                if box is None:
                    return f'no checkbox "{part}"'
                if not box.is_checked():
                    box.check()
        elif t == 'select':
            radio = e.locator('label', has_text=re.compile(rf'^\s*{re.escape(a)}\s*$')).first
            if radio.count():
                radio.click()
            else:
                box = e.locator('input').first; box.click(); box.type(a[:20], delay=40); time.sleep(1)
                self.page.locator('[role=option]').filter(has_text=a).first.click()
        return None

    # ---------- reading back ----------
    def read(self, f):
        t, p = f['type'], self.page
        if self.ats == 'lever':
            sel = f'[name="{f["key"]}"]'
            if t == 'file':
                li = self.entry(f)
                txt = N(li.inner_text()) if li.count() else ''
                return f.get('file', '') if re.search(r'success|\.pdf|uploaded|' + re.escape((f.get('file') or 'x')[:12]), txt, re.I) else ''
            if t == 'radio':
                return p.evaluate(f"() => (document.querySelector('input[type=radio]{sel}:checked')||{{}}).value || ''")
            if t == 'multi':
                return ' | '.join(p.evaluate(f"() => [...document.querySelectorAll('input[type=checkbox]{sel}:checked')].map(e => e.value)"))
            if t == 'checkbox':
                return 'Yes' if p.locator(f'input[type=checkbox]{sel}').first.is_checked() else 'No'
            if t == 'select':
                css = f.get('css') or f'select{sel}'
                return p.evaluate("css => { const s = document.querySelector(css); return s && s.selectedIndex >= 0 ? s.options[s.selectedIndex].text.trim() : ''; }", css)
            return p.locator(f'input{sel}, textarea{sel}').first.input_value()
        e = self.entry(f)
        if not e.count():
            return ''
        if t == 'education':                               # the read-back is the same JSON shape: school / degree / major
            k = f['key']
            p.evaluate('() => document.activeElement && document.activeElement.blur && document.activeElement.blur()')
            time.sleep(0.3)                                # read the committed choice, not text still being typed (Ramp 10-31)
            got = {'school': N(e.locator('input[placeholder*="school" i]').first.input_value()) or
                   N((e.locator('[class*=school], [class*=Selected], [class*=selected]').first.inner_text() if e.locator('[class*=school], [class*=Selected], [class*=selected]').count() else '')),
                   'degree': N(e.locator(f'[id="{k}-degree"]').first.input_value()) if e.locator(f'[id="{k}-degree"]').count() else '',
                   'major': N(e.locator(f'[id="{k}-major"]').first.input_value()) if e.locator(f'[id="{k}-major"]').count() else ''}
            return json.dumps(got)
        if t == 'file':
            txt = N(e.inner_text())
            return f.get('file', '') if (f.get('file') and f['file'][:15].lower() in txt.lower()) or re.search(r'\.pdf', txt, re.I) else ''
        if t in ('radio', 'select'):                  # Ashby radio groups: <input id=X> + sibling <label for=X> (an Ashby employer EEO 2026-10-31: read 'on')
            ck = e.locator('input[type=radio]:checked').first
            if ck.count():
                lb = self.page.locator(f'label[for="{ck.get_attribute("id")}"]').first
                if lb.count():
                    return N(lb.inner_text())
        if t == 'radio':
            b = e.locator('button[aria-pressed="true"], button[class*="_active"]').first
            return N(b.inner_text()) if b.count() else ''
        if t == 'multi':
            return ' | '.join(N(x.get_attribute('name')) for x in e.locator('input[type=checkbox]').all() if x.is_checked())
        if t == 'select':
            chk = [N(lb.inner_text()) for lb in e.locator('label').all() if lb.locator('input:checked').count()]
            if chk:
                return chk[0]
        box = e.locator('input:not([type=checkbox]):not([type=file]), textarea').first
        return box.input_value() if box.count() else ''

    def same(self, f, got):
        want = str(f.get('answer') if f['type'] != 'file' else f.get('file', ''))
        g, w = N(got).lower(), N(want).lower()
        if f['type'] == 'multi':
            return sorted(x.strip() for x in g.split('|')) == sorted(x.strip() for x in w.split('|'))
        if f['type'] == 'education':
            return edu_same(f.get('answer'), got)
        if f['type'] == 'combo':
            return bool(g) and (g == w or w.split(',')[0] in g)
        if f['type'] == 'date':                          # "June 14, 2027" = 06/14/2027 (JSA-208); "December 2027" = any day of it
            return date_same(want, got)
        if is_phone(f):
            return re.sub(r'\D', '', g)[-10:] == re.sub(r'\D', '', w)[-10:]
        return g == w

    def recheck(self, types):
        """Read the fields of these types again just before Submit (JSA-209: a type-ahead that drops an unpicked school
        on blur would otherwise pass on its typed text). A field that no longer reads back turns its result BAD."""
        by = {f['key']: f for f in self.plan['fields'] if f.get('type') in types and f.get('status') == 'ok'}
        for r in self.results:
            f = by.get(r['key'])
            if not f or not r['ok']:
                continue
            try:
                got = self.read(f)
            except Exception as e:
                got = ''; r['error'] = f'read failed: {type(e).__name__}'
            if not self.same(f, got):
                r.update(ok=False, page=got, error=r.get('error') or 'changed before Submit')
                self.log(f"  BAD {f['type']:8s} {f['label'][:60]} → {str(got)[:40]}  (re-read before Submit)")

    def wait_system(self, timeout=20):
        """JSA-073: Ashby renders the system fields (name, e-mail ...) late on a first open; fill only once they are all on the
        page (one reload if they never come). Returns the labels still missing."""
        sysf = system_fields(self.plan)
        if not sysf:
            return []
        by = {f['key']: f for f in sysf}
        present = lambda k: self.entry(by[k]).count() > 0
        missing = wait_until(present, list(by), timeout)
        if missing:
            self.log(f'system fields not on the page after {timeout}s ({", ".join(by[k]["label"] for k in missing)}) — reloading once')
            self.page.reload(wait_until='domcontentloaded', timeout=60000)
            missing = wait_until(present, list(by), timeout)
        if not missing:
            time.sleep(1)                                   # let the form settle: a value typed into a field still mounting is lost (an Ashby employer 11-02)
        return [by[k]['label'] for k in missing]

    def run(self):
        late = self.wait_system()
        if late:
            self.log('system fields still missing: ' + ', '.join(late))
        for f in self.plan['fields']:
            if f.get('status') not in ('ok', 'file'):
                continue
            err = None
            for attempt in (1, 2):
                try:
                    err = self.fill(f); break
                except Exception as e:
                    err = f'{type(e).__name__}: {str(e)[:100]}'; time.sleep(1)
            time.sleep(0.3)
            try:
                got = self.read(f)
            except Exception as e:
                got = ''; err = err or f'read failed: {type(e).__name__}'
            ok = (not err) and (self.same(f, got) if (f['type'] != 'file' or f.get('file')) else (not f.get('required')))
            if f['type'] == 'file' and not f.get('file') and not f.get('required'):
                ok, err = True, err or 'optional, no file'
            self.results.append({'key': f['key'], 'label': f['label'][:90], 'type': f['type'], 'required': f.get('required'),
                                 'want': f.get('answer') if f['type'] != 'file' else f.get('file'), 'page': got, 'ok': ok, 'error': err})
            self.log(f"  {'ok ' if ok else 'BAD'} {f['type']:8s} {f['label'][:60]} → {str(got)[:40]}" + (f'  ({err})' if err else ''))
        return self.results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--submit', action='store_true'); ap.add_argument('--attach')
    ap.add_argument('--wait-captcha', type=float, default=0, help='minutes to wait for Joey to solve a CAPTCHA, then submit')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222')
    ap.add_argument('--mail-wait', type=int, default=180, help='seconds to wait for the company receipt e-mail when no thank-you page shows (0 = off)')
    ap.add_argument('--no-handoff', action='store_true', help='Lever: do not open an hCaptcha-stopped page in Joey\'s Edge')
    ap.add_argument('--no-replan', action='store_true', help='use plan.json as prep wrote it (default: rebuild it from the live posting with today\'s rules, qa and answers.json — JSA-213)')
    a = ap.parse_args()
    import chrome_lock; chrome_lock.hold(f'run_form.py {os.path.basename(os.path.normpath(a.folder))}')   # JSA-236
    folder = jpaths.folder(a.folder)   # as typed, else under the data home (ADR-0008)
    if already_submitted(folder):                        # JSA-145: never a second submit, never a filled duplicate tab
        print(f'{os.path.basename(folder)}: already submitted (data/runner/results.jsonl) — nothing to do'); print('STATUS already-submitted'); return
    plan = json.load(open(os.path.join(folder, 'plan.json'), encoding='utf-8'))
    ats, url = plan['ats'], plan['url']
    t0 = time.time()
    logf = open(os.path.join(folder, 'run_log.md'), 'a', encoding='utf-8')
    def log(m): logf.write(f'- {now()} {m}\n'); logf.flush(); print(m)
    log(f'start {ats} {"submit" if a.submit else "dry-run"} {url}')
    if not a.no_replan:
        plan = replan(folder, plan, log)
    import materials_gate
    g = materials_gate.run_gate(folder, log, ats=ats)
    problems = [] if g['ok'] else ['materials gate: ' + '; '.join(g['next'] or g['problems'])[:200]]
    from playwright.sync_api import sync_playwright
    if ats == 'lever':
        mark_runner(folder, 'submit' if a.submit else 'dry-run', url)   # JSA-083: the lever_fill extension in this Chrome stands back
    import chrome_guard                                       # JSA-227: no autofill / password extension in the job Chrome
    if chrome_guard.stop(folder, url, log, queue, DATA, ats): return
    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp(a.cdp).contexts[0]
        page = next((p for p in ctx.pages if a.attach and a.attach in p.url), None)
        if page is None:
            page = ctx.new_page(); page.goto(url, wait_until='domcontentloaded', timeout=60000); time.sleep(4)
        elif VERIFY_ERR.search(page.inner_text('body')[:20000]):    # stale banner from a rejected CAPTCHA: start from a clean form
            log('stale "error verifying" banner on the attached tab — reloading the form')
            page.goto(url, wait_until='domcontentloaded', timeout=60000); time.sleep(4)
        form = Form(page, plan, folder, log)
        res = form.run()
        page.mouse.click(2, 2); time.sleep(0.5)
        if ats == 'ashby':
            form.recheck(('education',))                 # JSA-209: the School pick must still be there once focus left it
        page.screenshot(path=os.path.join(folder, 'filled_check.png'), full_page=True)
        bad = [r for r in res if not r['ok']]
        needs = [r for r in bad if str(r.get('error') or '').startswith('needs-user')]
        if needs:
            problems.append('needs Joey: ' + '; '.join(f"{r['label'][:40]} — {str(r['error'])[len('needs-user: '):][:160]}" for r in needs[:4]))
        if not plan.get('ready'):
            problems.append('plan not ready: ' + '; '.join(n['label'][:50] for n in plan.get('needs_user', [])[:4]))
        if bad:
            problems.append('fields not confirmed on the page: ' + '; '.join(f"{r['label'][:40]} ({r['page']!r})" for r in bad[:6]))
        recs = [{'label': f['label'], 'value': f['answer']} for f in plan['fields'] if f.get('status') == 'ok' and isinstance(f.get('answer'), str)]
        cbad = canon.audit(recs, canon.tenant_of(url))
        if cbad:
            problems.extend(canon.block(cbad))
        json.dump({'at': now(), 'url': url, 'fields': res, 'canon': cbad, 'problems': problems},
                  open(os.path.join(folder, 'form_check.json'), 'w'), indent=1, ensure_ascii=False)
        cap = lambda: any(l.is_visible() for l in page.locator(CAPTCHA[ats]).all())
        solved = lambda: any((x.input_value() or '').strip() for x in page.locator(SOLVED[ats]).all())
        status, confirmed_by = 'dry-run', None
        if problems:
            log('NOT submitted: ' + ' | '.join(problems)); status = 'needs-user' if needs else 'blocked' if a.submit else 'dry-run'
            if a.submit: queue(folder, 'not submitted: ' + ' | '.join(problems)[:300], url)
        elif not a.submit:
            log('all checks pass — dry-run, not submitted')
        elif not approved_for(folder):
            log('NOT submitted: batch not approved'); status = 'blocked'
        else:
            if cap() and not solved():
                log('CAPTCHA on the form → Joey (never answered by the runner)')
                queue(folder, f'CAPTCHA on the {ats} form — solve it in the job Chrome tab; the runner submits after', url)
                if a.wait_captcha > 0: human_check.push(*human_check.message(folder, [{}], parked=False))
                end = time.time() + a.wait_captcha * 60
                while time.time() < end and not solved():
                    time.sleep(3)
                if not solved():                             # JSA-106: parked for Joey, the tab kept, the batch moves on
                    status = 'captcha'; human_check.park(folder, ats, page.url, [{}], notify=a.wait_captcha <= 0)
            if status != 'captcha':
                for sel in ('button:has-text("Decline")', 'button:has-text("Reject")', 'button:has-text("Dismiss")', 'button[aria-label*="close" i]'):
                    b = page.locator(sel).first           # cookie notice over the submit button (a Lever employer): decline, never accept
                    try:
                        if b.count() and b.is_visible():
                            b.click(); time.sleep(0.5); break
                    except Exception:
                        pass
                page.locator(SUBMIT[ats]).first.scroll_into_view_if_needed()
                pre = page.url
                t_submit = datetime.now().astimezone()
                page.locator(SUBMIT[ats]).first.click(); log('submit clicked')
                ok, errs = False, []
                for _ in range(60):
                    time.sleep(0.5)
                    txt = page.inner_text('body')[:20000]
                    errs = submit_errors(txt) if ats == 'ashby' else []   # JSA-209: the page's validation errors first
                    if errs:
                        break
                    if (page.url != pre and re.search(r'/thanks|/confirmation|application-submitted', page.url)) or CONFIRM.search(txt):
                        ok = True; break
                    if cap() and not solved():
                        log('CAPTCHA challenge after submit (never answered by the runner) — the submit may still go through')
                        end = time.time() + a.wait_captcha * 60
                        while time.time() < end and not CONFIRM.search(page.inner_text('body')[:20000]):
                            if VERIFY_ERR.search(page.inner_text('body')[:20000]):
                                log('Lever rejected the CAPTCHA verification ("error verifying your application") — form reset, rerun'); break
                            time.sleep(3)
                        ok = bool(CONFIRM.search(page.inner_text('body')[:20000])); break
                if errs:                                     # Ashby refused the form: nothing was sent — failed, with the fields
                    page.screenshot(path=os.path.join(folder, 'after_submit.png'), full_page=True)
                    status = 'failed'
                    problems.append('validation errors after Submit (nothing was submitted): ' + '; '.join(errs[:8]))
                    log('NOT submitted — the form showed errors after Submit: ' + '; '.join(errs[:8]))
                    queue(folder, 'failed: the form refused Submit (nothing sent) — ' + '; '.join(errs[:6])[:240], url)
                    try:
                        fc = os.path.join(folder, 'form_check.json'); d = json.load(open(fc, encoding='utf-8'))
                        d.update(after_submit_errors=errs, problems=problems); json.dump(d, open(fc, 'w'), indent=1, ensure_ascii=False)
                    except Exception:
                        pass
                elif ok:
                    page.screenshot(path=os.path.join(folder, 'submitted_confirmation.png'), full_page=True)
                    m = CONFIRM.search(page.inner_text('body')[:20000])
                    log('CONFIRMED: ' + (m.group(0) if m else page.url)); status = 'submitted'
                    with open(os.path.join(folder, 'application_record.md'), 'a', encoding='utf-8') as rec:
                        rec.write(f"\n## Submitted by run_form.py ({ats}) {now()}\n- URL: {url}\n- Field check: {len(res)} fields read back, all ok\n"
                                  f"- Files: {', '.join(r['want'] for r in res if r['type'] == 'file' and r['want'])}\n- Confirmation: submitted_confirmation.png\n")
                else:
                    page.screenshot(path=os.path.join(folder, 'after_submit.png'), full_page=True)
                    subj = mail_receipt(folder, t_submit, a.mail_wait, log)   # Lever 10-31: 7 of 10 "unconfirmed" submits had gone through
                    if subj:
                        status, confirmed_by = 'submitted', 'email'
                        log(f'CONFIRMED by e-mail: "{subj[:90]}"')
                        with open(os.path.join(folder, 'application_record.md'), 'a', encoding='utf-8') as rec:
                            rec.write(f"\n## Submitted by run_form.py ({ats}) {now()}\n- URL: {url}\n- Field check: {len(res)} fields read back, all ok\n"
                                      f"- Confirmation: company e-mail \"{subj[:120]}\" (the page showed no thank-you; see after_submit.png)\n")
                    else:
                        status = 'unconfirmed'
                        queue(folder, 'clicked Submit but no confirmation page and no company e-mail — check Gmail, then manual submit', url)
                        push('求职 runner：没有确认', os.path.basename(folder)[11:60] + ' — 页面和邮件都没确认，交给你')
                        log('no confirmation seen (page or e-mail)')
        os.makedirs(DATA, exist_ok=True)
        with open(os.path.join(DATA, 'results.jsonl'), 'a') as out:
            out.write(json.dumps({'at': now(), 'folder': os.path.basename(folder), 'url': url, 'ats': ats, 'status': status,
                                  'problems': problems[:8], 'fields': len(res), 'bad': len([r for r in res if not r['ok']]),
                                  'secs': round(time.time() - t0, 1), 'by': 'runner', **({'confirmed_by': confirmed_by} if confirmed_by else {})}) + '\n')
        clear_runner(folder)                                 # from here a /thanks page is Joey's (Edge hand-off, a parked CAPTCHA)
        if ats == 'lever':                                   # JSA-042: clean dry-run / unconfirmed → hand-off sheet for Joey
            import manual_submit; manual_submit.write(folder, plan, res, problems, status, now()[:10], log)
            cmd = None if a.no_handoff else handoff_cmd(ats, status, problems, url)
            if cmd:                                          # JSA-072: open it in Joey's Edge; close the job-Chrome tab
                try:
                    subprocess.run(cmd, timeout=20, check=True); log(f'hand-off: opened in {cmd[2]} — Joey clicks Submit there')
                    page.close()
                except Exception as e:
                    log(f'hand-off: could not open {cmd[2]} ({type(e).__name__}) — use manual_submit.md')
        if status == 'submitted':
            sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
            import sync_results; sync_results.sync_folder(folder, log)
            try: page.close()
            except Exception: pass
            log(f'closed {close_posting_tabs(ctx, url)} other tab(s) of this posting')   # JSA-145: dry-run tabs stay until the submit (Joey 11-04)
        if status != 'captcha': human_check.resolve(folder, status)
        import tab_policy                                     # Joey 2026-11-05: dry-run / stopped tabs close too (supersedes JSA-145's 「干跑页保留到提交」); only a CAPTCHA stays
        if not tab_policy.keep_open(status, getattr(a, 'keep_tab', False)):
            try:
                if not page.is_closed(): page.close()
            except Exception: pass
        log(f'STATUS {status}'); print(f'TIME {round(time.time() - t0, 1)}s')


if __name__ == '__main__':
    main()
