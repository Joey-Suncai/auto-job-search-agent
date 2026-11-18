#!/usr/bin/env python3
"""Workable runner (JSA-122, 2026-11-03; submit path JSA-146, 2026-11-04). Reads the posting's public form schema
(`https://apply.workable.com/api/v1/jobs/<shortcode>/form`: sections → fields with fixed ids `firstname` … and the
company's own `QA_<n>` questions), answers every field with answer_rules.js (config/profile.json) through rules_bridge.js,
fills the apply page (`https://apply.workable.com/<account>/j/<shortcode>/apply/`) in the job Chrome, reads every field
back and stops before "Submit application" (dry-run).

    ~/.job-agent-venv/bin/python run_workable.py --url <posting url> [--job J01234] [--resume <pdf>] [--out <dir>] [--keep-tab]
    ~/.job-agent-venv/bin/python run_workable.py --folder applications/<folder> [--submit] [--wait-captcha 10]

--folder: an application folder (job.json with id / url, the tailored resume PDF; results and logs go there).
--submit (JSA-146, Joey 2026-11-04 「tier C投递」 / 「开始补」): only when every field read back, nothing unknown, the folder is
in data/runner/approved_batches.json and not already submitted (results.jsonl). Clicks "Submit application"; a CAPTCHA
(a Greenhouse employer Turnstile / hCaptcha) is Joey's (push, wait --wait-captcha minutes); confirmed by the thank-you page
(`confirmed_page`) or the company's receipt e-mail (gmail_code, read-only, 180 s) → status submitted, tracker row
(sync_results), every tab of the posting closed. No confirmation → unconfirmed (queue, push). Dry-run tabs stay open.
Prose boxes (JSA-151, Joey 2026-11-04 「workable 的这三个你都没有写」): the cover-letter box gets <folder>/cover.txt (optional
or not); every essay box (`essay_like`), required or optional, gets its <folder>/open_answers.md answer by field id; a fact
rule's short answer in an essay box is refused (`guard_short_answers`); after the read-back every required field
that is empty on the page is a problem (`required_empty`, 「必选题不能留空」), so --submit never presses Submit with one. Anything still undrafted → questions.json is
written and the run stops (needs-user): run scripts/ds_materials.py on the folder, then rerun — the runner never drafts.
Writes <out>/run_log.md, form_check.json, page.png; one line in data/runner/results.jsonl.
Default out (no --folder): data/runner/dryrun/workable/<account>_<shortcode>.
"""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import argparse, json, os, re, subprocess, sys, time, urllib.request
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
import jsa_profile  # noqa: E402  (JSA-403: the user's own values come from the profile)
DATA = os.environ.get('CX_DATA') or jpaths.data('runner')
RULES = os.path.join(HERE, '..', 'scripts', 'answer_rules.js')
COMPANY = ''                                                   # the hiring company (job.json / store row): referral questions check it against the referrer pool (JSA-195)
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'}
TYPES = {'text': 'text', 'email': 'text', 'phone': 'text', 'paragraph': 'textarea', 'boolean': 'radio',
         'multiple': 'radio', 'dropdown': 'select', 'date': 'date', 'numeric': 'text', 'number': 'text', 'file': 'file', 'group': 'group'}


