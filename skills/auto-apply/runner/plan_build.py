#!/usr/bin/env python3
"""Build plan.json for one application: every question, its exact options, the answer and where the answer came from.

Usage:
  python3 plan_build.py <app_folder> --url <job or embed URL>            # Greenhouse: questions from the public API
  python3 plan_build.py <app_folder> --fields fields.json                 # any ATS: fields extracted from the live page (extract.js)
  python3 plan_build.py <app_folder> --gh-json api.json                   # offline: a saved Greenhouse API response

Answer priority (first hit wins):
  1. <app_folder>/answers.json      Joey's answers for THIS application  {"<key or label regex>": "value"}
  1b. <app_folder>/ds_answers.json  DeepSeek triage (run_wd.py): unknown question mapped to a saved fact; audit in ds_triage.json
  2. <app_folder>/open_answers.md   approved open-ended answers (ds_materials.py output), matched by question label
  3. answer_rules.js                standard answers (candidate-profile.md)
  4. otherwise -> needs_user (asked once, when he approves the batch)
A required field without an answer makes plan.ready = false; the runner never submits a plan that is not ready.
"""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import argparse, html, json, os, re, secrets, subprocess, sys, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
import canon  # noqa: E402  (same folder)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077: the profile the rules answer from)
RULES = os.environ.get('CX_RULES') or os.path.join(HERE, '..', 'scripts', 'answer_rules.js')
GH_TYPES = {'input_text': 'text', 'textarea': 'textarea', 'multi_value_single_select': 'combo',
            'multi_value_multi_select': 'multi', 'input_file': 'file', 'input_hidden': 'hidden'}
# Greenhouse API field name -> DOM id on the new job-boards UI
GH_DOM = {'location': 'candidate-location'}
# Values the page shows differently from what we choose (verify accepts any of these)
DISPLAY_ALIASES = {'country': ['United States', '+1']}


def norm(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def gh_parse_url(url):
    m = re.search(r'[?&]for=([\w-]+).*?[?&]token=(\d+)', url) or re.search(r'greenhouse\.io/([\w-]+)/jobs/(\d+)', url)
    if not m:
        m2 = re.search(r'[?&]token=(\d+).*?[?&]for=([\w-]+)', url)
        if m2:
            return m2.group(2), m2.group(1)
        raise SystemExit('not a Greenhouse URL: ' + url)
    return m.group(1), m.group(2)


def gh_fetch(board, job):
    api = f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job}?questions=true'
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
            return json.load(r)
    except Exception as e:                      # e.g. macOS Python without CA certificates → fetch through the job Chrome
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = cdp_connect.connect(pw, os.environ.get('CX_CDP', 'http://127.0.0.1:9222')); page = br.contexts[0].new_page()
            page.goto(api); txt = page.evaluate('() => document.body.innerText'); page.close()
            return json.loads(txt)


GDPR_BOXES = (   # Greenhouse GDPR boxes (data_compliance, not in "questions"; a Greenhouse employer / Veeam 2026-10-31): name, flag that adds it, required flag, label
    ('gdpr_processing_consent_given', 'requires_processing_consent', 'requires_processing_consent',
     'By checking this box, I agree to allow the company to store and process my data for the purpose of considering my eligibility regarding my current application for employment.'),
    ('gdpr_retention_consent_given', 'requires_retention_consent', 'requires_retention_consent',
     'By checking this box, I agree to allow the company to retain my data for future opportunities for employment.'),
    ('gdpr_demographic_data_consent_given', 'demographic_data_consent_applies', None,
     'By checking this box, I consent to the company collecting, storing, and processing my responses to the demographic data surveys.'))


def gdpr_fields(data):
    """Greenhouse data_compliance (type gdpr) → the consent checkboxes the page renders. Joey's rules: data processing and
    demographic consent = check; keep my data for future roles = check (talent community)."""
    out = []
    for c in data.get('data_compliance') or []:
        if c.get('type') != 'gdpr':
            continue
        for name, flag, req, label in GDPR_BOXES:
            if c.get(flag) and name not in [f['key'] for f in out]:
                out.append({'key': name, 'label': label, 'type': 'checkbox', 'required': bool(req and c.get(req)),
                            'options': [], 'sel': f'[name="{name}"]', 'consent': True})
    return out


def gh_fields(data):
    """Greenhouse API JSON -> flat field list. Phone country selector is not in the API: added as a synthetic combo."""
    out = []
    groups = list(data.get('questions') or []) + list(data.get('location_questions') or [])
    for c in data.get('compliance') or []:
        groups += c.get('questions') or []
    out += gdpr_fields(data)
    for q in groups:
        label = norm(q.get('label'))
        for f in q.get('fields') or []:
            t = GH_TYPES.get(f.get('type'), 'text')
            name = f.get('name')
            if t == 'hidden':
                out.append({'key': name, 'label': label + ' (hidden)', 'type': 'hidden', 'required': bool(q.get('required')),
                            'sel': f'[name="{name}"]'})
                continue
            if name in ('resume_text', 'cover_letter_text'):
                continue
            desc = norm(re.sub(r'<[^>]+>', ' ', html.unescape(q.get('description') or '')))   # the option list some boards put here (Allen Institute 10-31)
            fld = {'key': name, 'label': label, 'type': t, 'required': bool(q.get('required')), **({'description': desc[:1500]} if desc else {}),
                   'options': [norm(v.get('label')) for v in f.get('values') or []],
                   'sel': (f'input[type=checkbox][id^="{name}_"], input[type=checkbox][name="{name}"], [id="{name}"], [id="{name[:-2]}"]' if name.endswith('[]') else '#' + GH_DOM.get(name, name))}
            if name == 'race' and not any(x['key'] == 'hispanic_ethnicity' for x in out):
                out.append({'key': 'hispanic_ethnicity', 'label': 'Are you Hispanic/Latino?', 'type': 'combo', 'required': False,
                            'options': [], 'sel': '#hispanic_ethnicity'})
            out.append(fld)
            if name == 'phone':
                out.append({'key': 'country', 'label': 'Country', 'type': 'combo', 'required': bool(q.get('required')),
                            'options': [], 'sel': '#country'})
    # Voluntary demographic questionnaire (Gender Identity, Race/Ethnicity, Pronoun, Sexual Orientation …): a separate API block,
    # rendered as react-select comboboxes whose input id is the question id. Some boards mark them required (a Greenhouse employer 2026-10-28).
    for q in ((data.get('demographic_questions') or {}).get('questions') or []):
        multi = 'multi_select' in str(q.get('type'))
        out.append({'key': str(q['id']), 'label': norm(q.get('label')), 'type': 'multi' if multi else 'combo',
                    'required': bool(q.get('required')), 'options': [norm(o.get('label')) for o in q.get('answer_options') or []],
                    'sel': f'[id="{q["id"]}"]', 'demographic': True})
    edu = data.get('education')
    if edu in ('education_required', 'education_optional'):
        req = edu == 'education_required'
        for key, label in (('school--0', 'School'), ('degree--0', 'Degree'), ('discipline--0', 'Discipline'),
                           ('start-month--0', 'Start date month'), ('start-year--0', 'Start date year'),
                           ('end-month--0', 'End date month'), ('end-year--0', 'End date year')):
            out.append({'key': key, 'label': label, 'type': 'combo' if 'year' not in key else 'text', 'required': req,
                        'options': [], 'sel': f'[id="{key}"]', 'edu': True})
    emp = data.get('employment')                       # the newer form's Employment section (JSA-228, a Greenhouse employer 11-06)
    if emp in ('employment_required', 'employment_optional'):
        out += employment_fields(1, emp == 'employment_required')   # the page renders one block; never more than that
    return out