def N(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def parse_posting(url):
    """Pure (tested). 'https://apply.workable.com/<account>/j/<SHORTCODE>/…' → {'account', 'shortcode'} or None."""
    m = re.match(r'^https?://apply\.workable\.com/([\w-]+)/j/([0-9A-Fa-f]{6,12})(?:[/?#]|$)', str(url or '').strip())
    return {'account': m.group(1), 'shortcode': m.group(2).upper()} if m else None


def plan_fields(form):
    """Pure (tested). The form schema (a list of sections {name, fields:[{id, type, required, label, choices}]}) → the
    fields to answer: [{key, label, type, required, options}] in page order. `group` fields (Education / Experience
    lists) and the photo (`avatar`) are skipped; `resume` / other files keep type 'file'; boolean → options ['Yes', 'No'];
    otherwise the option texts come from `choices` (each `body`, else `name`) or, for the company's own `CA_` fields, from
    `options` (each `value`, else `name`)."""
    out = []
    for sec in form or []:
        for f in sec.get('fields') or []:
            t = TYPES.get(f.get('type'), 'text')
            if t == 'group' or f.get('id') == 'avatar':
                continue
            opts = (['Yes', 'No'] if f.get('type') == 'boolean' else [N(c.get('body') or c.get('name')) for c in (f.get('choices') or [])]
                    or [N(c.get('value') or c.get('name')) for c in (f.get('options') or [])])
            out.append({'key': f.get('id'), 'label': N(f.get('label')), 'type': t, 'required': bool(f.get('required')), 'options': opts})
    return out


def choice_map(form):
    """Pure (tested). The form schema → {field id: {option text: option id}} for fields with choices / options: the id is
    what the page's radio carries as its value — a choice's `id` (else `name`), an option's `name` (else `value`).
    Booleans map Yes → 'true', No → 'false'. Fields without options are left out."""
    out = {}
    for sec in form or []:
        for f in sec.get('fields') or []:
            if f.get('type') == 'boolean':
                out[f.get('id')] = {'Yes': 'true', 'No': 'false'}
                continue
            m = {}
            for c in f.get('choices') or []:
                m[N(c.get('body') or c.get('name'))] = str(c.get('id') if c.get('id') is not None else c.get('name'))
            for c in f.get('options') or []:
                m[N(c.get('value') or c.get('name'))] = str(c.get('name') if c.get('name') is not None else c.get('value'))
            if m:
                out[f.get('id')] = m
    return out


def full_address(fields, ans, city_state_zip):
    """Pure (tested). Workable's single "Address" box (key `address`) with no separate city / state / zip field on the form
    gets the whole address: "<street>, <city, state zip>" (an employer 11-04 showed only the street). A form that also asks
    city / zip keeps the street; an answer that already contains the city / zip is left alone. Returns the new answers."""
    a = dict(ans.get('address') or {})
    if a.get('status') != 'ok' or not city_state_zip:
        return ans
    if any(re.search(r'\b(city|zip|postal|state)\b', f.get('label') or '', re.I) or f.get('key') in ('city', 'zip', 'state')
           for f in fields if f.get('key') != 'address'):
        return ans
    street = str(a.get('value') or '').strip()
    if not street or city_state_zip.split(',')[0].strip().lower() in street.lower():
        return ans
    return dict(ans, address=dict(a, value=f'{street}, {city_state_zip}', note='whole address in one box'))


MONTHS = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}


def parse_date(s):
    """Pure (tested). A date answer or a page value → (year, month, day) or None. Reads YYYY-MM-DD / YYYY/MM/DD /
    YYYY.MM.DD, US MM/DD/YYYY (the rules' format; also - or .), and 'June 14, 2027' / '14 June 2027'. Impossible dates → None."""
    t = N(s)
    m = re.fullmatch(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', t)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', t)
        if m:
            mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            m = re.fullmatch(r'([A-Za-z]{3,9})\.? (\d{1,2}),? (\d{4})', t) or None
            m2 = None if m else re.fullmatch(r'(\d{1,2}) ([A-Za-z]{3,9})\.?,? (\d{4})', t)
            if m:
                mo, d, y = MONTHS.get(m.group(1)[:3].lower()), int(m.group(2)), int(m.group(3))
            elif m2:
                mo, d, y = MONTHS.get(m2.group(2)[:3].lower()), int(m2.group(1)), int(m2.group(3))
            else:
                return None
    try:
        datetime(y, mo, d)
    except (TypeError, ValueError):
        return None
    return (y, mo, d)


def to_mask(value, placeholder):
    """Pure (tested). The date answer rewritten in the page box's own format, read from its placeholder (JSA-234: Syntiant's
    react-datepicker is masked 'YYYY/MM/DD'; '06/14/2027' typed there became '0614/02/27' and was cleared on blur).
    Tokens YYYY / MM / DD (any case, also M / D / YY) in the placeholder's order and separators; no usable placeholder
    → 'YYYY/MM/DD', Workable's own. Returns None when the answer is not a date."""
    ymd = parse_date(value)
    if not ymd:
        return None
    y, mo, d = ymd
    m = re.search(r'(?i)\b(y{2,4}|m{1,2}|d{1,2})([^a-z0-9]+)(y{2,4}|m{1,2}|d{1,2})\2(y{2,4}|m{1,2}|d{1,2})\b', N(placeholder))
    ph = m.group(0) if m and len({g[0].lower() for g in (m.group(1), m.group(3), m.group(4))}) == 3 else 'YYYY/MM/DD'
    tok = {'yyyy': f'{y:04d}', 'yy': f'{y % 100:02d}', 'mm': f'{mo:02d}', 'm': str(mo), 'dd': f'{d:02d}', 'd': str(d)}
    return re.sub(r'(?i)y{3,4}|y{2}|m{1,2}|d{1,2}', lambda x: tok['yyyy' if len(x.group(0)) > 2 and x.group(0)[0] in 'yY' else x.group(0).lower()], ph)


def same_date(want, got):
    """Pure (tested). True when the answer and the page value are the same calendar day (both parsed by parse_date)."""
    a, b = parse_date(want), parse_date(got)
    return bool(a) and a == b


def answer(fields, company=None):
    qs = [{'key': f['key'], 'label': f['label'], 'type': f['type'], 'options': f['options']} for f in fields if f['type'] != 'file']
    q = {'fields': qs, 'jd': '', 'company': COMPANY if company is None else company}   # company: referrer pool (JSA-195)
    r = subprocess.run(['node', os.path.join(HERE, 'rules_bridge.js'), RULES], input=json.dumps(q), capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout or '{}')


ESSAY_RE = re.compile(r'^\s*(describe|tell us|share|explain|walk us through)\b|\bwhy\b|\bhow (did|do|would) you\b.{0,80}\b(check|decide|approach|solve|fix|handle|find the|know|verify)', re.I)
SHORT = 60          # a fact rule's answer is short; a drafted essay is not


def essay_like(f):
    """Pure (tested). A free-text box that wants prose: a textarea (never the fixed `cover_letter` / `summary` boxes) whose
    label starts with Describe / Tell us / Share / Explain, asks why / how you checked …, or is longer than 100 characters."""
    return (f.get('type') == 'textarea' and f.get('key') not in ('cover_letter', 'summary')
            and (bool(ESSAY_RE.search(f.get('label') or '')) or len(f.get('label') or '') > 100))


def guard_short_answers(fields, ans):
    """Pure (tested). An essay box answered by a fact rule with a short value (BFF 11-04: "How did you find the root cause"
    got the how-heard answer "Online job board") → unknown, so it is drafted instead. Returns the new answers."""
    out = dict(ans)
    for f in fields:
        a = out.get(f['key']) or {}
        if essay_like(f) and a.get('status') == 'ok' and not a.get('leave') and len(str(a.get('value') or '')) < SHORT:   # 'leave' = deliberately empty (an optional follow-up)
            out[f['key']] = {'status': 'unknown', 'label': f['label'], 'why': f"short fact answer ({a.get('rule')}) for an essay box"}
    return out


def read_open_answers(folder):
    """Pure-ish (tested). <folder>/open_answers.md (ds_materials: blocks '## <id> — <label>' + the answer) → {id: answer};
    'ASK', empty answers and 'limit:' lines are left out."""
    p = os.path.join(folder or '', 'open_answers.md')
    if not folder or not os.path.exists(p):
        return {}
    out = {}
    for block in re.split(r'\n(?=## )', open(p, encoding='utf-8').read()):
        m = re.match(r'## (\S+) — .+?\n(.*)', block, re.S)
        if not m:
            continue
        body = '\n'.join(l for l in m.group(2).strip().splitlines() if not l.startswith('limit:')).strip()
        if body and body.upper() != 'ASK':
            out[m.group(1)] = body
    return out