# Greenhouse Employment section (JSA-228): ids company-name-N, title-N, start-date-month-N (react-select), start-date-year-N,
# end-date-month-N, end-date-year-N, checkbox name current-role-N (id current-role-N_1). The current box is never required.
EMP_KINDS = (('company', 'company-name-{i}', 'Company name', 'text'), ('title', 'title-{i}', 'Title', 'text'),
             ('start_month', 'start-date-month-{i}', 'Start date month', 'combo'), ('start_year', 'start-date-year-{i}', 'Start date year', 'text'),
             ('end_month', 'end-date-month-{i}', 'End date month', 'combo'), ('end_year', 'end-date-year-{i}', 'End date year', 'text'),
             ('current', 'current-role-{i}', 'Current role', 'checkbox'))


def employment_fields(blocks, required):
    """Pure (tested). The field descriptors of `blocks` Employment blocks (0 … blocks-1), no answers: key, label, type,
    required (the current-role box never), sel, emp = block index, emp_kind."""
    out = []
    for i in range(max(0, int(blocks or 0))):
        for kind, key, label, t in EMP_KINDS:
            k = key.format(i=i)
            out.append({'key': k, 'label': label, 'type': t, 'required': bool(required) and kind != 'current', 'options': [],
                        'sel': f'[name="{k}"]' if kind == 'current' else f'[id="{k}"]', 'emp': i, 'emp_kind': kind})
    return out


def employment_entries(work):
    """Pure (tested). The profile's work list (config/wd_profile.json `work`: Company, Job Title, From / To "MM/YYYY",
    current) → [{company, title, start_month, start_year, start_num, end_month, end_year, end_num, current}], most recent
    first: current jobs first, then by From date, newest first (no From = last; ties keep the profile's order). Month =
    English name, *_num = two digits, '' when the date is missing or not MM/YYYY (or YYYY-MM). current = True only when
    `current` is true. Entries without a company are dropped."""
    def ym(v):
        s = str(v or '').strip()
        m = re.fullmatch(r'(\d{1,2})/(\d{4})', s) or re.fullmatch(r'(\d{4})-(\d{1,2})', s)
        if not m: return '', '', ''
        mo, yr = (m.group(1), m.group(2)) if '/' in s else (m.group(2), m.group(1))
        if not 1 <= int(mo) <= 12: return '', '', ''
        return EDU_MONTHS[int(mo) - 1], yr, f'{int(mo):02d}'
    out = []
    for e in work or []:
        e = e or {}
        if not str(e.get('Company') or '').strip():
            continue
        sm, sy, sn = ym(e.get('From')); em, ey, en = ym(e.get('To'))
        out.append({'company': str(e['Company']).strip(), 'title': str(e.get('Job Title') or '').strip(),
                    'start_month': sm, 'start_year': sy, 'start_num': sn, 'end_month': em, 'end_year': ey, 'end_num': en,
                    'current': e.get('current') is True})
    order = sorted(range(len(out)), key=lambda j: (not out[j]['current'], -(int(out[j]['start_year'] + out[j]['start_num']) if out[j]['start_year'] else -1), j))
    return [out[j] for j in order]


def employment_answer(f, entries):
    """Pure (tested). One Employment field (employment_fields) + employment_entries → the field with answer / status /
    source. Block N takes entry N; no entry N → nothing is invented (needs_user when required, else skip_optional). A
    current job: the box is checked and both end fields stay empty (status skip_current). A past job: the box is left
    unchecked (answer False). A month field also carries alts (3-letter name, two digits, digit) and accept, so a page
    that lists "Aug" / "08" still matches; month_num = the two digits for a month typed into a text box. An empty fact
    for a field → needs_user when required, else skip_optional."""
    f = dict(f)
    i, kind = f.get('emp', 0), f.get('emp_kind')
    e = entries[i] if 0 <= i < len(entries or []) else None
    blank = 'needs_user' if f.get('required') else 'skip_optional'
    if e is None:
        f.update(status=blank, source='profile.work:no entry'); return f
    if kind == 'current':
        f.update(answer=bool(e['current']), status='ok', source='profile.work'); return f
    if kind in ('end_month', 'end_year') and e['current']:
        f.update(status='skip_current', source='profile.work:current'); return f
    val = e.get(kind) or ''
    if not val:
        f.update(status=blank, source='profile.work:empty'); return f
    f.update(answer=val, status='ok', source='profile.work')
    if kind in ('start_month', 'end_month'):
        num = e[kind.replace('month', 'num')]
        f['alts'] = [x for x in dict.fromkeys([val[:3], num, str(int(num))]) if x != val]
        f['accept'] = list(dict.fromkeys([val] + f['alts']))
        f['month_num'] = num
    return f