def apply_drafts(fields, ans, drafts, cover):
    """Pure (tested). Fills the prose boxes: an essay box from `drafts` ({field id: answer}) and the cover-letter box
    (`cover_letter`, optional or not — Joey 2026-11-03) from `cover` (cover.txt). Returns (answers, missing) where missing
    = the questions still to draft for ds_materials ([{id, label, limit}]): every essay box without an answer, required or
    optional (Joey 2026-11-04: optional questions are answered too), plus the cover letter when there is no cover text."""
    out, missing = dict(ans), []
    for f in fields:
        a = out.get(f['key']) or {}
        if f['key'] == 'cover_letter' and f['type'] == 'textarea':
            if cover:
                out[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'cover_txt', 'value': cover}
            else:
                missing.append({'id': f['key'], 'label': f['label'], 'limit': 3000})
        elif essay_like(f) and a.get('status') != 'ok':
            if drafts.get(f['key']):
                out[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'open_answers', 'value': drafts[f['key']]}
            else:
                missing.append({'id': f['key'], 'label': f['label'], 'limit': 1200})
    return out, missing


def required_empty(rows):
    """Pure (tested). The required fields whose value read back from the page is empty (Joey 2026-11-04: 「必选题不能留空」) —
    whatever the reason (no answer, a failed fill, a cleared box) → their labels. Checked on the page, not on the answers."""
    return [r['label'] for r in rows if r.get('required') and not N(r.get('page'))]


def write_questions(folder, missing):
    """Adds the missing questions to <folder>/questions.json (kept by id) for ds_materials. A question already there gets
    the page's limit when this run read one (JSA-312: an employer's 'limit': 1500 was a guess, the page allowed 200) — matched by
    id or by label; a guess never replaces a known limit."""
    p = os.path.join(folder, 'questions.json')
    qs = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else []
    lab = lambda q: re.sub(r'[^0-9a-z]+', ' ', str(q.get('label') or '').lower()).strip()
    for m in missing:
        if m['id'] == 'cover_letter':
            continue
        old = next((q for q in qs if q.get('id') == m['id']), None) or next((q for q in qs if lab(q) and lab(q) == lab(m)), None)
        if old is None:
            qs.append(m); continue
        if m.get('limit_from') and m.get('limit_from') != 'guess':
            for k in ('limit', 'min', 'limit_from'):
                if m.get(k):
                    old[k] = m[k]
        if m.get('redraft'):
            old['redraft'] = m['redraft']
    json.dump(qs, open(p, 'w'), ensure_ascii=False, indent=1)


DONE_RE = re.compile(r"thank(s| you)( so much)? for (applying|your application)|application (was |has been )?(successfully )?"
                     r"(submitted|received|sent)|we('ve| have) received your application|your application is (in|on its way)", re.I)
# JSA-299: "thank you for your interest" is no success sentence — forms greet the candidate with it (Bosch SR 11-11).


def confirmed_page(url, text):
    """Pure (tested). True when a page SAYS the application went in: a thank-you / received sentence, or a Workable
    success URL (…/apply/success, …/confirmation). Error banners ("please fix", "required") are not success. Text only —
    after a click, decide with page_done (confirm_page.judge: the page must also have changed, JSA-299)."""
    t = N(text)
    if re.search(r'please (fix|correct|complete)|is required|there (was|were) (an )?errors?', t, re.I) and not DONE_RE.search(t):
        return False
    return bool(DONE_RE.search(t) or re.search(r'/apply/(success|thank)|/confirmation\b', str(url or ''), re.I))


def page_done(before, after):
    """Pure (tested). After the Submit click: (confirmed, why) — the page changed (URL, or the submit button gone) and
    says so (confirm_page.judge, JSA-299). `before` / `after` = {'url', 'text', 'form'}."""
    import confirm_page as CP
    return CP.judge(before, after, done_re=DONE_RE,
                    extra=lambda s: bool(re.search(r'/apply/(success|thank)|/confirmation\b', CP.url_key(s.get('url')), re.I)))