def month_text_answer(name, num, input_type='text', maxlength=None, placeholder=''):
    """Pure (tested). The value to type when a month field is a plain input instead of a list: a number input → the
    digit ("8"); maxlength ≤ 2 or a placeholder like MM → two digits ("08"); otherwise the month name."""
    if str(input_type or '').lower() == 'number':
        return str(int(num))
    try: ml = int(maxlength) if maxlength not in (None, '') else None
    except (TypeError, ValueError): ml = None
    if (ml is not None and 0 < ml <= 2) or re.fullmatch(r'\s*(mm|m)\s*', str(placeholder or ''), re.I):
        return num
    return name


OPT_CAP = 200   # options listed for a needs-user / DeepSeek question: all of them (FT 10-31: only 12 kept, the right one (USD) missing)

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'}


def _get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=dict(UA, **(headers or {})))
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


# ---------- Lever (JSA-004): the apply page carries every question; custom cards hold a JSON template ----------
LEVER_TYPES = {'text': 'text', 'textarea': 'textarea', 'multiple-choice': 'radio', 'multiple-select': 'multi', 'file-upload': 'file',
               'dropdown': 'select', 'university': 'select', 'date': 'date'}
LEVER_STD = [('name', 'Full name', 'text'), ('email', 'Email', 'text'), ('phone', 'Phone', 'text'), ('org', 'Current company', 'text'),
             ('location', 'Current location', 'combo'), ('comments', 'Additional information', 'textarea')]   # urls[…]: lever_urls (JSA-144)


def lever_parse_url(url):
    import posting as PO   # the shared Lever parse (JSA-332: tolerates Xpansiv%20)
    r = PO.lever_parse(url)
    if not r:
        raise SystemExit('not a Lever URL: ' + str(url))
    return r


def lever_fetch(site, job):
    return _get(f'https://jobs.lever.co/{site}/{job}/apply')


def _select_options(page, name):
    m = re.search(r'<select[^>]*name="%s"[^>]*>(.*?)</select>' % re.escape(name), page, re.S)
    return [norm(html.unescape(re.sub(r'<[^>]+>', '', o))) for o in re.findall(r'<option[^>]*>(.*?)</option>', m.group(1), re.S)] if m else []


def lever_urls(page):
    """Pure (tested). Every URL box on a Lever page, in page order: name="urls[X]" → {key, label, type text, required, …};
    label = X, plus " URL" unless X already says url / link / website / profile. Was a fixed list of five names, which missed
    Firework's required "urls[LinkedIn Profile]" and ShopBack's "urls[Github / Portfolio]" (JSA-144, 2026-11-04)."""
    out, have = [], set()
    for tag in re.finditer(r'<input[^>]*\bname="(urls\[([^\]"]+)\])"[^>]*>', page):
        inner = norm(html.unescape(tag.group(2)))
        name = f'urls[{html.unescape(tag.group(2))}]'
        if name in have:
            continue
        have.add(name)
        out.append({'key': name, 'label': inner + ('' if re.search(r'\b(url|link|website|profile)\b', inner, re.I) else ' URL'),
                    'type': 'text', 'required': bool(re.search(r'\srequired\b', tag.group(0))), 'options': [], 'sel': f'[name="{name}"]'})
    return out


def lever_fields(page):
    """Lever apply-page HTML → flat field list (same shape as gh_fields)."""
    out = []
    for name, label, t in LEVER_STD:
        tag = re.search(r'<(?:input|textarea|select)[^>]*\bname="%s"[^>]*>' % re.escape(name), page)
        if tag:
            out.append({'key': name, 'label': label, 'type': t, 'required': 'required' in tag.group(0), 'options': [],
                        'sel': f'[name="{name}"]'})
    out += lever_urls(page)
    if re.search(r'name="resume"', page):
        out.append({'key': 'resume', 'label': 'Resume/CV', 'type': 'file', 'required': True, 'options': [], 'sel': '[name="resume"]'})
    for m in re.finditer(r'value="([^"]*)"\s+name="cards\[([^\]]+)\]\[baseTemplate\]"', page):
        card, cid = json.loads(html.unescape(m.group(1))), m.group(2)
        for i, f in enumerate(card.get('fields') or []):
            name = f'cards[{cid}][field{i}]'
            t = LEVER_TYPES.get(f.get('type'), 'text')
            opts = [norm(o.get('text')) for o in f.get('options') or []] or (_select_options(page, name) if t == 'select' else [])
            out.append({'key': name, 'label': norm(f.get('text')), 'type': t, 'required': bool(f.get('required')), 'options': opts,
                        'sel': f'[name="{name}"]' + ('' if t not in ('radio', 'multi') else f', [name="{name}"][type]')})
    for name in sorted(set(re.findall(r'<select[^>]*name="(eeo\[[a-z]+\])"', page))):   # EEO survey (US postings)
        out.append({'key': name, 'label': {'eeo[gender]': 'Gender', 'eeo[race]': 'Race', 'eeo[veteran]': 'Veteran status',
                                           'eeo[disability]': 'Disability status'}.get(name, name), 'type': 'select', 'required': False,
                    'options': [o for o in _select_options(page, name) if o and not o.lower().startswith('select')], 'sel': f'[name="{name}"]',
                    'demographic': True})
    if 'name="eeo[disabilitySignature]"' in page:     # CC-305: name + date are required once Disability status is answered (an employer 2026-10-31)
        for key, label in (('eeo[disabilitySignature]', 'Full name (self-identification form signature)'),
                           ('eeo[disabilitySignatureDate]', 'Date signed (self-identification form)')):
            out.append({'key': key, 'label': label, 'type': 'text', 'required': False, 'options': [], 'sel': f'[name="{key}"]', 'demographic': True})
    for m in re.finditer(r'<input[^>]*type="checkbox"[^>]*name="(consent\[[a-z]+\])"[^>]*>', page):
        after = norm(html.unescape(re.sub(r'<[^>]+>', ' ', re.split(r'</p>|</label>|<input', page[m.end():m.end() + 600])[0])))
        label = after[:200] or 'Consent: ' + m.group(1)[8:-1]     # the box's own sentence ("Yes, X can contact me about future job opportunities …")
        out.append({'key': m.group(1), 'label': label, 'type': 'checkbox', 'required': False, 'options': [],
                    'sel': f'[name="{m.group(1)}"]', 'consent': True})
    return out + lever_survey(page)


LEVER_LOC_KEY, LEVER_LOC_CSS = 'candidate-location', 'select.candidate-location'
SURVEY_SEC = re.compile(r'id="countrySurvey\s*([^"]*?)\s*"', re.S)