def snap(page, form_sel='[data-ui="apply-button"]'):
    """{'url', 'text', 'form'}: the page now; form = the submit button is visible."""
    try:
        form = page.locator(form_sel).first.is_visible() if page.locator(form_sel).count() else False
    except Exception:
        form = None
    try:
        text = page.inner_text('body')[:20000]
    except Exception:
        text = ''
    return {'url': page.url, 'text': text, 'form': form}


def captcha_up(page):
    for f in page.frames:
        if re.search(r'turnstile|challenges\.cloudflare|hcaptcha\.com/.*frame=challenge|recaptcha/api2/bframe', f.url or ''):
            try:
                el = f.frame_element(); box = el.bounding_box()
                if box and box['width'] > 50 and box['height'] > 50 and el.is_visible():
                    return True
            except Exception:
                pass
    return False


def submit(page, res, company, wait_captcha, log, push):
    """Click "Submit application" and confirm. Returns (status, confirmed_by)."""
    from datetime import timedelta
    import gmail_code
    import confirm_page as CP
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    before = snap(page)
    page.locator('[data-ui="apply-button"]').first.click()
    log('submit clicked')
    t_end = time.time() + 25
    why = ''
    while time.time() < t_end:
        time.sleep(2)
        ok, why = page_done(before, snap(page))
        if ok:
            log(f'confirmation page: {why}'); CP.settle(page)
            return 'submitted', 'page'
        if captcha_up(page):
            log('CAPTCHA after submit → Joey (never answered by the runner)')
            push('求职 runner：人机验证', f'{company} Workable — job Chrome 里的页面等你过验证')
            t_end = time.time() + wait_captcha * 60
    log(f'no thank-you page ({why}) — waiting up to 180 s for the receipt e-mail (Gmail read-only)')
    subj = gmail_code.wait_for_mail(since, company, timeout=180)
    if subj:
        log(f'company e-mail: {subj[:100]}'); return 'submitted', 'email'
    return 'unconfirmed', None


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def offline_plan(posting, folder=None):
    """The answers before the browser opens (JSA-235): the public form schema → fields → rule answers → drafted open
    answers / cover.txt. Returns (form, fields, cmap, ans, missing, problems); form is None when the schema is unreadable.
    batch_apply.py prepare uses it to ask Joey first without opening the job Chrome."""
    p = parse_posting(posting)
    res = {'problems': []}
    req = urllib.request.Request(f"https://apply.workable.com/api/v1/jobs/{p['shortcode']}/form", headers=UA)
    try:
        form = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:
        res['problems'].append(f'form schema not readable: {type(e).__name__} {str(e)[:120]}'); return None, [], {}, {}, [], res['problems']
    fields = plan_fields(form)
    cmap = choice_map(form)
    ans = answer(fields)
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import jsa_profile
    ans = full_address(fields, ans, (jsa_profile.get('answers.city_state_zip') or {}).get('text') if isinstance(jsa_profile.get('answers.city_state_zip'), dict) else jsa_profile.get('answers.city_state_zip'))
    ans = guard_short_answers(fields, ans)
    cover = None
    if folder and os.path.exists(os.path.join(folder, 'cover.txt')):
        cover = open(os.path.join(folder, 'cover.txt'), encoding='utf-8').read().strip() or None
    ans, missing = apply_drafts(fields, ans, read_open_answers(folder), cover)
    if missing:
        names = ' | '.join(q['label'][:70] for q in missing)
        if folder:
            write_questions(folder, missing)
            res['problems'].append(f'not drafted yet: {names} — questions.json written; run scripts/ds_materials.py on the folder, then rerun')
        else:
            res['problems'].append(f'prose boxes need an application folder (cover.txt / open_answers.md): {names}')
    numeric = {f.get('id') for sec in form for f in sec.get('fields') or [] if f.get('type') in ('number', 'numeric')}
    hourly = any((a or {}).get('rule') == 'pay_period' and re.match(r'^hour', str((a or {}).get('value')), re.I) for a in ans.values())
    for k in numeric:                                         # a digits-only pay box: 25 / hour or 52000 / year (Joey 2026-11-01)
        a = ans.get(k) or {}
        if a.get('rule') == 'comp' and not re.fullmatch(r'[\d.,]+', str(a.get('value') or '')):
            lab = next((f['label'] for f in fields if f['key'] == k), '')
            ans[k] = dict(a, value='25' if hourly or re.search(r'hour', lab, re.I) else '52000', note='digits-only pay box')
    return form, fields, cmap, ans, missing, res['problems']