def lever_survey(page):
    """Lever's demographic survey (JSA-075, a Lever employer 2026-11-02). A "What is your location?" country <select> without a name
    (class candidate-location, option values = country codes) reveals the survey section(s) for that country: id
    countrySurvey_<code> or countrySurvey_all-candidate-locations, each with a template JSON (surveysResponses[<id>][baseTemplate])
    whose fields are named surveysResponses[<id>][responses][fieldN]. Every field gets survey: True and survey_for = '*' (all
    locations) or the country code; build() keeps only the sections the chosen country shows."""
    m = re.search(r'<select[^>]*class="candidate-location"[^>]*>(.*?)</select>', page, re.S)
    if not m:
        return []
    opts = [(v, norm(html.unescape(re.sub(r'<[^>]+>', '', t)))) for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', m.group(1), re.S)]
    opts = [(v, t) for v, t in opts if v and t]
    head = re.findall(r'<div class="application-label[^"]*">(.*?)</div>', page[max(0, m.start() - 600):m.start()], re.S)
    q = norm(html.unescape(re.sub(r'<[^>]+>', ' ', head[-1]))) if head else 'What is your location?'
    out = [{'key': LEVER_LOC_KEY, 'label': f'Country of residence ({q})', 'type': 'select', 'required': False,
            'options': [t for _, t in opts], 'option_values': {t: v for v, t in opts}, 'sel': LEVER_LOC_CSS, 'css': LEVER_LOC_CSS,
            'demographic': True, 'survey': True}]
    secs = list(SURVEY_SEC.finditer(page))
    for i, s in enumerate(secs):
        code = re.sub(r'\s+', '', s.group(1)).lstrip('_')
        block = page[s.end(): secs[i + 1].start() if i + 1 < len(secs) else len(page)]
        for t in re.finditer(r'value="([^"]*)"[^>]*?name="(surveysResponses\[[^\]]+\])\[baseTemplate\]"', block):
            try:
                card = json.loads(html.unescape(t.group(1)))
            except ValueError:
                continue
            for j, f in enumerate(card.get('fields') or []):
                name = f'{t.group(2)}[responses][field{j}]'
                ft = LEVER_TYPES.get(f.get('type'), 'text')
                out.append({'key': name, 'label': norm(f.get('text')), 'type': ft, 'required': bool(f.get('required')),
                            'options': [norm(o.get('text')) for o in f.get('options') or []], 'sel': f'[name="{name}"]',
                            'demographic': True, 'survey': True, 'survey_for': '*' if code.startswith('all') else code})
    return out


# ---------- Ashby (JSA-004): the public non-user GraphQL returns the application form and the EEO survey ----------
ASHBY_TYPES = {'String': 'text', 'Email': 'text', 'Phone': 'text', 'Number': 'text', 'SocialLink': 'text', 'File': 'file',
               'LongText': 'textarea', 'Boolean': 'radio', 'ValueSelect': 'select', 'MultiValueSelect': 'multi',
               'Location': 'combo', 'Date': 'date', 'EducationHistory': 'education'}
ASHBY_Q = ('query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) { jobPosting('
           'organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) { id title '
           'applicationForm { sections { title fieldEntries { ... on FormFieldEntry { id field isRequired descriptionHtml } } } } '
           'surveyForms { sections { title fieldEntries { ... on FormFieldEntry { id field isRequired descriptionHtml } } } } } }')


EDU_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def education_entries(education):
    """Pure (tested). The profile's `education` list (newest first) → the entries for a structured Education History
    field: [{school, degree, major, start_month, start_year, end_month, end_year, current}] in the same order. degree =
    `degree_full` (else `degree`); major = `major` (else ''); a "YYYY-MM" `start` / `end` → the English month name and
    the year as strings ('' when missing or not YYYY-MM); current = True only when `current` is true. Entries without a
    school are dropped."""
    out = []
    for e in education or []:
        if not (e or {}).get('school'):
            continue
        def ym(v):
            m = re.fullmatch(r'(\d{4})-(\d{2})', str(v or ''))
            return (EDU_MONTHS[int(m.group(2)) - 1], m.group(1)) if m and 1 <= int(m.group(2)) <= 12 else ('', '')
        sm, sy = ym(e.get('start')); em, ey = ym(e.get('end'))
        out.append({'school': e['school'], 'degree': e.get('degree_full') or e.get('degree') or '', 'major': e.get('major') or '',
                    'start_month': sm, 'start_year': sy, 'end_month': em, 'end_year': ey, 'current': e.get('current') is True})
    return out


def ashby_parse_url(url):
    m = re.search(r'jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})', url or '')
    if not m:
        raise SystemExit('not an Ashby URL: ' + str(url))
    return m.group(1), m.group(2)


def ashby_fetch(org, job):
    body = json.dumps({'operationName': 'ApiJobPosting', 'query': ASHBY_Q,
                       'variables': {'organizationHostedJobsPageName': org, 'jobPostingId': job}}).encode()
    d = json.loads(_get('https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting', body, {'content-type': 'application/json'}))
    if d.get('errors') or not (d.get('data') or {}).get('jobPosting'):
        raise SystemExit('Ashby posting not found / API error: ' + json.dumps(d.get('errors') or 'no jobPosting')[:200])
    return d['data']['jobPosting']


def ashby_description(org, job):
    """The posting's description HTML from the public posting API (job board list)."""
    d = json.loads(_get(f'https://api.ashbyhq.com/posting-api/job-board/{org}'))
    j = next((x for x in d.get('jobs', []) if job in (x.get('jobUrl') or '') or x.get('id') == job), None)
    return (j or {}).get('descriptionHtml') or (j or {}).get('descriptionPlain') or ''


NUMERIC = re.compile(r'^\s*-?\d+(\.\d+)?\s*$')


def numeric_answer(label, src, ans):
    """JSA-268 (an Ashby employer Ashby 11-10): a Number box got the text answer "Open / per internship program standard" — the page
    keeps it empty and the read-back stops the submit. A pay answer (rules:comp) becomes the profile's digits
    (answers.comp.digits: annual / yearly / salary → year, otherwise hour — an internship pays by the hour, Joey
    2026-11-01); any other text answer → (None, why), so Joey is asked instead of a guess."""
    if src == 'rules:comp':
        d = ((jsa_profile.load().get('answers') or {}).get('comp') or {}).get('digits') or {}
        v = d.get('year') if re.search(r'\b(annual|yearly|per year|a year|annum|salary)\b', label, re.I) else d.get('hour')
        if v is not None and NUMERIC.match(str(v)):
            return str(v), 'rules:comp (digits)'
        return None, 'number box: no answers.comp.digits on file'
    return None, f'number box: the answer {str(ans)[:40]!r} ({src}) is not a number'


def html_text(h):
    """Pure (tested, JSA-419). Description HTML → plain text, whitespace folded ('' for none)."""
    t = re.sub(r'<(br|/p|/li|/div)\s*/?>', ' ', str(h or ''), flags=re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', t))).strip()


def ashby_fields(posting):
    out = []
    def add(entry, demographic=False):
        f = entry.get('field') or {}
        t = ASHBY_TYPES.get(f.get('type'), 'text')
        opts = ['Yes', 'No'] if t == 'radio' else [norm(v.get('label')) for v in f.get('selectableValues') or []]
        path = f.get('path') or entry.get('id')
        help_ = html_text(entry.get('descriptionHtml'))      # JSA-419: the text under the question ("If no, is your home country listed below?" → the country list)
        out.append({'key': path, 'label': norm(f.get('title')), 'type': t, 'required': bool(entry.get('isRequired')),
                    'options': opts, 'sel': f'[name="{path}"], [id="{path}"]', **({'demographic': True} if demographic else {}),
                    **({'help': help_} if help_ else {}),
                    **({'numeric': True} if f.get('type') == 'Number' else {}),
                    **({'edu_excluded': [k for k in ('degree', 'major', 'startDate', 'endDate') if f.get(k) == 'excluded']}
                       if f.get('type') == 'EducationHistory' else {})})   # sub-fields the form leaves out (JSA-330)   # an <input type=number> takes digits only (JSA-268)
    for sec in ((posting.get('applicationForm') or {}).get('sections') or []):
        for e in sec.get('fieldEntries') or []:
            add(e)
    for form in posting.get('surveyForms') or []:
        for sec in form.get('sections') or []:
            for e in sec.get('fieldEntries') or []:
                add(e, demographic=True)
    return out


def label_match(pattern, label):
    """answers.json key used as a label regex; a key that is not a valid regex (Lever "cards[uuid][field3]", a Lever employer
    2026-10-31) never matches a label — it can still match its field key exactly."""
    try:
        return re.search(pattern, label or '', re.I) is not None
    except re.error:
        return False


def override_for(f, overrides, field_keys):
    """Pure (tested): the answers.json entry for field f → (value,) or None. A key equal to f's key wins; otherwise the
    first key (file order) that is not any field's key, does not start with "question_", and matches f's label as a
    case-insensitive regex (an invalid regex never matches)."""
    if f['key'] in overrides:
        return (overrides[f['key']],)
    for k, v in overrides.items():
        if k not in field_keys and not k.startswith('question_') and label_match(k, f['label']):
            return (v,)
    return None


MONTHS = 'january february march april may june july august september october november december'.split()


def _mon(s):
    """'June' / 'jun' / 'Sept.' → 6 / 6 / 9; any other word → None."""
    s = s.lower().rstrip('.,')
    for i, full in enumerate(MONTHS):
        if s == full or s == full[:3] or (full == 'september' and s == 'sept'):
            return i + 1
    return None


def date_answer(v):
    """Pure (tested, JSA-073): an answers.json value for a date box → (value, None) or (None, why). Date boxes take
    MM/DD/YYYY (react-datepicker reads back 06/14/2027, so "June 14, 2027" never matched — an Ashby employer 11-02). A full date in
    another unambiguous form (M/D/YYYY, YYYY-MM-DD, "June 14, 2027", "14 June 2027") is rewritten; month + year ("December
    2027") is kept (the box shows the 1st, run_form.same accepts it); anything else — a season, DD/MM/YYYY, a date that does not
    exist — is refused with the reason."""
    s = norm(v)
    y = mo = d = None
    m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if mo > 12:
            return None, f'"{s}" looks like DD/MM/YYYY — a date box takes MM/DD/YYYY'
    elif re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', s):
        y, mo, d = map(int, s.split('-'))
    elif re.fullmatch(r'([A-Za-z]{3,9}\.?) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})', s):
        m = re.fullmatch(r'([A-Za-z]{3,9}\.?) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})', s); mo, d, y = _mon(m.group(1)), int(m.group(2)), int(m.group(3))
    elif re.fullmatch(r'(\d{1,2})(?:st|nd|rd|th)? ([A-Za-z]{3,9}\.?),? (\d{4})', s):
        m = re.fullmatch(r'(\d{1,2})(?:st|nd|rd|th)? ([A-Za-z]{3,9}\.?),? (\d{4})', s); d, mo, y = int(m.group(1)), _mon(m.group(2)), int(m.group(3))
    elif re.fullmatch(r'([A-Za-z]{3,9}\.?),? (\d{4})', s) and _mon(s.split()[0].rstrip(',')):
        return s, None
    else:
        return None, f'"{s}" is not a date — a date box takes MM/DD/YYYY'
    try:
        datetime(y, mo, d)
    except (TypeError, ValueError):
        return None, f'"{s}" is not a real date — a date box takes MM/DD/YYYY'
    return f'{mo:02d}/{d:02d}/{y}', None


def multi_answer(v, options):
    """Pure (tested, JSA-073): an answers.json value for a multi-select → ('A | B', None) or (None, why). A list, or one
    string with ' | ' between parts; every part must be an exact option (spaces normalised). A string that is not an option
    but whose comma-separated parts all are is read as that list. Anything else is refused, naming the parts that miss."""
    opts = {norm(o): norm(o) for o in options or []}
    if isinstance(v, (list, tuple)):
        parts = [norm(x) for x in v]
    else:
        s = norm(v)
        parts = [norm(x) for x in s.split('|')] if '|' in s else [s]
        if not all(p in opts for p in parts) and ',' in s and all(norm(x) in opts for x in s.split(',')):
            parts = [norm(x) for x in s.split(',')]
    parts = [p for p in parts if p]
    if not parts:
        return None, 'empty multi-select answer'
    if options:
        miss = [p for p in parts if p not in opts]
        if miss:
            return None, 'not an exact option: ' + ', '.join(f'"{p}"' for p in miss) + ' — give a list of option texts'
    return ' | '.join(dict.fromkeys(parts)), None


# rules whose answer is built from the profile's facts: they win over an open_answers.md draft for the same box (JSA-218,
# HRT 11-05: DeepSeek's education paragraph said "B.S." / "M.S. Data Science" / high school "not provided")
FACT_FIRST = {'education_list', 'visa_expiry', 'ft_start', 'name_pronunciation'}
DEGREE_EQUIV = {'master': ["Master's Degree", "Master's", 'Masters', 'Master', 'Master of Science', 'MS', 'M.S.'],
                'bachelor': ["Bachelor's Degree", "Bachelor's", 'Bachelors', 'Bachelor', 'Bachelor of Arts', 'BA', 'B.A.']}


def degree_equiv(ans):
    """Spellings of the same degree level a Greenhouse Degree combo may show (JSA-219): "Master's Degree" = "Masters"."""
    a = canon.norm(ans)
    if re.match(r"^(master'?s?( degree)?|master of science|m\.?s\.?)$", a): return DEGREE_EQUIV['master']
    if re.match(r"^(bachelor'?s?( degree)?|bachelor of arts|b\.?a\.?)$", a): return DEGREE_EQUIV['bachelor']
    return []


def load_open_answers(folder):
    """<folder>/open_answers.md (ds_materials): blocks '## <field id> — <label>' + the answer → [(label, answer)]; 'ASK' and
    empty answers skipped. The id is any run of non-space characters (Greenhouse question_123, Lever cards[uuid][field0])."""
    p = os.path.join(folder, 'open_answers.md')
    if not os.path.exists(p):
        return []
    txt = open(p, encoding='utf-8').read()
    res = []
    for block in re.split(r'\n(?=## )', txt):
        m = re.match(r'## \S+ — (.+?)\n(.*)', block, re.S)          # any id without spaces: Lever's cards[uuid][fieldN] too (JSA-150)
        if not m:
            continue
        body = '\n'.join(l for l in m.group(2).strip().splitlines() if not l.startswith('limit:')).strip()
        if not body or body.upper() == 'ASK':      # ds_materials' "cannot answer from the facts" marker → the field stays needs_user (2026-10-31)
            continue
        res.append((norm(m.group(1)), body))
    return res


def load_jd(folder):
    """<folder>/jd.md (prep_batch / prep_wd) — the rules that answer from the JD's requirement read it (JSA-105); '' when absent."""
    try: return open(os.path.join(folder, 'jd.md'), encoding='utf-8').read()
    except OSError: return ''


def load_cover(folder):
    """<folder>/cover.txt (the job's cover letter, JSA-286: the optional "message to the hiring manager" box); '' when absent."""
    try: return open(os.path.join(folder, 'cover.txt'), encoding='utf-8').read()
    except OSError: return ''


def load_company(folder):
    """The hiring company of an application folder (JSA-195): job.json (or Workday's wd_job.json) → company, else the
    jd.md title line '# <title> — <Company>'; '' when none says (the referral rules then ask the user)."""
    for name in ('job.json', 'wd_job.json'):
        try:
            c = (json.load(open(os.path.join(folder, name), encoding='utf-8')) or {}).get('company')
            if c:
                return str(c).strip()
        except (OSError, ValueError, AttributeError):
            pass
    try:
        first = open(os.path.join(folder, 'jd.md'), encoding='utf-8').readline()
    except OSError:
        return ''
    m = re.match(r'#\s.*\s[\u2014\u2013]\s+(.+?)\s*$', first)          # prep_batch / prep_wd write '# <title> — <company>'
    return m.group(1).strip() if m else ''


def run_rules(fields, jd='', company='', cover=''):
    q = [{'key': f['key'], 'label': f['label'], 'type': f['type'], 'options': f.get('options', [])}
         for f in fields if f['type'] not in ('file', 'hidden')]
    q = {'fields': q, 'jd': jd, 'company': company or '', 'cover': cover or ''}   # company: referral questions vs the referrer pool (JSA-195); cover: JSA-286
    import shutil
    if shutil.which('node'):
        r = subprocess.run(['node', os.path.join(HERE, 'rules_bridge.js'), RULES], input=json.dumps(q),
                           capture_output=True, text=True, timeout=30)
        if r.returncode:
            raise SystemExit('rules_bridge failed: ' + r.stderr[-500:])
        return json.loads(r.stdout)
    # no Node on this Mac: run the same two files inside a browser page via Playwright
    from playwright.sync_api import sync_playwright
    js = ('([prof, pool, applied, rules, bridge, q]) => { globalThis.__cxProfile = prof; globalThis.__cxPool = pool; globalThis.__cxApplied = applied; const m1 = {exports: {}}, m2 = {exports: {}}; '
          '(new Function("module", rules))(m1); (new Function("module", "require", bridge))(m2, undefined); '
          'return m2.exports.answerAll(m1.exports.answerFor, q.fields, {jd: q.jd, company: q.company, cover: q.cover}); }')
    with sync_playwright() as pw:
        try:
            br = cdp_connect.connect(pw, os.environ.get('CX_CDP', 'http://127.0.0.1:9222')); page = br.contexts[0].new_page()
        except Exception:
            br = pw.chromium.launch(); page = br.new_page()
        out = page.evaluate(js, [jsa_profile.load(), jsa_profile.pool(), jsa_profile.applied(), open(RULES).read(), open(os.path.join(HERE, 'rules_bridge.js')).read(), q]); page.close()
        return out


def work_profile():
    """The work entries from the data home's config/wd_profile.json (the example twin when there is none; JSA_WD_PROFILE)."""
    return json.load(open(jsa_profile.data_file('wd_profile.json', 'JSA_WD_PROFILE'), encoding='utf-8')).get('work') or []


OTHER_WRITERS = re.compile(r'^(answers\.json|ds_answers\.json|canon:)')


def whole_read_plan(plan_fields, needs):
    """JSA-288b (Joey 2026-11-10 「扩」): the critical answers the folder's answers.json, the DeepSeek triage
    (ds_answers.json) or canon's option pick wrote get the same whole-question read as the rules' answers (those are read in
    rules_bridge.js) — a different answer, UNSURE or an error → needs_user, the runner asks Joey. Live runs only
    (whole_read.enabled); in place."""
    import whole_read as W
    if not W.enabled():
        return
    labels = [f.get('label') or '' for f in plan_fields]
    items = [{'key': f['key'], 'label': f.get('label') or '', 'options': f.get('options') or [], 'type': f.get('type'), 'value': f.get('answer'),
              'rule': f.get('source'), 'pos': i, 'context': labels[max(0, i - 4):i]}
             for i, f in enumerate(plan_fields) if f.get('status') == 'ok' and OTHER_WRITERS.match(str(f.get('source') or ''))]
    if not items:
        return
    rev = W.review(items)
    for f in plan_fields:
        v = rev.get(f['key'])
        if not v or v['agree']:
            continue
        why = f"whole read: {f.get('source')} said {f.get('answer')!r}, the model " + (f"said {v['model']!r}" if v.get('model') else 'gave no answer') + (f" — {v['why'][:160]}" if v.get('why') else '')
        needs.append({'key': f['key'], 'label': f.get('label') or '', 'why': why, 'options': (f.get('options') or [])[:OPT_CAP], 'required': True, 'no_triage': True})
        f.update(status='needs_user', rejected=f.get('answer'), whole_read=v.get('how'))
        f.pop('answer', None)


def ds_cache_may_answer(rule, ds_value):
    """JSA-337: may a cached DeepSeek answer (ds_answers.json) fill this field? Never when the rules (incl. Joey's qa table) have
    an answer, when the question is Joey's (ask / no_auto) or a consent box — the cache only fills what the rules cannot answer."""
    rule = rule or {}
    if ds_value is None or ds_value == '': return False
    if rule.get('no_auto') or rule.get('ask') or rule.get('status') == 'consent' or rule.get('rule') == 'hiring_manager_note': return False   # JSA-286: no cover letter = empty box, never an old cached text
    if rule.get('status') == 'ok' and not rule.get('leave'): return False
    return True


def build(folder, fields, url, ats):
    overrides = {}
    op = os.path.join(folder, 'answers.json')
    if os.path.exists(op):
        overrides = json.load(open(op, encoding='utf-8'))
    dsp = os.path.join(folder, 'ds_answers.json')      # DeepSeek triage: mapped to a SAVED fact (run_wd.py, 2026-10-28b); Joey's answers.json wins
    ds_over = json.load(open(dsp, encoding='utf-8')) if os.path.exists(dsp) else {}
    opens = load_open_answers(folder)
    rules = run_rules(fields, load_jd(folder), load_company(folder), load_cover(folder))
    tenant = canon.tenant_of(url)
    plan_fields, needs = [], []
    field_keys = {x["key"] for x in fields}             # an answers.json key equal to a field key matches that field only
    country = None                                      # Lever survey: the country code picked in "What is your location?"
    for f in fields:
        f = dict(f)
        if f.get('survey_for') and (not country or f['survey_for'].upper() not in ('*', country)):
            continue                                    # this survey section stays hidden for the chosen country (or none chosen)
        if f['type'] == 'file':
            f.update(status='file', source='runner')       # resume upload handled by the runner from the app folder
            plan_fields.append(f); continue
        if f['type'] == 'hidden':
            f.update(status='check_only', source='page')   # e.g. latitude/longitude set by the location picker
            plan_fields.append(f); continue
        if f['type'] == 'education':                       # Ashby Education History (JSA-056): the profile's newest school
            ents = education_entries(jsa_profile.get('education'))
            if ents:
                f.update(answer=json.dumps(ents[:1]), status='ok', source='profile.education')
            else:
                f.update(status='needs_user' if f['required'] else 'skip_optional', source='profile.education:empty')
            plan_fields.append(f); continue
        if f.get('emp') is not None:                       # Greenhouse Employment block (JSA-228): the profile's work, newest first
            g = employment_answer(f, employment_entries(work_profile()))
            if g['status'] == 'needs_user':
                needs.append({'key': g['key'], 'label': g['label'], 'why': g['source'], 'options': [], 'required': True, 'no_triage': True})
            plan_fields.append(g); continue
        ans, src = None, None
        hit = override_for(f, overrides, field_keys)
        if hit:
            ans, src = hit[0], 'answers.json'
        if src is None:
            for k, v in ds_over.items():
                try: hit = k == f['key'] or re.search(k, f['label'], re.I)
                except re.error: hit = k == f['label']
                if hit and v is not None: ans, src = v, 'ds_answers.json'; break
            if src == 'ds_answers.json' and not ds_cache_may_answer(rules.get(f['key']), ans):
                ans, src = None, None                    # the rules / qa answer it (JSA-337) or Joey does (no_auto, JSA-361): an old DeepSeek mapping never fills it
        if src in ('answers.json', 'ds_answers.json') and ans is not None and f['type'] in ('date', 'multi'):
            ans, why = date_answer(ans) if f['type'] == 'date' else multi_answer(ans, f.get('options'))   # JSA-073: format checked at prep
            if why:
                needs.append({'key': f['key'], 'label': f['label'], 'why': f'{src}: {why}', 'options': f.get('options', [])[:OPT_CAP], 'required': f['required']})
                f.update(status='needs_user' if f['required'] else 'skip_optional', source=src + ':bad_format')
                plan_fields.append(f); continue
        if src == 'answers.json' and ans is None:              # Joey: leave this one blank
            f.update(status='needs_user' if f['required'] else 'skip_optional', source='answers.json:blank')
            if f['required']: needs.append({'key': f['key'], 'label': f['label'], 'why': 'answers.json says blank but it is required', 'options': f.get('options', [])[:OPT_CAP], 'required': True})
            plan_fields.append(f); continue
        ra = rules.get(f['key']) or {}
        if ans is None and ra.get('status') == 'ok' and ra.get('rule') in FACT_FIRST:   # facts beat a DeepSeek draft (JSA-218)
            ans, src = ra.get('value'), 'rules:' + ra['rule']
        if ans is None and f['type'] in ('textarea', 'text'):
            for lab, body in opens:
                if lab[:60].lower() == f['label'][:60].lower():
                    ans, src = body, 'open_answers.md'; break
        if ans is None:
            a = rules.get(f['key']) or {}
            if a.get('status') == 'ok' and not a.get('leave'):
                ans, src = a.get('value'), 'rules:' + a.get('rule', '')
                if a.get('alts') and not f.get('options'): f['alts'] = a['alts']
            elif a.get('status') == 'consent':
                src = 'consent'
            elif a.get('ask'):                                # the rule knows the question but the answer is Joey's (JSA-105: the JD asks for years)
                src, f['no_triage'] = 'ask: ' + a.get('why', a.get('rule', '')), True
                if a.get('no_auto'): f['no_auto'] = True     # nothing may fill it — canon, a page prefill (run_wd) — Joey answers (JSA-361)
        # canonical fields (sponsorship, authorization, degree, veteran, EEO, source …): the answer must pass canon for this
        # tenant; when the rule text picked a wrong or missing option, take the canon-valid option from the list (JSA-005)
        ckey = canon.classify(f['label']) if f.get('type') not in ('text', 'textarea', 'date') else None
        if ckey and f.get('options') and src != 'answers.json' and f.get('type') != 'multi' and not ra.get('no_auto'):   # no_auto: the rules hand it to Joey and nothing may fill it (JSA-361, Joey 2026-11-16)
            if ans is None or not canon.judge(ckey, f['label'], ans, tenant)[0] or ans not in f['options']:
                cp = canon.pick_for(ckey, f['label'], f['options'], tenant)   # the label's inversion applied (JSA-267)
                if cp is not None:
                    if ans is not None and cp != ans:
                        f['canon_fixed'] = f'{ans!r} → {cp!r}'
                    ans, src = cp, 'canon:' + ckey
        if f.get('numeric') and ans is not None and not NUMERIC.match(str(ans)):
            ans, src = numeric_answer(f['label'], src, ans)
        if isinstance(ans, list):                 # multi-select given as a list → the runner's 'A | B' form
            ans = ' | '.join(str(x) for x in ans)
        if ans is not None and f.get('options'):
            parts = [x.strip() for x in str(ans).split(' | ')] if f.get('type') == 'multi' else [ans]
            if not all(x in f['options'] for x in parts):   # exact option text only — never a near miss (each part of a multi)
                needs.append({'key': f['key'], 'label': f['label'], 'why': f'answer "{ans}" ({src}) is not an exact option',
                              'options': f['options'][:OPT_CAP], 'required': f['required']})
                ans, src = None, None
        if ans is None:
            if f['required'] or src == 'consent':
                needs.append({'key': f['key'], 'label': f['label'], 'why': src or 'no rule',
                              'options': f.get('options', [])[:OPT_CAP], 'required': f['required'], **({'no_triage': True} if f.get('no_triage') else {})})
            elif f.get('survey'):                         # JSA-075: an optional survey question with no fact → left blank, listed for Joey
                needs.append({'key': f['key'], 'label': f['label'], 'why': 'Lever survey: no fact in the profile — left blank; Joey may answer',
                              'options': f.get('options', [])[:OPT_CAP], 'required': False, 'survey': True, 'no_triage': True})
            f.update(status='needs_user' if f['required'] else 'skip_optional', source=src)
        else:
            f.update(answer=ans, status='ok', source=src)
            if f.get('alts'): f['accept'] = list(dict.fromkeys([ans] + f['alts']))
            if not f.get('options') and f.get('type') in ('combo', 'select') and canon.classify(f['label']) == 'degree_level':
                eq = degree_equiv(ans)                   # the page may spell the same level "Masters" (Epic 11-05, JSA-219)
                if eq: f['accept'] = list(dict.fromkeys(f.get('accept', [ans]) + eq))
            if f['key'] in DISPLAY_ALIASES:
                f['accept'] = DISPLAY_ALIASES[f['key']]
        if f['key'] == LEVER_LOC_KEY and f.get('status') == 'ok':
            country = str((f.get('option_values') or {}).get(f['answer']) or '').upper() or None
        plan_fields.append(f)
    whole_read_plan(plan_fields, needs)
    # de-duplicate needs (same key)
    seen, uniq = set(), []
    for n in needs:
        if n['key'] not in seen:
            seen.add(n['key']); uniq.append(n)
    return {'version': 1, 'nonce': secrets.token_hex(8), 'created': datetime.now().isoformat(timespec='seconds'),
            'folder': os.path.basename(os.path.abspath(folder)), 'url': url, 'ats': ats,
            'ready': not any(n['required'] for n in uniq), 'needs_user': uniq, 'fields': plan_fields}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--url')
    ap.add_argument('--gh-json')
    ap.add_argument('--lever-html', help='saved Lever apply page (offline)')
    ap.add_argument('--ashby-json', help='saved Ashby jobPosting JSON (offline)')
    ap.add_argument('--fields')
    ap.add_argument('--ats', default=None)
    a = ap.parse_args()
    if a.fields:
        fields, ats = json.load(open(a.fields)), a.ats or 'page'
    elif a.gh_json:
        fields, ats = gh_fields(json.load(open(a.gh_json))), 'greenhouse'
    elif a.lever_html:
        fields, ats = lever_fields(open(a.lever_html, encoding='utf-8').read()), 'lever'
    elif a.ashby_json:
        fields, ats = ashby_fields(json.load(open(a.ashby_json, encoding='utf-8'))), 'ashby'
    elif a.url and 'greenhouse' in a.url:
        fields, ats = gh_fields(gh_fetch(*gh_parse_url(a.url))), 'greenhouse'
    elif a.url and 'lever.co' in a.url:
        fields, ats = lever_fields(lever_fetch(*lever_parse_url(a.url))), 'lever'
    elif a.url and 'ashbyhq.com' in a.url:
        fields, ats = ashby_fields(ashby_fetch(*ashby_parse_url(a.url))), 'ashby'
    else:
        raise SystemExit('give --url (Greenhouse / Lever / Ashby), --gh-json, --lever-html, --ashby-json or --fields')
    plan = build(a.folder, fields, a.url, ats)
    out = os.path.join(a.folder, 'plan.json')
    json.dump(plan, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = sum(1 for f in plan['fields'] if f['status'] == 'ok')
    print(f"plan.json: {len(plan['fields'])} fields, {ok} answered, needs_user {len(plan['needs_user'])}, ready={plan['ready']}")
    for n in plan['needs_user'][:15]:
        print(f"  ? {n['key']}: {n['label'][:70]} — {n['why']}" + (f" | options: {n['options']}" if n['options'] else ''))


if __name__ == '__main__':
    main()