def offline_unknowns(fields, ans, missing):
    """Pure (JSA-235). Questions Joey must answer before a Workable submit: every required, non-file field whose answer is
    not ok and that is not an undrafted essay (those are drafted by ds_materials from questions.json)."""
    drafted = {q['id'] for q in missing or []}
    return [{'question': f['label'], 'options': list(f.get('options') or []), 'kind': 'question'}
            for f in fields or [] if f.get('required') and f.get('type') != 'file'
            and (ans.get(f['key']) or {}).get('status') != 'ok' and f['key'] not in drafted]


def run(page, posting, resume, log, out, folder=None):
    p = parse_posting(posting)
    res = {'status': 'blocked', 'problems': [], 'fields': [], 'unknown': []}
    form, fields, cmap, ans, missing, probs = offline_plan(posting, folder)
    res['problems'] += probs
    if form is None:
        return res
    page.goto(f"https://apply.workable.com/{p['account']}/j/{p['shortcode']}/apply/", wait_until='domcontentloaded', timeout=60000)
    time.sleep(6)
    if re.search(r'no longer accepting|job (is )?(not found|closed)|page not found', page.inner_text('body'), re.I):
        res['status'] = 'closed'; return res
    dec = page.locator('[data-ui="cookie-consent-decline"]')
    if dec.count():
        dec.first.click(); time.sleep(1)
    rows = []
    for f in fields:
        row = dict(f); a = ans.get(f['key']) or {}
        try:
            if f['type'] == 'file':
                if f['key'] == 'resume' and resume:
                    page.locator('[data-ui="resume"] input[type=file], input[type=file][data-ui="resume"]').first.set_input_files(resume)
                    row['want'] = os.path.basename(resume); time.sleep(4)
                else:
                    row['want'] = None
                rows.append(row); continue
            if a.get('status') != 'ok':
                row['want'] = None; row['why'] = a.get('why'); rows.append(row)
                if f['required'] and f['key'] not in {q['id'] for q in missing}:   # an undrafted essay is already in problems
                    res['unknown'].append(f['label'] + (f" (options: {' / '.join(f['options'][:6])})" if f['options'] else ''))
                continue
            want = a.get('value'); row['want'] = want; row['rule'] = a.get('rule')
            if f['type'] == 'radio':
                v = (cmap.get(f['key']) or {}).get(N(want))
                if v is None:
                    raise ValueError(f'no option {want!r}')
                inp = page.locator(f'input[type=radio][name="{f["key"]}"][value="{v}"]').first
                wid = inp.get_attribute('id')                  # a styled option box: the click goes to its wrapper
                box = page.locator(f'[id="wrapper_{wid}"]')
                (box.first if box.count() else inp).click(); time.sleep(0.4)
                if not inp.is_checked():
                    inp.check(force=True)
            elif f['type'] in ('text', 'textarea'):
                loc = page.locator(f'[id="{f["key"]}"], input[name="{f["key"]}"]:not([type=radio]):not([aria-hidden=true]), textarea[name="{f["key"]}"]' if f['key'] != 'phone' else '#input_phone').first   # CA_ inputs carry only a name (Thorlabs 11-03)
                loc.fill(str(want))
            elif f['type'] == 'select':                       # a combobox: type, then the listbox option with that text
                cb = page.locator(f'[id="input_{f["key"]}_input"]').first
                cb.click(); time.sleep(0.5)
                if not cb.get_attribute('readonly') is not None:       # a searchable combobox takes typing; a read-only one only opens
                    cb.fill(str(want)); time.sleep(0.8)
                opt = page.locator(f'[id="input_{f["key"]}_listbox"] [role=option]').filter(has_text=re.compile('^' + re.escape(N(want)) + '$', re.I))
                (opt.first if opt.count() else page.locator('[role=option]').filter(has_text=str(want)).first).click(); time.sleep(0.4)
            elif f['type'] == 'date':                         # a masked react-datepicker text box (JSA-234): the answer in its placeholder's format
                loc = page.locator(f'input[name="{f["key"]}"]:not([type=hidden]), [id="{f["key"]}"]').first
                typed = to_mask(want, loc.get_attribute('placeholder'))
                if typed is None:
                    raise ValueError(f'not a date: {want!r}')
                row['typed'] = typed
                loc.click(); loc.fill(typed); time.sleep(0.3)
                loc.press('Escape'); loc.evaluate('e => e.blur()'); time.sleep(0.4)   # close the calendar; the picker keeps a valid date on blur, clears a bad one
            else:
                row['why'] = f'type {f["type"]} not handled yet'
        except Exception as e:
            row['error'] = f'{type(e).__name__}: {str(e)[:120]}'
        rows.append(row)
    time.sleep(1.5)
    for row in rows:                                            # read back
        k = row['key']
        if row['type'] == 'file':
            stem = os.path.splitext(row.get('want') or '')[0][:30]   # the page shows the uploaded file's name (cut short)
            shown = bool(stem) and stem.lower() in page.inner_text('body').lower()
            row['page'] = (row.get('want') if shown else '')
            row['ok'] = shown or (not row.get('want') and not row['required'])
        elif row['type'] == 'radio':
            got = page.evaluate(f"() => {{ const c = document.querySelector('input[name=\"{k}\"]:checked'); return c ? c.value : '' }}")
            back = {v: t for t, v in (cmap.get(k) or {}).items()}
            row['page'] = back.get(got, got)
            row['ok'] = (row.get('want') is None and not row['required']) or (row.get('want') is not None and bool(got) and N(row['page']).lower() == N(row['want']).lower())
        elif row['type'] == 'select':
            got = page.locator(f'[id="input_{k}_input"]').first.input_value() if page.locator(f'[id="input_{k}_input"]').count() else ''
            row['page'] = got
            row['ok'] = (row.get('want') is None and not row['required']) or (row.get('want') is not None and N(got).lower() == N(row['want']).lower())
        else:
            sel = f'[id="{k}"], input[name="{k}"]:not([type=radio]):not([aria-hidden=true]), textarea[name="{k}"]' if k != 'phone' else '#input_phone'
            got = page.locator(sel).first.input_value() if page.locator(sel).count() else ''
            row['page'] = got
            w = N(row.get('want')); g = N(got)
            row['ok'] = (w == '' and not row['required']) or (bool(g) and w.lower() == g.lower()) or (row['type'] == 'date' and same_date(w, g)) or (k == 'phone' and re.sub(r'\D', '', g)[-10:] == re.sub(r'\D', '', w)[-10:])
        if not row['ok'] and row.get('want') is not None:
            res['problems'].append(f"{row['label']}: want {row.get('want')!r}, page {row.get('page')!r}" + (f" ({row['error']})" if row.get('error') else ''))
    res['fields'] = rows
    said = ' '.join(res['problems'] + res['unknown'])
    for lab in required_empty(rows):                            # the page itself: a required box left empty never goes in
        if lab[:60] not in said:
            res['problems'].append(f'required field empty on the page: {lab}')
    try:
        page.screenshot(path=os.path.join(out, 'page.png'), full_page=True)
    except Exception:
        pass
    if [f for f in page.frames if re.search(r'turnstile|challenges\.cloudflare', f.url or '')]:
        res['problems'].append('Cloudflare Turnstile on the page — the candidate clears it before a real submit')
    res['status'] = 'dry-run' if not res['problems'] and not res['unknown'] else 'needs-user'
    log(f'all fields filled and read back — {sum(1 for r in rows if r.get("ok"))}/{len(rows)} read back')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url'); ap.add_argument('--job'); ap.add_argument('--resume'); ap.add_argument('--out')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222'); ap.add_argument('--keep-tab', action='store_true')
    ap.add_argument('--folder'); ap.add_argument('--submit', action='store_true'); ap.add_argument('--wait-captcha', type=float, default=10)
    a = ap.parse_args()
    import run_form as RF                                       # shared gates: approved_for / already_submitted / push / queue
    folder = jpaths.folder(a.folder) if a.folder else None   # as typed, else under the data home (ADR-0008)
    if folder:
        fj = json.load(open(os.path.join(folder, 'job.json')))
        a.job = a.job or fj.get('id'); a.url = a.url or fj.get('url')
        pdfs = sorted(x for x in os.listdir(folder) if x.lower().endswith('.pdf') and 'resume' in x.lower())
        a.resume = a.resume or (os.path.join(folder, pdfs[0]) if pdfs else None); a.out = folder
        global COMPANY
        COMPANY = fj.get('company') or ''                       # referral questions (JSA-195)
        if RF.already_submitted(folder):
            print(f'{os.path.basename(folder)}: already submitted — nothing to do'); print('STATUS already-submitted'); return
    if a.submit and not folder:
        sys.exit('--submit needs --folder (approval, tailored resume and the tracker row come from it)')
    job = {}
    if a.job:
        for line in open(jpaths.data('store', 'jobs.jsonl'), encoding='utf-8'):
            r = json.loads(line)
            if r.get('id') == a.job:
                job = r; break
    posting = a.url or job.get('ats_url') or job.get('url')
    p = parse_posting(posting)
    if not p:
        sys.exit(f'not a Workable posting: {posting}')
    resume = a.resume or jpaths.resume('2026-10', jsa_profile.resume_file('Data_Analyst_A-Classic.pdf'))
    out = os.path.abspath(a.out or os.path.join(DATA, 'dryrun', 'workable', f"{p['account']}_{p['shortcode']}"))
    os.makedirs(out, exist_ok=True)
    logf = open(os.path.join(out, 'run_log.md'), 'a')
    def log(m): logf.write(f'- {now()} {m}\n'); logf.flush(); print(m)
    from playwright.sync_api import sync_playwright
    t0 = time.time()
    log(f'start workable {"submit" if a.submit else "dry-run"} {posting} (resume {os.path.basename(resume)})')
    import runner_common as RC                                   # JSA-187: opening checks · submit gate · closing books
    R = RC.Run('workable', posting, folder, out, submit=a.submit, log=log, label='Workable', data_dir=DATA)
    if not R.opening(resume):                                    # submit + materials problem: stopped before filling
        return
    with sync_playwright() as pw:
        ctx = cdp_connect.connect(pw, a.cdp).contexts[0]
        page = ctx.new_page(); page.set_viewport_size({'width': 1300, 'height': 900})
        R.mark('page')
        try:
            r = run(page, posting, resume, log, out, folder)
        except Exception as e:
            r = {'status': 'blocked', 'problems': [f'runner error {type(e).__name__}: {str(e)[:200]}'], 'fields': [], 'unknown': []}
        decision = R.gate(r)
        n, ok = len(r['fields']), sum(1 for f in r['fields'] if f.get('ok'))
        json.dump({'at': now(), 'posting': posting, 'job': a.job, **r, 'readback': f'{ok}/{n}'}, open(os.path.join(out, 'form_check.json'), 'w'), indent=1, ensure_ascii=False)
        confirmed_by = None
        if decision == 'press':
            R.mark('submit')
            company = job.get('company') or json.load(open(os.path.join(folder, 'job.json'))).get('company') or p['account']
            r['status'], confirmed_by = submit(page, r, company, a.wait_captcha, log, RF.push)
            if r['status'] == 'submitted':
                log(f'CONFIRMED by {confirmed_by}')
        R.finish(r, ctx=ctx, page=page, confirmed_by=confirmed_by, keep_tab=a.keep_tab)

if __name__ == '__main__':
    main()
