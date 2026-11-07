#!/usr/bin/env python3
"""Oracle Recruiting Cloud runner (JSA-048, 2026-11-03; submit path JSA-147, 2026-11-04). Opens an Oracle Cloud HCM "Candidate Experience"
posting (`https://<tenant>.fa.<dc>.oraclecloud.com/hcmUI/CandidateExperience/<lang>/sites/<site>/job/<id>`) in the job
Chrome, goes straight to its apply flow (`…/job/<id>/apply/email`), enters the e-mail (and the one-time code Oracle mails
when the address already has a profile on that tenant — read from Gmail, read-only), then walks the apply sections
(Contact Information · Address · Application Questions · Supporting Documents · Diversity · Disability · Agreements ·
E-Signature …): every field answered by answer_rules.js (config/profile.json), filled, read back. It stops at the button
that reads "Submit" without clicking it (dry-run). With --folder <application folder> --submit (Joey 2026-11-04 「tier C投递」,
「开始补」) it presses that final button only when every section read back with nothing unknown, the folder is in
data/runner/approved_batches.json and not already submitted; confirmed by the thank-you page or the company's receipt
e-mail → tracker row, every tab of the posting closed. A CAPTCHA is always Joey's.

    ~/.job-agent-venv/bin/python run_oracle.py --url <posting url> [--job J01234] [--track Data_Analyst] [--resume <pdf>]
         [--out <dir>] [--wait-captcha 10] [--wait-code 3] [--attach <url text>] [--keep-tab] [--answers <json>]

Writes <out>/run_log.md, form_check.json (every field per section: label, kind, rule, want, page, ok), section_<n>.png;
one line in data/runner/results.jsonl (status dry-run | needs-user | code | captcha | closed | blocked — never submitted).
Default out: data/runner/dryrun/oracle/<tenant>_<job id>. A stop keeps the tab open; a finished dry-run closes it.
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
import job_board  # noqa: E402  (the job-board list after "How did you hear = Job Board", 2026-11-03)
import runner_common as RC  # noqa: E402  (JSA-187: opening checks · submit gate · closing books)

TRACKS = {'Data Engineer': 'Data_Engineer', 'Data Sci / Analytics': 'Data_Analyst', 'Data Analyst': 'Data_Analyst',
          'Product Manager': 'Product_Manager', 'AI Product Manager': 'Product_Manager', 'AI Agentic Eng': 'AI_Agentic_Engineer'}
EMAIL = 'alex.rivera@example.com'
NO_ADVANCE = False
SUBMIT = False                                                 # set by main() only after the approval / not-yet-submitted gates
RUN = None                                                     # runner_common.Run of this run (JSA-187)


# ---------- pure helpers (tested: scripts/test_oracle.py, DeepSeek cases) ----------
def N(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


POSTING_RE = re.compile(r'^/hcmUI/CandidateExperience/([A-Za-z_-]+)/sites/([^/?#]+)/(?:job|requisitions/preview)/(\d+)(?:/|$)', re.I)


def parse_posting(url):
    """Oracle Candidate Experience URL → {'host', 'lang', 'site', 'job'} or None. Accepts the job page
    (`/hcmUI/CandidateExperience/en/sites/CX_1/job/8491`), its apply pages (`…/job/8491/apply/email`, `/apply/section/2`),
    the older `…/sites/CX_1/requisitions/preview/8491` form, any query / fragment; host must be an `*.oraclecloud.com`
    name with `.fa.` in it (the Fusion Applications pod), scheme http(s)."""
    u = str(url or '').strip()
    try:
        p = urlparse(u)
    except ValueError:
        return None
    host = (p.hostname or '').lower()
    if p.scheme not in ('http', 'https') or not host.endswith('.oraclecloud.com') or '.fa.' not in host:
        return None
    m = POSTING_RE.match(p.path or '')
    if not m:
        return None
    return {'host': host, 'lang': m.group(1), 'site': m.group(2), 'job': m.group(3)}


def apply_url(url):
    """Posting URL → the apply flow's e-mail page `https://<host>/hcmUI/CandidateExperience/<lang>/sites/<site>/job/<id>/apply/email`
    (None when it is not an Oracle posting)."""
    p = parse_posting(url)
    if not p:
        return None
    return f"https://{p['host']}/hcmUI/CandidateExperience/{p['lang']}/sites/{p['site']}/job/{p['job']}/apply/email"


def classify(url, text):
    """Where the tab is: 'closed' (posting no longer open) · 'applied' (this e-mail already applied to the job) · 'done'
    (a thank-you / submitted page) · 'code' (the one-time verification code page) · 'email' (the e-mail step) · 'form'
    (a section of the apply flow) · 'job' (the job description page) · 'limited' (too many attempts — try again later) ·
    'unknown'."""
    u, t = str(url or ''), N(text)
    if re.search(r'too many attempts|maximum number of attempts|try again (later|in \d+ minutes?)', t, re.I):
        return 'limited'                       # too many code requests for this e-mail: wait (an employer 11-03: 30 minutes)
    if re.search(r'no longer (accepting applications|available|open)|job (is )?(not found|no longer)|position has been (filled|closed)|'
                 r'this job (posting )?(has )?(expired|closed)', t, re.I):
        return 'closed'
    if re.search(r"you('ve| have) already applied|already (submitted|applied)", t, re.I):
        return 'applied'
    if re.search(r'thank you for (applying|your application|submitting)|application (has been |was )?(successfully )?submitted|'
                 r'we (have )?received your application', t, re.I):
        return 'done'
    if re.search(r'/my-profile\b', u) and re.search(r'\bapplied on \d{1,2}/\d{1,2}/\d{2,4}\b', t, re.I):
        return 'done'                          # after Submit some tenants land on My Profile → Active job applications (Ricoh 11-04)
    if re.search(r'verification code|one-time (pass)?code|enter the code|confirm your identity|we sent (you )?a (code|pin)|\bPIN\b', t, re.I) \
            and '/apply/section' not in u:
        return 'code'
    if re.search(r'/apply/email\b', u):
        return 'email'
    if re.search(r'/apply/section/\d+', u) or re.search(r'/apply\b', u) and re.search(r'job application form', t, re.I):
        return 'form'
    if re.search(r'/job/\d+/?(\?|#|$)', u) or re.search(r'/requisitions/preview/\d+', u):
        return 'job'
    return 'unknown'


def is_final(button):
    """True when the apply flow's forward button would hand in the application: 'Submit', 'Submit Application', 'Finish',
    'Apply', 'Send' (any case); False for 'Next', 'Continue', 'Save and Continue', 'Back', 'Cancel' and an empty text."""
    b = N(button).lower()
    if not b or re.search(r'^(next|continue|save( and| &)? continue|back|previous|cancel)$', b):
        return False
    return bool(re.search(r'\bsubmit\b|\bfinish\b|^apply( now)?$|^send( application)?$|complete (my )?application', b))


def clean_label(label):
    """On-page label → the label the answer rules read: whitespace collapsed, a trailing required star / '(required)' /
    'Required' dropped, a leading star dropped. 'Country *' → 'Country'."""
    s = N(label)
    s = re.sub(r'\s*\((required|optional)\)\s*$', '', s, flags=re.I)
    s = re.sub(r'\s*\brequired\.?\s*$', '', s, flags=re.I)
    s = re.sub(r'\s*\*+\s*$', '', s)
    return re.sub(r'^\*+\s*', '', s).strip()


def pick_option(want, options):
    """The option to click for answer `want`: an exact match (case / space-insensitive) first, then the single option that
    starts with `want`, then the single option that contains `want` as whole words; None when there is none or the
    starts-with / contains steps find more than one."""
    w = N(want).lower()
    if not w:
        return None
    opts = [o for o in (options or []) if N(o)]
    for o in opts:
        if N(o).lower() == w:
            return o
    st = [o for o in opts if N(o).lower().startswith(w)]
    if len(st) == 1:
        return st[0]
    if st:
        return None
    rx = re.compile(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])')
    ct = [o for o in opts if rx.search(N(o).lower())]
    return ct[0] if len(ct) == 1 else None


US_STATES = {'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA', 'colorado': 'CO',
             'connecticut': 'CT', 'delaware': 'DE', 'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI',
             'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA',
             'maine': 'ME', 'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
             'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
             'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
             'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD',
             'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
             'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY', 'puerto rico': 'PR'}


def geo_same(want, got):
    """Address read-back: equal ignoring case / spaces; a U.S. state name equals its two-letter code ('Illinois' = 'IL');
    a city option shown as 'Chicago, Cook, IL' equals 'Chicago' (its first comma part)."""
    w, g = N(want).lower(), N(got).lower()
    if not w or not g:
        return w == g
    if w == g:
        return True
    ab = lambda x: US_STATES.get(x, x).lower()
    if ab(w) == ab(g):
        return True
    return N(g.split(',')[0]) == w or N(w.split(',')[0]) == g


def geo_pick(want, options, state=None):
    """Option to click in an Oracle geography list (City / County / Postal Code, options like 'Chicago, Cook, IL' or
    '62701'): an exact option first; else the options whose first comma part equals `want` — one left → it; several →
    the one that also names `state` (name or two-letter code) as a later comma part; None when still not exactly one."""
    w = N(want).lower()
    opts = [o for o in (options or []) if N(o)]
    if not w:
        return None
    ex = [o for o in opts if N(o).lower() == w or geo_same(want, o) and ',' not in o]
    if len(ex) == 1:
        return ex[0]
    first = [o for o in opts if N(o.split(',')[0]).lower() == w]
    if len(first) == 1:
        return first[0]
    if len(first) > 1 and state:
        st = {N(state).lower(), US_STATES.get(N(state).lower(), N(state)).lower()}
        hit = [o for o in first if any(N(p).lower() in st for p in o.split(',')[1:])]
        if len(hit) == 1:
            return hit[0]
    return None


TERMS_RE = re.compile(r'terms (and|&) conditions|terms of (use|service)', re.I)
BEYOND_RE = re.compile(r'arbitration|class action|jury|waive|automated (telephone )?dial|'
                       r'prerecorded|artificial voice|(calls?|text messages?|texts|sms)\b.{0,40}\b(consent|agree)|(consent|agree)\w*\b.{0,60}\b(calls?|text messages?|texts|sms)\b|'
                       r'marketing|promotional|newsletter|recruiting related messages|be bound by', re.I)
PRIVACY_RE = re.compile(r'privacy (notice|policy|statement)|personal (data|information)|data (protection|processing)|process(ing)? (of )?my|'
                        r'candidate privacy|i (have read|acknowledge|agree|consent)', re.I)


def email_consent(text, terms_text=None):
    """The legal-disclaimer box some tenants put on the e-mail step → 'tick' or 'ask'.
    'ask' (Joey approves the wording once, `--consent-ok`) when the box text binds the candidate to arbitration / a waiver
    ("be bound by"), consents to automated calls / texts, marketing or recruiting messages; when it names "terms and
    conditions" / "terms of use" and the linked terms text (`terms_text`, read from the tenant's dialog) is missing or
    itself contains such wording or no privacy wording; and for an empty or unrelated text (never ticked blind).
    'tick' when what remains is only the privacy / data-processing notice for this application."""
    t = N(text)
    if not t or BEYOND_RE.search(t):
        return 'ask'
    if TERMS_RE.search(t):
        tt = N(terms_text)
        if not tt or BEYOND_RE.search(tt):
            return 'ask'
        return 'tick' if PRIVACY_RE.search(tt) else 'ask'
    return 'tick' if PRIVACY_RE.search(t) else 'ask'


def consent_approved(text, cli='', approved=()):
    """Pure (tested). True when the e-mail-step box text contains (case / space-insensitive) the --consent-ok text or one
    of the profile's `consents_approved[].contains` snippets the candidate approved once; empty snippets never match."""
    t = N(text).lower()
    snips = [cli] + [(x or {}).get('contains', '') if isinstance(x, dict) else str(x or '') for x in (approved or [])]
    return any(N(x) and N(x).lower() in t for x in snips)


def _profile_consents():
    try:
        return json.load(open(jpaths.config('profile.json'), encoding='utf-8')).get('consents_approved') or []
    except (OSError, ValueError):
        return []


PROFILE_CONSENTS = _profile_consents()


def _profile_extra():
    try:
        d = json.load(open(jpaths.config('profile.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return ['LinkedIn', 'Indeed'], None
    b = (d.get('answers') or {}).get('how_heard_board') or {}
    t = (d.get('transcript') or {})
    src = os.path.join(ROOT, t['path']) if t.get('path') else None
    path = None
    if src and os.path.exists(src):                       # upload under the clean file name (not "UIUC official transcript.pdf")
        path = os.path.join(os.environ.get('TMPDIR', '/tmp'), t.get('file_name') or os.path.basename(src))
        try:
            import shutil; shutil.copyfile(src, path)
        except OSError:
            path = src
    return [b.get('default') or 'LinkedIn'] + list(b.get('fallback') or []), path


BOARD_DEFAULT, TRANSCRIPT = _profile_extra()


def _education():
    try:
        return json.load(open(jpaths.config('profile.json'), encoding='utf-8')).get('education') or []
    except (OSError, ValueError):
        return []


EDUCATION = _education()


def edu_fill(school, education, today):
    """Pure (tested). An education card imported from an old Oracle profile (an employer 11-04, JSA-147) → what its empty
    required boxes get, from config education: the entry whose `match_re` (else its school name) is found in the card's
    School text (case-insensitive) → {'city', 'state', 'graduated': 'Yes' | 'No', 'degree': "Master's" | "Bachelor's" |
    "Doctorate" | None} (+ 'school' when the card names no school and the entry was found by its level and end month —
    the card's empty School box gets it). graduated = 'No' while `current` is true or the `end` month ("YYYY-MM") is after today's month,
    else 'Yes'. No matching entry → None (Joey answers)."""
    t = N(school).lower()
    t2 = re.sub(r'\s+', '', t)                                     # letters split by a resume parse: "U NIVERSITY OF C HICAGO" (an employer 11-05)
    for e in education or []:
        rx = e.get('match_re') or re.escape(N(e.get('school')).lower())
        if t and rx and (re.search(rx, t, re.I) or re.search(rx, t2, re.I) or re.search(re.sub(r'\\? ', '', rx), t2, re.I)):
            end = str(e.get('end') or '')
            grad = 'No' if e.get('current') or (end and end[:7] > str(today)[:7]) else 'Yes'
            deg = {'master': "Master's", 'bachelor': "Bachelor's", 'phd': 'Doctorate', 'doctorate': 'Doctorate'}.get(str(e.get('level') or '').lower())
            return {'city': e.get('city'), 'state': e.get('state'), 'graduated': grad, 'degree': deg}
    # no school on the card ("B.A. in Economics From No date provided to May 2026", an employer 11-05): the one entry whose
    # level word (B.A. / B.S. / Bachelor, M.S. / Master, Ph.D.) and end month ("May 2026" = "2026-05") both match
    MON = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}
    ends = {f"{y}-{MON[m[:3]]:02d}" for m, y in re.findall(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})\b', t)}
    lv = 'bachelor' if re.search(r'\b(b\.?\s?a|b\.?\s?s|bachelor\S*)\b', t) else 'master' if re.search(r'\b(m\.?\s?s|m\.?\s?a|master\S*)\b', t) else \
        'phd' if re.search(r'\b(ph\.?\s?d|doctor\S*)\b', t) else None
    hits = [e for e in education or [] if lv and str(e.get('level') or '').lower() == lv and str(e.get('end') or '')[:7] in ends]
    if len(hits) == 1:
        e = hits[0]; end = str(e.get('end') or '')
        grad = 'No' if e.get('current') or (end and end[:7] > str(today)[:7]) else 'Yes'
        deg = {'master': "Master's", 'bachelor': "Bachelor's", 'phd': 'Doctorate', 'doctorate': 'Doctorate'}.get(lv)
        return {'city': e.get('city'), 'state': e.get('state'), 'graduated': grad, 'degree': deg, 'school': e.get('school')}
    return None


EDIT_FORM = '.standard-apply-flow-profile-item, .standard-apply-flow-timeline-form, .profile-item-container, .app-dialog, [role=dialog]'


def degree_option(want, options):
    """Pure (tested). The education card's Degree list option for edu_fill's degree ("Master's" / "Bachelor's" /
    "Doctorate"): the option equal to it (case, curly apostrophes and spaces ignored), else the one that starts with it
    ("Master's Degree", "Bachelor's degree (BA/BS)"), else the one that names it as a word ("Degree - Master's"); never
    a longer cousin ("Post doctorate degree" for Doctorate, "Some College" for anything). None when no option fits."""
    def norm(x):
        return re.sub(r'\s+', ' ', str(x or '').replace('\u2019', "'").replace('\u2018', "'")).strip().lower()
    w = norm(want)
    if not w:
        return None
    opts = [o for o in options or [] if norm(o)]
    for test in (lambda o: norm(o) == w, lambda o: norm(o).startswith(w),
                 lambda o: re.search(r'(^|[^a-z])' + re.escape(w) + r'($|[^a-z])', norm(o)) and not re.search(r'\bpost\b', norm(o))):
        hit = [o for o in opts if test(o)]
        if hit:
            return hit[0]
    return None


def fix_tiles(page, visible_only=True):
    """Imported profile cards that need fixing: a tile that says "Fields to fix" (an employer, an employer) or a card of the
    "Work and Education History" timeline marked with the red "!" (an employer 11-05: the only sign of Submit's "1 issue")."""
    t = page.locator('.apply-flow-profile-item-tile').filter(has_text=re.compile(r'fields to fix', re.I)).or_(
        page.locator('.beautiful-timeline-item').filter(has=page.locator('.beautiful-timeline-item--invalid-block')))
    return t.filter(visible=True) if visible_only else t


EDIT_ICON = '.apply-flow-profile-item-tile__edit-item-icon, .beautiful-timeline-item__edit-icon'


def blank_card(title):
    """Pure (tested). A profile card that holds nothing: Oracle titles an item with no name "Unnamed License" /
    "Unnamed Certification" / "Unnamed …" — left in a tenant's profile by an earlier run (an employer 11-06, JSA-226). Such a
    card is deleted (no candidate data is lost); a card with a real title never is."""
    return bool(re.match(r'^\s*unnamed\b', N(title or ''), re.I))


def delete_card(page, tile, log):
    """Delete one blank card: hover, its Delete icon, a confirm dialog's Yes / Delete if one opens. True when it is gone."""
    label = N(tile.inner_text())[:60]
    n0 = fix_tiles(page, visible_only=False).count()
    try: tile.hover(timeout=3000)                          # best effort: a popup over the tile blocks a hover
    except Exception: pass
    time.sleep(0.4)
    icon = tile.locator('.apply-flow-profile-item-tile__delete-icon, .beautiful-timeline-item__delete-icon').first
    try:
        icon.evaluate('b => b.click()')                       # the button's own click: an iCloud-password popup lay over it (an employer 11-06)
    except Exception:
        icon.click(force=True)
    time.sleep(1.5)
    ok_btn = page.locator('[role=dialog] button:visible, .app-dialog button:visible').filter(has_text=re.compile(r'^\s*(yes|delete|remove|ok|confirm)\s*$', re.I))
    if ok_btn.count():
        ok_btn.first.click(); time.sleep(1.5)
    gone = fix_tiles(page, visible_only=False).count() < n0
    log(f'  blank card {label!r}: ' + ('deleted' if gone else 'NOT deleted'))
    return gone


def fix_education_cards(page, log):
    """Cards that say "Fields to fix" (an old profile's education entries miss new required boxes): open each, fill the
    empty City / "Did you graduate?" (pills) or "Graduated" (checkbox) / Degree (pills, or a cx-select list — an employer 11-05,
    JSA-226) from edu_fill, SAVE, check the tile no longer says so. Only the cards of the section on screen (the other
    sections stay in the page, hidden). → list of problems."""
    problems = []
    for _ in range(6):
        tiles = fix_tiles(page)
        if not tiles.count():
            return problems
        tile = tiles.first
        title = tile.locator('.apply-flow-profile-item-tile__summary-title, .beautiful-timeline-item__title')
        if blank_card(N(title.first.inner_text()) if title.count() else ''):
            if delete_card(page, tile, log):
                continue
            problems.append(f'a blank card ({N(tile.inner_text())[:60]}) could not be deleted'); return problems
        school = N(tile.inner_text())
        want = edu_fill(school, EDUCATION, datetime.now().date())
        if not want:
            problems.append(f'an imported card needs fixing and matches no profile entry: {school[:80]}'); return problems
        try: tile.hover(timeout=3000)                          # the Edit icon shows on hover (best effort)
        except Exception: pass
        time.sleep(0.5)
        try:
            tile.locator(EDIT_ICON).first.evaluate('b => b.click()')   # the button's own click: popups can lie over it
        except Exception:
            tile.locator(EDIT_ICON).first.click(force=True)
        time.sleep(2)
        dlg = page.locator(EDIT_FORM).filter(has=page.locator('.save-btn')).last   # inline under the tile (an employer), or a dialog
        def row(label):
            return dlg.locator('.input-row').filter(has=page.locator('label, legend').filter(has_text=re.compile('^\\s*' + label, re.I)))
        city = row('City').locator('input').first
        if city.count() and not city.input_value() and want['city']:
            city.fill(want['city']); city.press('Tab'); time.sleep(0.8)   # leave the box: a click right after typing was swallowed (an employer 11-04)
            log(f'  education card: City → {want["city"]}')
        g = row('Did you graduate').locator('button').filter(has_text=re.compile(f'^\\s*{want["graduated"]}\\s*$', re.I))
        for _ in range(3):                                    # click until the pill shows as selected
            if not g.count() or 'selected' in (g.first.get_attribute('class') or ''):
                break
            g.first.click(); time.sleep(0.8)
        if g.count():
            log(f'  education card: Did you graduate? → {want["graduated"]}' + ('' if 'selected' in (g.first.get_attribute('class') or '') else ' (NOT selected)'))
        gb = row('Graduated').locator('input[type=checkbox]')
        if gb.count() and gb.first.is_checked() != (want['graduated'] == 'Yes'):
            row('Graduated').locator('label').first.click(); time.sleep(0.5)
            log(f'  education card: Graduated → {want["graduated"]}')
        sch = row('(?:School|Institution)\\b').locator('input').first   # an empty school box (a card with no school name)
        if want.get('school') and sch.count() and not N(sch.input_value()):
            if sch.get_attribute('role') == 'combobox':
                ox2 = Oracle(page, log); cid = sch.get_attribute('id')
                opts = ox2.combo_options(cid, typed=want['school'])
                o = next((x for x in opts if N(x).lower() == N(want['school']).lower()), None) or \
                    next((x for x in opts if N(want['school']).lower() in N(x).lower()), None)
                if o:
                    page.locator(f'[id="{cid}-listbox"] [role=gridcell], [id="{cid}-listbox"] [role=option]').filter(
                        has_text=re.compile('^\\s*' + re.escape(o) + '\\s*$')).first.click(); time.sleep(1.0)
                    log(f'  education card: School → {o}')
                else:
                    sch.press('Escape'); log(f'  education card: no School option for {want["school"]!r}')
            else:
                sch.fill(want['school']); sch.press('Tab'); time.sleep(0.6); log(f'  education card: School → {want["school"]}')
        DEG = '(?:Degree|Education Level)\\b'                       # an employer 11-05 calls it "Education Level"
        d = row(DEG).locator('button:not([id$="-toggle-button"])')
        combo = row(DEG).locator('input[role=combobox]')
        if want['degree'] and combo.count() and not N(combo.first.input_value()):
            cid = combo.first.get_attribute('id')
            opts = Oracle(page, log).combo_options(cid)
            o = degree_option(want['degree'], opts)
            if o:
                cell = page.locator(f'[id="{cid}-listbox"] [role=gridcell], [id="{cid}-listbox"] [role=option]').filter(
                    has_text=re.compile('^\\s*' + re.escape(o) + '\\s*$'))
                cell.first.scroll_into_view_if_needed(); cell.first.click(); time.sleep(1.0)
                log(f'  education card: Degree → {o}')
            else:
                page.keyboard.press('Escape')
                problems.append(f'education card: no Degree option for {want["degree"]!r} ({" / ".join(opts[:8])})'); return problems
        elif want['degree'] and d.count() and not any('selected' in (d.nth(i).get_attribute('class') or '') for i in range(d.count())):
            pick = d.filter(has_text=re.compile('^\\s*' + re.escape(want['degree']), re.I))
            if pick.count():
                pick.first.click(); log(f'  education card: Degree → {want["degree"]}')
        time.sleep(0.5)
        dlg.locator('.save-btn').first.click(); time.sleep(2.5)
        still = page.locator(EDIT_FORM).filter(has=page.locator('.save-btn'))
        if still.count() and still.last.is_visible():
            errs = N(still.last.inner_text())[:200]
            problems.append(f'education card did not save: {errs}'); return problems
    problems.append('education cards still need fixing after 6 tries'); return problems


JOB = {}                                                       # the store row (--job): its source / url pick the job board


def is_other_followup(label):
    """True for the free-text box Oracle shows after an 'Other' pick: 'If other, please specify', 'Other (please specify)',
    'If you selected Other, please explain', 'Please specify'; False for ordinary questions that merely contain 'other'
    ('Do you have any other names?', 'Other languages spoken')."""
    l = clean_label(label)
    return bool(re.match(r'^(if (you (selected|chose|answered) )?["\']?other["\']?\b.{0,30}(specify|explain|describe|tell us)|'
                         r'other,? \(?please (specify|explain)\)?|please (specify|explain)\b)', l, re.I))


def is_secondary_email(label):
    """True for a box that asks for an e-mail address other than the main one ("Please provide a secondary email.",
    "Alternate Email Address", "Backup email (optional)"); False for the main address and for questions about e-mail."""
    return bool(re.search(r'\b(secondary|alternate|alternative|additional|second|backup|other)\s+e-?\s?mail\b', N(label), re.I))


def is_how_heard(label):
    """A question about where the candidate learned of the job ("How did you hear about …", "Source", "Referral source")."""
    l = N(label)
    return bool(re.search(r'\bhow (did )?you (hear|heard|find|found|learn|learned) (about|of)\b|\bhow you (heard|found|learned) (about|of)\b|'
                          r'\bwhere did you (see|find|hear about|learn about)\b|^(referral |recruitment |recruiting |job |application )?source\b', l, re.I))


OTHER_RE = re.compile(r'^["\'‘’“”(]*others?\b', re.I)
NUMBER_Q = re.compile(r'\bnumber of (months|years|days|weeks)\b|\bhow (many|long)\b', re.I)


SALARY_BOX = re.compile(r'\b(salary|pay|compensation|wage|rate)\b', re.I)
NOT_AMOUNT = re.compile(r'\b(currency|frequency|period|type|unit|basis)\b', re.I)


def box_fit(label, kind, value, box):
    """Pure (tested). Does a rule's text answer fit the box as it is? `box` = {'maxlength', 'type', 'inputmode', 'block'}
    from the page. 'not_number' — an amount box (type number / inputmode numeric, or a salary / pay box of the
    structured "work-preferences" block) and the answer is not a plain amount ("Open / per internship program standard"
    was cut to "Open / per interns" in an employer's Salary Expectations, 11-05, JSA-226); 'too_long' — longer than the box's
    maxlength (the page would cut it); None — fits. Amounts may carry $, commas, a decimal point."""
    if kind not in ('text', 'textarea') or value is None:
        return None
    v = N(str(value)); box = box or {}
    amount = bool(re.fullmatch(r'\$?\s*\d{1,3}(,\d{3})*(\.\d+)?|\$?\s*\d+(\.\d+)?', v))
    numeric_box = str(box.get('type') or '').lower() == 'number' or str(box.get('inputmode') or '').lower() in ('numeric', 'decimal') or \
        (str(box.get('block') or '') == 'work-preferences' and SALARY_BOX.search(N(label)) and not NOT_AMOUNT.search(N(label)))
    if numeric_box and not amount:
        return 'not_number'
    ml = box.get('maxlength')
    if isinstance(ml, int) and ml > 0 and len(v) > ml:
        return 'too_long'
    return None


def box_plan(label, kind, required, rule_answer, related, facts, options, box=None):
    """Whether a conditional / easily over-answered box is filled (JSA-174, Goldman 11-05). None = use the shared rules'
    answer as it is; else {'action': 'fill'|'leave'|'ask', 'value', 'rule'}. Order: the candidate's own qa answer → the
    secondary e-mail (profile `contact.secondary_email`, never the main address twice) → an "Other, please specify" box
    (only when the nearest earlier choice question was answered Other; a how-heard source gets the profile's text) → a
    number asked where the rules gave words."""
    ra = rule_answer or {}
    plan = lambda act, value=None, rule='': {'action': act, 'value': value if act == 'fill' else None, 'rule': rule}
    if box is not None and ra.get('status') == 'ok' and not ra.get('leave'):
        fit = box_fit(label, kind, ra.get('value'), box)   # never cut an answer, never words in an amount box (JSA-226)
        if fit:
            return plan('ask' if required else 'leave', rule=fit)
    if str(ra.get('rule') or '').startswith('qa:'):
        return None
    facts = facts or {}
    if is_secondary_email(label):
        sec = re.sub(r'\s+', '', str(facts.get('secondary_email') or ''))
        prim = re.sub(r'\s+', '', str(facts.get('primary_email') or ''))
        if sec and sec.lower() != prim.lower():
            return plan('fill', sec, 'secondary_email')
        return plan('ask' if required else 'leave', rule='secondary_email')
    if is_other_followup(label):
        rel = related or {}
        if not OTHER_RE.match(N(rel.get('answer'))):
            return plan('ask' if required else 'leave', rule='other_followup')
        if not is_how_heard(rel.get('label') or ''):
            return plan('ask', rule='other_followup')
        if options:
            o = [x for x in options if OTHER_RE.match(N(x))]
            return plan('fill', o[0], 'other_followup') if len(o) == 1 else plan('ask', rule='other_followup')
        t = N(facts.get('how_heard_text'))
        return plan('fill', t, 'other_followup') if t else plan('ask', rule='other_followup')
    if kind in ('text', 'textarea') and not options and NUMBER_Q.search(N(label)) and ra.get('status') == 'ok' \
            and not re.fullmatch(r'\d+(\.\d+)?', N(ra.get('value'))):
        return plan('ask', rule='number_asked')
    return None


def _secondary_email():
    try:
        c = (json.load(open(jpaths.config('profile.json'), encoding='utf-8')).get('contact') or {})
    except (OSError, ValueError):
        return None
    return c.get('secondary_email') or None


SECONDARY_EMAIL = _secondary_email()
CHOICE_KINDS = ('select', 'pills', 'pills_multi', 'radio', 'checks')


def same(want, got):
    """Read-back comparison: case / space-insensitive; phones by the last 10 digits; lists (multi-select) as sets."""
    if isinstance(want, (list, tuple)) or isinstance(got, (list, tuple)):
        a = {N(x).lower() for x in (want if isinstance(want, (list, tuple)) else [want]) if N(x)}
        b = {N(x).lower() for x in (got if isinstance(got, (list, tuple)) else [got]) if N(x)}
        return a == b
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


def now():
    return datetime.now().isoformat(timespec='seconds')


# ---------- page ----------
# Every field of the apply flow is an `.input-row` inside an `.apply-flow-block`; the extractor tags each with data-ox=<n>
# so the filler can find it again, and returns its kind, label, required flag, options and current value.
EXTRACT = r"""() => {
  const vis = e => !!(e && (e.offsetWidth || e.offsetHeight || e.getClientRects().length));
  const txt = e => (e ? e.innerText || e.textContent || '' : '').replace(/\s+/g, ' ').trim();
  const out = []; let n = 0;
  // numbers from an earlier extract stay on rows of a section that is now hidden → two [data-ox="6"], the hidden one first
  // (Goldman 11-05, JSA-174): clear them all before numbering the visible rows again
  document.querySelectorAll('[data-ox]').forEach(e => e.removeAttribute('data-ox'));
  document.querySelectorAll('[data-oxfile]').forEach(e => e.removeAttribute('data-oxfile'));
  for (const blk of document.querySelectorAll('.apply-flow-block')) {
    const bcls = [...blk.classList].find(c => c.startsWith('apply-flow-block--')) || '';
    const block = bcls.replace('apply-flow-block--', '');
    const btitle = txt(blk.querySelector('.apply-flow-block__title'));
    for (const row of blk.querySelectorAll('.input-row')) {
      if (!vis(row) || row.parentElement.closest('.input-row')) continue;
      const labEl = row.querySelector('.input-row__label, legend');
      let label = labEl ? txt(labEl) : '';
      const req = !!(row.querySelector('.input-row__label--required') || row.querySelector('[aria-required=true]'));
      const f = { n: n, block, btitle, label, required: req, kind: null, options: [], value: '' };
      const pills = row.querySelector('ul.cx-select-pills-container');
      const tel = row.querySelector('input[type=tel]');
      const combo = row.querySelector(tel ? 'input.cx-select-input' : 'input.cx-select-input[role=combobox]');   // the phone's country code is a read-only cx-select
      const radios = [...row.querySelectorAll('input[type=radio]')];
      const checks = [...row.querySelectorAll('input[type=checkbox]')];
      const text = row.querySelector('input.input-row__control:not([type=checkbox]):not([type=radio]), textarea');
      if (row.classList.contains('datepicker-row')) { f.kind = 'date'; f.value = [...row.querySelectorAll('input')].map(i => i.value).join('/'); }
      else if (pills) {
        f.kind = pills.getAttribute('role') === 'radiogroup' ? 'pills' : 'pills_multi';
        const bs = [...pills.querySelectorAll('button')];
        f.options = bs.map(txt);
        const on = bs.filter(b => b.getAttribute('aria-checked') === 'true' || b.getAttribute('aria-pressed') === 'true' || /--selected|selected/.test(b.className));
        f.value = f.kind === 'pills' ? (on[0] ? txt(on[0]) : '') : on.map(txt);
        if (!label) label = pills.getAttribute('aria-label') || '';
      }
      else if (tel && combo) { f.kind = 'phone'; f.value = tel.value || ''; f.code = combo.value || ''; f.combo_id = combo.id; f.code_locked = combo.readOnly || /disabled/.test(combo.className); }
      else if (combo) { f.kind = 'select'; f.value = combo.value || ''; f.combo_id = combo.id; f.geo = row.classList.contains('geo-hierarchy-form-element'); }
      else if (radios.length) {
        f.kind = 'radio';
        f.options = radios.map(r => txt(document.querySelector('label[for="' + CSS.escape(r.id) + '"]')));
        const on = radios.find(r => r.checked); f.value = on ? txt(document.querySelector('label[for="' + CSS.escape(on.id) + '"]')) : '';
      }
      else if (row.classList.contains('input-row--checkbox') && checks.length === 1) {
        f.kind = 'checkbox'; f.value = checks[0].checked;
        label = label || txt(row.querySelector('.apply-flow-input-checkbox__label')) || txt(row);
      }
      else if (checks.length) {
        f.kind = checks.length > 1 ? 'checks' : 'checkbox';
        const lab = c => { const l = (c.id && document.querySelector('label[for="' + CSS.escape(c.id) + '"]')) || c.closest('label');
                           return txt(l && (l.querySelector('.apply-flow-input-checkbox__label') || l)); };
        if (f.kind === 'checks') { f.options = checks.map(lab); f.value = checks.filter(c => c.checked).map(lab); }
        else { f.value = checks[0].checked; f.option = lab(checks[0]); label = label || f.option; }
      }
      else if (text) {
        if (/honey/i.test(text.name || '') || /honey/i.test(text.id || '')) continue;      // bot trap: never filled
        f.kind = text.tagName === 'TEXTAREA' ? 'textarea' : 'text'; f.value = text.value || ''; f.type = text.type; f.maxlength = text.maxLength > 0 ? text.maxLength : null; f.inputmode = text.getAttribute('inputmode') || '';
      }
      else continue;
      f.label = label;
      row.setAttribute('data-ox', String(n)); n++;
      out.push(f);
    }
  }
  const files = [...document.querySelectorAll('.apply-flow-block input[type=file]')].map((e, i) => {
    const box = e.closest('.file-form-element, .apply-flow-block__component, .input-row') || e.parentElement;
    e.setAttribute('data-oxfile', String(i));
    return { i, id: e.id, label: txt(box).slice(0, 120), block: ((e.closest('.apply-flow-block') || {}).className || '') };
  });
  const upload_text = txt(document.querySelector('.apply-flow-block--file-upload'));
  const btns = [...document.querySelectorAll('.apply-flow-pagination button, .apply-flow-pagination__button')].filter(vis)
     .map(b => ({ text: txt(b) || b.getAttribute('aria-label') || '' }));
  const errors = [...document.querySelectorAll('.input-row--invalid')].filter(vis).map(r => txt(r).slice(0, 160)).slice(0, 12);
  const steps = txt(document.querySelector('.apply-flow-header'));
  const esign = txt(document.querySelector('.apply-flow-esign__description'));
  const agreements = txt(document.querySelector('.apply-flow-block--agreements'));
  return { url: location.href, fields: out, files, upload_text, buttons: btns, errors, steps, esign, agreements,
           text: txt(document.body).slice(0, 6000) };
}"""


class Oracle:
    def __init__(self, page, log):
        self.page, self.log = page, log
        self.nmap = {}

    def state(self):
        st = self.page.evaluate(EXTRACT)
        seen = {}
        for f in st['fields']:                                 # a key that survives re-rendering (data-ox numbers shift)
            k = f"{f['block']}|{clean_label(f['label'])}|{f['kind']}"
            seen[k] = seen.get(k, 0) + 1
            f['key'] = f"{k}|{seen[k]}"
        self.nmap = {f['key']: f['n'] for f in st['fields']}
        return st

    def row(self, key):
        """The row of a field key, by the data-ox number of the latest extract (numbers shift when rows appear)."""
        return self.page.locator(f'[data-ox="{self.nmap.get(key, -1)}"]')

    def shown(self, key):
        """The row is still on the page and visible: a conditional row an earlier answer just hid keeps its data-ox number
        until the next extract — filling it waited 30 s for a click that cannot happen (Goldman 11-05, JSA-174)."""
        loc = self.row(key)
        try:
            return loc.count() == 1 and loc.first.is_visible()
        except Exception:
            return False

    def fill_text(self, key, value):
        loc = self.row(key).locator('input.input-row__control, textarea').first
        loc.click(timeout=10000); loc.fill(''); loc.press_sequentially(str(value), delay=15)
        loc.dispatch_event('change'); loc.press('Tab')

    def open_combo(self, combo_id):
        inp = self.page.locator(f'[id="{combo_id}"]')
        inp.scroll_into_view_if_needed(); inp.click(); time.sleep(1.0)
        return inp

    def combo_options(self, combo_id, typed=None):
        """Open a cx-select (optionally type into it) and read its option texts; leaves the list open."""
        inp = self.open_combo(combo_id)
        if typed is not None:
            inp.fill(''); inp.press_sequentially(str(typed)[:30], delay=30)
        last = None
        for _ in range(8):                                     # the list loads / filters by ajax: wait until two reads agree
            time.sleep(0.7)
            opts = self.page.evaluate("(id) => { const l = document.getElementById(id + '-listbox'); return l ? [...l.querySelectorAll('[role=gridcell], [role=option]')].map(o => (o.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean) : []; }", combo_id)
            if opts == last and opts:
                break
            last = opts
        return opts or []

    def pick_combo(self, combo_id, want, search=None, picker=None, typed_first=False):
        """Choose `want` in a cx-select: read the full list first (short lists), else type `search` / the value to filter
        (`typed_first`: type straight away — geography lists only load on typing). Returns None on success, else the
        option texts seen."""
        picker = picker or pick_option
        o, opts = None, []
        if not typed_first:
            opts = self.combo_options(combo_id)
            o = picker(want, opts)
        if o is None:
            opts = self.combo_options(combo_id, typed=search or want)
            o = picker(want, opts)
        if o is None:
            self.page.keyboard.press('Escape'); time.sleep(0.3)
            return opts
        cell = self.page.locator(f'[id="{combo_id}-listbox"] [role=gridcell], [id="{combo_id}-listbox"] [role=option]').filter(
            has_text=re.compile('^\\s*' + re.escape(o) + '\\s*$'))
        cell.first.scroll_into_view_if_needed(); cell.first.click(); time.sleep(1.0)
        return None

    def click_pill(self, key, option):
        b = self.row(key).locator('ul.cx-select-pills-container button').filter(has_text=re.compile('^\\s*' + re.escape(N(option)) + '\\s*$'))
        if not b.count():
            return False
        b.first.scroll_into_view_if_needed(); b.first.click(); time.sleep(0.4)
        return True

    def click_label(self, key, option=None):
        """Radio / checkbox in an Oracle row: the input is hidden — click its label (by text when given)."""
        labs = self.row(key).locator('label.apply-flow-input-radio, label.apply-flow-input-checkbox')
        if option is not None:
            labs = labs.filter(has_text=re.compile('^\\s*' + re.escape(N(option)) + '\\s*$'))
        if not labs.count():
            return False
        labs.first.scroll_into_view_if_needed(); labs.first.click(); time.sleep(0.3)
        return True

    def read_key(self, key):
        st = self.state()
        return next((f for f in st['fields'] if f['key'] == key), None)


def qtype(f):
    return {'text': 'text', 'textarea': 'textarea', 'select': 'select', 'pills': 'radio', 'pills_multi': 'select',
            'radio': 'radio', 'checkbox': 'checkbox', 'checks': 'select', 'phone': 'text', 'date': 'date'}[f['kind']]


def upload_resume(ox, st, resume, log):
    """The resume slot of 'Supporting Documents': an `input[type=file]` whose box says Resume. Returns the row for
    form_check.json (want = file name, page = whether the name shows in the block)."""
    row = {'label': 'Resume', 'kind': 'file', 'required': False, 'want': os.path.basename(resume) if resume else None, 'rule': 'resume'}
    slot = next((x for x in st['files'] if re.search(r'resume|\bcv\b', x['label'], re.I)), None) or (st['files'][0] if st['files'] else None)
    if not slot:
        return None
    base = os.path.basename(resume) if resume else ''
    if resume and base.lower() not in (st.get('upload_text') or '').lower():
        ox.page.locator(f'[data-oxfile="{slot["i"]}"]').set_input_files(resume)
        log('resume uploaded — waiting for its name to show')
        for _ in range(20):
            time.sleep(1.5)
            if base.lower() in N(ox.page.evaluate("() => (document.querySelector('.apply-flow-block--file-upload') || {}).innerText || ''")).lower():
                break
    shown = N(ox.page.evaluate("() => (document.querySelector('.apply-flow-block--file-upload') || {}).innerText || ''"))
    row['page'] = base if base and base.lower() in shown.lower() else ''
    row['ok'] = bool(row['page']) if resume else True
    return row


def upload_enrollment(ox, st, log):
    """An "Intern Proof of Enrollment" / enrollment-verification / transcript slot → the profile's official transcript
    (`config/profile.json` → transcript; Joey 2026-11-03 「先用 UIUC 成绩单」 until a UChicago enrollment letter exists)."""
    slot = next((x for x in st['files'] if re.search(r'proof of enrol+ment|enrol+ment (verification|proof)|transcript', x['label'], re.I)), None)
    if not slot or not TRANSCRIPT:
        return None
    base = os.path.basename(TRANSCRIPT)
    row = {'label': clean_label(slot['label']), 'kind': 'file', 'required': False, 'want': base, 'rule': 'transcript'}
    txt = lambda: N(ox.page.evaluate("() => [...document.querySelectorAll('.apply-flow-block--file-upload')].map(e => e.innerText).join(' ')")).lower()
    if base.lower() not in txt():
        ox.page.locator(f'[data-oxfile="{slot["i"]}"]').set_input_files(TRANSCRIPT)
        log('proof of enrollment uploaded (the profile transcript)')
        for _ in range(20):
            time.sleep(1.5)
            if base.lower() in txt():
                break
    row['page'] = base if base.lower() in txt() else ''
    row['ok'] = bool(row['page'])
    return row


def find_cover(folder):
    """The application folder's cover letter: the first `*Cover_Letter*.pdf` (case-insensitive, sorted); None when the
    folder is empty / missing or holds none."""
    if not folder or not os.path.isdir(folder):
        return None
    hits = sorted(x for x in os.listdir(folder) if x.lower().endswith('.pdf') and 'cover_letter' in x.lower())
    return os.path.join(folder, hits[0]) if hits else None


def upload_cover(ox, st, cover, log):
    """A cover-letter slot (Joey 2026-11-03 「求职信如果是选填的默认写」: optional slots get the letter too). With a
    letter: upload it and read its name back. Without one (dry runs): record 'cover letter slot (optional) — would
    upload' instead of skipping it silently."""
    slot = next((x for x in st['files'] if re.search(r'cover', x['label'], re.I)), None)
    if not slot:
        return None
    row = {'label': 'Cover letter', 'kind': 'file', 'required': False, 'rule': 'cover_letter'}
    if not cover:
        row.update(want=None, page='', ok=True, note='cover letter slot (optional) — would upload (no letter in the folder)')
        log('cover letter slot (optional) — would upload; no *Cover_Letter*.pdf in the folder')
        return row
    base = os.path.basename(cover)
    row['want'] = base
    txt = lambda: N(ox.page.evaluate("() => (document.querySelector('.apply-flow-block--file-upload') || {}).innerText || ''")).lower()
    if base.lower() not in txt():
        ox.page.locator(f'[data-oxfile="{slot["i"]}"]').set_input_files(cover)
        log('cover letter uploaded')
        for _ in range(20):
            time.sleep(1.5)
            if base.lower() in txt():
                break
    row['page'] = base if base.lower() in txt() else ''
    row['ok'] = bool(row['page'])
    return row


BOX_WHY = {'secondary_email': {'leave': 'optional second e-mail; the profile has none (contact.secondary_email)',
                               'ask': 'a second e-mail address is required and the profile has none (contact.secondary_email)'},
           'other_followup': {'leave': 'the question before it was not answered Other',
                              'ask': 'an "Other, please specify" box needs the candidate\'s own words'},
           'number_asked': {'ask': 'a number is asked and the profile facts give none'},
           'not_number': {'leave': 'an amount box (optional) and the rules gave words — left empty, never cut',
                          'ask': 'an amount box: the rules gave words, the candidate gives the number'},
           'too_long': {'leave': 'the answer is longer than the box allows (optional) — left empty, never cut',
                        'ask': 'the answer is longer than the box allows — the candidate gives a shorter one'}}


def related_question(order, f, rows):
    """The nearest earlier choice question on the page (list / pills / radio / checks) and its answer — what the runner
    chose for it (latest row), else what the page holds. None when there is none above `f`."""
    i = next((j for j, g in enumerate(order) if g['key'] == f['key']), -1)
    for g in reversed(order[:max(i, 0)]):
        if g['kind'] in CHOICE_KINDS:
            r = next((r for r in reversed(rows) if r.get('key') == g['key'] and r.get('want') is not None), None)   # upload rows have no key (JSA-220)
            ans = r['want'] if r else g['value']
            return {'label': clean_label(g['label']), 'answer': ' | '.join(ans) if isinstance(ans, (list, tuple)) else N(ans)}
    return None


GEO_ORDER = ['country', 'postal', 'zip', 'state', 'county', 'city', 'address line 1']   # the postal code fills city / county / state


def geo_rank(label):
    l = clean_label(label).lower()
    return next((i for i, k in enumerate(GEO_ORDER) if l.startswith(k)), len(GEO_ORDER))


def needs_retry(row, f):
    """A row this section already filled whose answer the page no longer shows, with no error recorded: an answer to an
    earlier question revealed a row and the page re-rendered the block, dropping a click made at the same time (an employer
    11-05: the ACE-employee radio came back empty after the sponsorship Yes revealed a box above it, JSA-220). Filled once
    more; text rows and rows with an error are left to the read-back."""
    if not row or row.get('want') is None or row.get('error') or row.get('gone'):
        return False
    if f['kind'] not in ('radio', 'pills', 'checkbox', 'select', 'text', 'textarea', 'phone'):
        return False
    got, want = f.get('value'), row['want']
    if f['kind'] == 'checkbox':
        return bool(got) != bool(want)
    if f.get('geo'):
        return False
    if f['kind'] in ('radio', 'pills', 'select'):
        o = pick_option(want, f.get('options') or []) or want
        return not (same(o, got) or same(want, got))
    if f['kind'] == 'phone':
        return re.sub(r'\D', '', str(got or ''))[-10:] != re.sub(r'\D', '', str(want))[-10:]
    return not same(want, got)


def fill_section(ox, overrides, resume, log):
    """Answer, fill and read back every field of the current section. Returns (rows, problems, unknown, state)."""
    st = ox.state()
    rows, problems, unknown = [], [], []
    if st['files']:
        r = upload_resume(ox, st, resume, log)
        if r:
            rows.append(r)
            if not r['ok']:
                problems.append('resume upload not shown on the page')
        time.sleep(2)
        e = upload_enrollment(ox, ox.state(), log)
        if e:
            rows.append(e)
        c = upload_cover(ox, ox.state(), COVER, log)
        if c:
            rows.append(c)
            if not c['ok']:
                problems.append('cover letter upload not shown on the page')
        st = ox.state()                                        # a resume parse may prefill fields: read them after it
    done, how_text, retried, planned = set(), [], set(), {}
    for _pass in range(5):                                     # a pick can reveal a dependent row ("If other, please specify")
        order = st['fields']                                   # page order of this extract: the nearest earlier choice question
        again = {f['key'] for f in order if f['key'] in done and f['key'] not in retried and needs_retry(planned.get(f['key']), f)}
        fields = [f for f in order if f['key'] not in done or f['key'] in again]
        if not fields:
            break
        if again:
            log(f'filled again (the page lost the answer while another row appeared): {len(again)} row(s)')
            rows = [r for r in rows if r.get('key') not in again]
        retried |= again
        done |= {f['key'] for f in fields}
        for f in fields:
            if f['kind'] == 'select' and not f['options']:
                try:
                    f['options'] = [] if f.get('geo') else ox.combo_options(f['combo_id'])
                finally:
                    ox.page.keyboard.press('Escape'); time.sleep(0.2)
        qs = []
        for f in fields:
            f['rlabel'] = clean_label(f['label']) or clean_label(f.get('option') or '')
            qs.append({'key': str(f['n']), 'label': f['rlabel'], 'type': qtype(f), 'options': f['options']})
        ans = answer(qs) if qs else {}
        plan = []
        for f in fields:
            lab = f['rlabel']
            a = overrides.get(lab) or ans.get(str(f['n'])) or {}
            row = {'n': f['n'], 'key': f['key'], 'block': f['block'], 'label': lab, 'kind': f['kind'], 'required': f['required']}
            if f['kind'] == 'date' and not f['required']:
                a = {}                                             # optional dates (veteran discharge date …) stay empty
            if is_other_followup(lab) and not how_text:       # the profile's source text, asked of the rules once
                h = answer([{'key': 'k', 'label': 'How did you hear about this job?', 'type': 'text', 'options': []}]).get('k') or {}
                how_text.append(h.get('value') if h.get('status') == 'ok' else '')
            bp = box_plan(lab, f['kind'], f['required'], a, related_question(order, f, rows),
                          {'primary_email': EMAIL, 'secondary_email': SECONDARY_EMAIL, 'how_heard_text': (how_text or [''])[0]}, f['options'],
                          {'maxlength': f.get('maxlength'), 'type': f.get('type'), 'inputmode': f.get('inputmode'), 'block': f.get('block')})
            if bp:                                             # JSA-174: secondary e-mail / "Other, please specify" / a number asked
                a = ({'status': 'ok', 'value': bp['value'], 'rule': bp['rule']} if bp['action'] == 'fill' else
                     {'status': 'ok', 'leave': True, 'rule': bp['rule'], 'why': BOX_WHY[bp['rule']]['leave']} if bp['action'] == 'leave' else
                     {'status': 'unknown', 'rule': bp['rule'], 'why': BOX_WHY[bp['rule']]['ask']})
            if a.get('status') != 'ok' and f['options'] and not bp:   # a job-board list ("Career Communicatees/Job Boards"): the row's own board,
                pick = job_board.board_pick(f['options'], JOB.get('source'), JOB.get('url'), BOARD_DEFAULT)   # else LinkedIn, else Indeed (Joey 11-03)
                if pick:
                    a = {'status': 'ok', 'value': pick, 'rule': 'how_heard_board'}
            if bp and bp['action'] == 'leave' and bp['rule'] in ('not_number', 'too_long') and f['value'] and \
                    box_fit(lab, f['kind'], f['value'], {'maxlength': None, 'type': f.get('type'), 'inputmode': f.get('inputmode'), 'block': f.get('block')}) == 'not_number':
                a = {'status': 'ok', 'value': '', 'rule': 'clear_' + bp['rule']}   # an old run's words left in the amount box
                                                                                  # ("Open / per interns", an employer 11-06): emptied
            if a.get('status') != 'ok' or a.get('leave') or (a.get('rule') == 'middle_initial' and not f['required']):
                row.update(want=None, rule=a.get('rule'), page=f['value'], why=a.get('why'))
                if (f['required'] or (bp and bp['action'] == 'ask')) and not f['value']:
                    row['unknown'] = lab + (f" (options: {' / '.join(f['options'][:8])})" if f['options'] else '') + \
                        (f" — {a['why']}" if bp and a.get('why') else '')
                elif f['required'] and f['value']:
                    row['note'] = 'prefilled by the site, no rule — kept'
                rows.append(row); continue
            want = a.get('value')
            if f['kind'] == 'checkbox':
                want = bool(want) if isinstance(want, bool) else bool(re.match(r'^(yes|true|i agree|i accept|i consent|i acknowledge)', str(want), re.I))
            if f['kind'] in ('checks', 'pills_multi'):
                want = [x.strip() for x in str(want).split(' | ') if x.strip()]
                want = [pick_option(w, f['options']) or w for w in want]
            row.update(want=want, rule=a.get('rule'))
            if a.get('combo'):
                row['combo'] = a['combo']
            plan.append((f, row))
            rows.append(row)
            planned[f['key']] = row
        # geo-hierarchy fields depend on each other: country → state → county → city → postal code → street
        plan.sort(key=lambda fr: (0, geo_rank(fr[0]['label'])) if fr[0].get('geo') else (1, 0))
        for f, row in plan:
            want = row['want']
            if not ox.shown(f['key']):                         # an earlier answer of this pass hid the row: not needed now
                row['gone'] = True; continue
            try:
                k = f['kind']
                if k in ('text', 'textarea'):
                    if N(f['value']).lower() != N(want).lower():
                        ox.fill_text(f['key'], want)
                elif k == 'select':
                    cur = (ox.read_key(f['key']) or {}).get('value', f['value']) if f.get('geo') else f['value']
                    if f.get('geo') and geo_same(want, cur):
                        pass                                       # already set (by the postal code)
                    elif N(cur).lower() != N(want).lower():
                        if f.get('geo') and clean_label(f['label']).lower().startswith('address line'):
                            inp = ox.open_combo(f['combo_id']); inp.fill(''); inp.press_sequentially(str(want), delay=20)
                            time.sleep(1.0); ox.page.keyboard.press('Escape'); inp.press('Tab')
                        elif f.get('geo') and not clean_label(f['label']).lower().startswith('country'):
                            stv = next((r2['want'] for f2, r2 in plan if clean_label(f2['label']).lower().startswith('state')), None)
                            miss = ox.pick_combo(f['combo_id'], want, None, picker=lambda w, o: geo_pick(w, o, stv), typed_first=True)
                            if miss is not None:
                                row['error'] = 'option not found: ' + ' / '.join(miss[:6])
                        else:
                            miss = ox.pick_combo(f['combo_id'], want, row.get('combo'))
                            if miss is not None:
                                row['error'] = 'option not found: ' + ' / '.join(miss[:6])
                elif k == 'phone':
                    inp = ox.row(f['key']).locator('input[type=tel]')
                    if not f.get('code_locked') and not re.search(r'\+1\b|united states', f.get('code') or '', re.I):
                        miss = ox.pick_combo(f['combo_id'], 'United States (+1)', 'United States')
                        if miss is not None:
                            o = next((x for x in miss if re.search(r'united states', x, re.I) and '+1' in x), None)
                            if o:
                                ox.pick_combo(f['combo_id'], o, 'United States')
                    if re.sub(r'\D', '', f['value'])[-10:] != re.sub(r'\D', '', str(want))[-10:]:
                        inp.click(); inp.fill(''); inp.press_sequentially(re.sub(r'\D', '', str(want))[-10:], delay=20); inp.press('Tab')
                elif k == 'pills':
                    o = pick_option(want, f['options'])
                    if not o:
                        row['error'] = 'option not found'
                    elif N(f['value']).lower() != N(o).lower() and not ox.click_pill(f['key'], o):
                        row['error'] = 'pill not clickable'
                elif k == 'pills_multi':
                    for o in want:
                        if o not in (f['value'] or []):
                            ox.click_pill(f['key'], o)
                elif k == 'radio':
                    o = pick_option(want, f['options'])
                    if not o:
                        row['error'] = 'option not found'
                    elif N(f['value']).lower() != N(o).lower() and not ox.click_label(f['key'], o):
                        row['error'] = 'radio not clickable'
                elif k == 'checks':
                    for o in f['options']:
                        if (o in want) != (o in (f['value'] or [])):
                            ox.click_label(f['key'], o)
                elif k == 'checkbox':
                    if bool(f['value']) != bool(want):
                        ox.click_label(f['key'])
                elif k == 'date':
                    row['error'] = 'date fields are not filled by the runner'
            except Exception as e:
                row['error'] = f'{type(e).__name__}: {str(e)[:120]}'
        time.sleep(1.0)
        st = ox.state()
    time.sleep(1.2)
    # read back
    st2 = ox.state()
    by = {f['key']: f for f in st2['fields']}
    for row in rows:
        if row['kind'] == 'file':
            continue
        if row['key'] not in by:                               # hidden again by a later answer: the page does not send it
            row.update(page='', ok=True, gone=True, note='no longer shown after an earlier answer — not filled')
            continue
        g = by[row['key']]
        got = g.get('value', '')
        if row['kind'] == 'phone':
            row['code'] = g.get('code')
        row['page'] = got
        if row.get('want') is None:
            row['ok'] = not (row['required'] and not got)
        elif row['kind'] == 'checkbox':
            row['ok'] = bool(got) == bool(row['want'])
        elif row['kind'] == 'select' and g.get('geo'):
            row['ok'] = geo_same(row['want'], got)
        elif row['kind'] in ('pills', 'radio', 'select'):
            o = pick_option(row['want'], g.get('options') or []) or row['want']
            row['ok'] = same(o, got) or same(row['want'], got)
        else:
            row['ok'] = same(row['want'], got)
        if row['kind'] == 'phone' and row['ok'] and not g.get('code_locked') and not re.search(r'\+1\b|united states', g.get('code') or '', re.I):
            row['ok'] = False; row['error'] = f"country code {g.get('code')!r}"
        if not row['ok']:
            problems.append(f"{row['label'][:70]}: want {row.get('want')!r}, page {got!r}" + (f" ({row['error']})" if row.get('error') else ''))
    have = {r.get('key') for r in rows}
    for g in st2['fields']:                                    # a row an answer of the last pass revealed: never left unchecked
        if g['key'] in have:
            continue
        lab = clean_label(g['label']) or clean_label(g.get('option') or '')
        row = {'n': g['n'], 'key': g['key'], 'block': g['block'], 'label': lab, 'kind': g['kind'], 'required': g['required'],
               'want': None, 'rule': None, 'page': g['value'], 'note': 'appeared after the last fill pass'}
        row['ok'] = not (g['required'] and not g['value'])
        if not row['ok']:
            row['unknown'] = lab
            problems.append(f"{lab[:70]}: appeared after the last fill pass, empty")
        rows.append(row)
    unknown += [r['unknown'] for r in rows if r.get('unknown') and not r.get('gone')]
    return rows, problems, unknown, st2


WAIT_CODE = 3.0                                                # --wait-code minutes


TENANT = ''                                                     # this posting's Oracle pod id ("egud", "ewgu"), set in run()


def tenant_id(url):
    """Pure (tested). The Oracle pod id of a posting URL — the first host label without "fa-" and without what follows the
    next "-": egud.fa.us2.oraclecloud.com → "egud", fa-ewgu-saasfaprod1.fa.ocs.oraclecloud.com → "ewgu"; '' otherwise."""
    host = (urlparse(url or '').hostname or '').lower()
    if 'oraclecloud.com' not in host:
        return ''
    first = re.sub(r'^fa-', '', host.split('.')[0])
    return first.split('-')[0]


def code_mail_ok(sender, body, tenant, company=None):
    """Pure (tested). Is this one-time-code mail for this tenant? Oracle's own senders name their pod
    ("egay.fa.sender@workflow.email…"): only our pod's counts — a code from another tenant's run a minute earlier was typed
    into an employer's page and refused (11-05, JSA-226). A company's own sender ("an employer Inc." <noreply@autozone.com>)
    counts when the mail names the company (its first word, case-insensitive); with no company known it counts."""
    m = re.search(r'\b([a-z0-9]+)\.fa\.sender', (sender or '').lower())
    if m:
        return bool(tenant) and m.group(1) == tenant.lower()
    word = re.split(r'[\s,.&]+', (company or '').strip())[0] if (company or '').strip() else ''
    if not word:
        return True
    return word.lower() in ((sender or '') + ' ' + (body or '')).lower()


CODE_BTN = re.compile(r'^\s*(verify|next|continue|submit|confirm)\s*$', re.I)


def code_button(pg):
    """The code step's own Verify button: the apply-flow dialog's button first (the cookie dialog and the legal-terms
    dialog carry buttons too — an employer 11-05 waited 30 s on one), then any visible matching button outside a cookie bar."""
    for css in ('.apply-flow-dialog__button:visible', 'button:visible:not(.cookie-consent__button):not(.app-dialog__footer-button)'):
        loc = pg.locator(css).filter(has_text=CODE_BTN)
        if loc.count():
            return loc.first
    return None


def type_code(pg, code):
    boxes = pg.locator('input[autocomplete="one-time-code"], input.pin-code-input__input, input.pin-code-input, input[id^="pin-code"], input[name*="pin" i], input[aria-label*="digit" i]').filter(visible=True)
    if boxes.count() > 1:
        for i, ch in enumerate(code[:boxes.count()]):
            boxes.nth(i).click(); boxes.nth(i).fill(''); boxes.nth(i).press_sequentially(ch, delay=40)   # key events: the page tracks each box
    elif boxes.count() == 1:
        boxes.first.click(); boxes.first.fill(''); boxes.first.press_sequentially(code, delay=40)
    else:
        inp = pg.locator('input[type=text]:visible, input[type=tel]:visible, input[type=number]:visible').first
        inp.click(); inp.fill(''); inp.press_sequentially(code, delay=40)
    time.sleep(1)
    return boxes


def enter_code(ox, out, log, since):
    """Oracle's one-time code for an e-mail that already has a profile on this tenant: read it from Gmail (read-only,
    newest mail after `since` from this tenant — code_mail_ok), type it, press the dialog's Verify. A refused code → one
    more try with a newer code (never the same one). True when the page moved on."""
    import gmail_code
    pg = ox.page
    accept = lambda frm, body: code_mail_ok(frm, body, TENANT, (JOB or {}).get('company'))
    typed = set()
    for attempt in range(2):
        code = None
        end = time.time() + (WAIT_CODE * 60 if not attempt else 90)
        while time.time() < end and not code:
            try:
                code = gmail_code.find_code(since=since, exclude=typed, accept=accept)
            except SystemExit as e:
                log(f'Gmail not readable: {e}'); return False
            except Exception as e:
                log(f'Gmail read error {type(e).__name__}: {str(e)[:120]}')
            if not code:
                time.sleep(10)
        if not code:
            log('no ' + ('newer ' if attempt else '') + 'verification code arrived in Gmail'); break
        log('verification code read from Gmail (not logged)' + (' — second try' if attempt else ''))
        typed.add(code)
        boxes = type_code(pg, code)
        btn = code_button(pg)
        try:
            if btn is not None:
                btn.click(timeout=10000)
            else:
                (boxes.last if boxes.count() else pg.keyboard).press('Enter')
        except Exception as e:                            # the cookie bar lies over Verify (an employer 11-06): the button's own click
            log(f'code step: Verify click failed ({type(e).__name__}) — clicking it from the page script')
            try:
                btn.evaluate('b => b.click()')
            except Exception:
                try: (boxes.last if boxes.count() else pg.keyboard).press('Enter')
                except Exception: pass
        time.sleep(6)
        if classify(pg.url, pg.inner_text('body')) != 'code':
            return True
        log('code step after Verify: ' + code_page_info(pg))
        if attempt == 0:
            r = pg.get_by_text(re.compile(r'^\s*send new code\s*$', re.I))
            if r.count():
                r.first.click(); time.sleep(2); log('code refused — asked for a new code')
    try: pg.screenshot(path=os.path.join(out, 'code_step.png'), full_page=True)
    except Exception: pass
    return False


def code_page_info(pg):
    try:
        return json.dumps(pg.evaluate("""() => ({
          inputs: [...document.querySelectorAll('input')].filter(i => i.offsetHeight).map(i => [i.type, i.id, i.name, i.getAttribute('autocomplete'), i.className.toString().slice(0, 40), (i.value || '').length]),
          buttons: [...document.querySelectorAll('button')].filter(b => b.offsetHeight).map(b => [(b.innerText || '').trim().slice(0, 20), b.disabled, b.className.toString().slice(0, 50)]),
          text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 300) })"""))[:1500]
    except Exception as e:
        return f'unreadable ({type(e).__name__})'


def captcha_up(page):
    for fr in page.frames:
        if re.search(r'hcaptcha|recaptcha|captcha', fr.url or '', re.I) and re.search(r'challenge|bframe|frame=challenge', fr.url or '', re.I):
            try:
                el = fr.frame_element(); box = el.bounding_box()
                if box and box['width'] > 50 and box['height'] > 50 and el.is_visible():
                    return True
            except Exception:
                pass
    return False


WAIT_CAPTCHA = 0.0                                             # --wait-captcha minutes
CONSENT_OK = ''                                                # --consent-ok <text Joey approved>
COVER = None                                                   # --cover <pdf>, or the --folder's *Cover_Letter*.pdf


def hold_for_captcha(page, out, where, log):
    """A visible CAPTCHA challenge → park it for Joey (human_check: push + open list) and wait up to WAIT_CAPTCHA minutes
    for it to go away. Never answered by the runner. True = no challenge (any more)."""
    import human_check
    if not captcha_up(page):
        return True
    log(f'CAPTCHA challenge at {where} → Joey (never answered by the runner)')
    human_check.park(out, 'oracle', page.url, [{'question': f'Oracle CAPTCHA at {where}'}], notify=True)
    end = time.time() + WAIT_CAPTCHA * 60
    while time.time() < end and captcha_up(page):
        time.sleep(5)
    if captcha_up(page):
        return False
    human_check.resolve(out, 'solved by Joey')
    log('CAPTCHA gone (solved in the tab) — continuing'); time.sleep(4)
    return True


def email_value_ok(value, email):
    """The e-mail step's box before Next: True = holds our address, False = empty or something else (retype it)."""
    return N(value or '').lower() == N(email or '').lower() and bool(N(email or ''))


# The e-mail step's own Next is the pagination button; the legal-disclaimer dialog has a hidden footer button also labelled
# "Next" that comes first in the DOM — `.first` of all buttons waited 30 s on it (an employer fa-ewgu 11-05, JSA-220).
NEXT_CSS = ('.apply-flow-pagination button:visible, button.apply-flow-pagination__button:visible',
            'button:visible:not(.app-dialog__footer-button)')


def next_button(page):
    for css in NEXT_CSS:
        loc = page.locator(css).filter(has_text=re.compile(r'^\s*next\s*$', re.I))
        if loc.count():
            return loc.first
    return page.locator('button:visible').filter(has_text=re.compile(r'^\s*next\s*$', re.I)).first


def run(page, posting, resume, log, out, answers_override=None):
    ox = Oracle(page, log)
    res = {'status': 'blocked', 'problems': [], 'sections': [], 'unknown': [], 'account': None}
    url = apply_url(posting)
    global TENANT
    TENANT = tenant_id(url or posting)
    res['job_id'] = (parse_posting(posting) or {}).get('job', '')
    if not url:
        res['problems'].append(f'not an Oracle posting: {posting}'); return res
    if classify(page.url, page.inner_text('body') if page.url.startswith('http') else '') == 'form':
        log(f'attached tab is already in the apply flow: {page.url[:100]}')
        return sections_loop(ox, page, res, resume, log, out, answers_override)
    since = datetime.now(timezone.utc)
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    for _ in range(20):                                        # the SPA renders after load
        time.sleep(1.5)
        k = classify(page.url, page.inner_text('body'))
        if k == 'email' and not page.locator('input[type=email]').count():   # the tenant remembered "SMS" and shows the phone box
            sw = page.get_by_text(re.compile(r'communicate by e-?mail instead', re.I))   # (GuideWell 11-03) → switch back to e-mail
            if sw.count():
                sw.first.click(); time.sleep(1.5); log('switched the e-mail step from phone back to e-mail')
        if k in ('email', 'form', 'closed', 'applied', 'code') and (k != 'email' or page.locator('input[type=email]').count()):
            break
    log(f'apply page: {k} {page.url[:110]}')
    if k in ('closed', 'applied'):
        res['status'] = k; res['problems'].append('posting closed' if k == 'closed' else 'this e-mail already applied to the job'); return res
    if k == 'email':
        em = page.locator('input[type=email]').first
        em.click(); em.fill(''); em.press_sequentially(EMAIL, delay=20)
        time.sleep(3)                                          # the legal-disclaimer box renders after the e-mail input
        boxes = page.evaluate("""() => [...document.querySelectorAll('input[type=checkbox]')].filter(c => { const l = c.closest('.input-row') || c.parentElement; return l && (l.offsetWidth || l.offsetHeight); })
            .map(c => { const l = (c.id && document.querySelector('label[for="' + CSS.escape(c.id) + '"]')) || c.closest('label') || c.closest('.input-row');
                        return { id: c.id, checked: c.checked, text: (l ? l.innerText : '').replace(/\\s+/g, ' ').trim() }; })""")
        for b in boxes:                                        # the tenant's legal disclaimer box (some tenants only)
            res['consent_text'] = b['text'][:1500]
            approved = consent_approved(b['text'], CONSENT_OK, PROFILE_CONSENTS)
            terms_text = None
            if TERMS_RE.search(b['text']) and page.locator('#legal-disclaimer-link').count():
                page.locator('#legal-disclaimer-link').first.click(); time.sleep(1.5)   # the linked terms open in a dialog
                terms_text = page.evaluate("() => [...document.querySelectorAll('[role=dialog], .app-dialog')].filter(e => e.offsetHeight).map(e => e.innerText).join(' ').replace(/\\s+/g, ' ').trim()")
                res['terms_text'] = (terms_text or '')[:3000]
                page.keyboard.press('Escape'); time.sleep(0.8)
                if page.evaluate("() => [...document.querySelectorAll('[role=dialog], .app-dialog')].some(e => e.offsetHeight)"):
                    close = page.locator('[role=dialog] button, .app-dialog button').filter(has_text=re.compile(r'^\s*(close|cancel|×)\s*$', re.I))
                    if close.count():
                        close.first.click(); time.sleep(0.8)
            verdict = email_consent(b['text'], terms_text)
            if verdict == 'ask' and not approved:
                res['status'] = 'consent'
                res['problems'].append(f'e-mail step: the box goes beyond the application — Joey approves it once (--consent-ok): "{b["text"][:400]}"')
                log(f'consent at the e-mail step — NOT ticked, stop for Joey: {b["text"][:200]}')
                return res
            if not b['checked']:
                box = page.locator(f'label[for="{b["id"]}"] .apply-flow-input-checkbox__button' if b['id'] else '.apply-flow-input-checkbox__button')
                (box if box.count() else page.locator(f'label[for="{b["id"]}"]')).first.click()   # the box, not its text: the text holds the terms link
                time.sleep(0.5)
                if not page.evaluate("(id) => { const c = id && document.getElementById(id); return !!(c && c.checked); }", b['id']):
                    res['status'] = 'blocked'; res['problems'].append('e-mail step: the consent box did not tick'); return res
            log(f'e-mail step box ticked ({"privacy notice" if verdict == "tick" else "approved by Joey"}): {b["text"][:120]}')
        since = datetime.now(timezone.utc) - timedelta(seconds=60)   # the code mail's Date can be a second or two before our clock (an employer 11-03)
        for attempt in range(2):
            if email_value_ok(page.locator('input[type=email]').first.input_value(), EMAIL) is False:   # the SPA re-rendered and
                em = page.locator('input[type=email]').first                                           # emptied the box (an employer 11-05, JSA-220)
                em.click(); em.fill(''); em.press_sequentially(EMAIL, delay=20); em.press('Tab'); time.sleep(1.0)
                log('e-mail box was empty before Next — typed it again')
            next_button(page).click(timeout=15000)
            for _ in range(20):
                time.sleep(1.5)
                k = classify(page.url, page.inner_text('body'))
                if k != 'email' or captcha_up(page):
                    break
            if k != 'email' or captcha_up(page) or not page.locator('input[type=email]').count():
                break
            log(f'still on the e-mail step after Next (attempt {attempt + 1})')
        log(f'after the e-mail step: {k} {page.url[:110]}')
    if captcha_up(page):
        if not hold_for_captcha(page, out, 'the e-mail step', log):
            res['status'] = 'captcha'; res['problems'].append('a CAPTCHA at the e-mail step was not solved in time (never answered by the runner)')
            return res
        for _ in range(20):
            time.sleep(1.5)
            k = classify(page.url, page.inner_text('body'))
            if k != 'email':
                break
    if k == 'limited':
        m = re.search(r'try again in (\d+) minutes?', N(page.inner_text('body')), re.I)
        res['status'] = 'limited'; res['problems'].append('too many attempts for this e-mail on this tenant — try again in '
                                                            + (m.group(1) + ' minutes' if m else 'a while') + ' (nothing filled)')
        return res
    if k == 'code':
        res['account'] = 'existing candidate profile on this tenant: one-time code by e-mail'
        if not enter_code(ox, out, log, since):
            res['status'] = 'code'; res['problems'].append('verification code step not passed (code not found or rejected)'); return res
        k = classify(page.url, page.inner_text('body'))
    else:
        res['account'] = res['account'] or 'no account: e-mail only (new candidate on this tenant)'
    if k in ('applied', 'closed'):
        res['status'] = k; res['problems'].append(k); return res
    if k != 'form':
        res['problems'].append(f'unexpected page after the e-mail step: {k} {page.url[:120]}'); return res
    return sections_loop(ox, page, res, resume, log, out, answers_override)


SUBMIT_REFUSED = re.compile(r'you have \d+ issues? that need(s)? to be fixed before you can submit|need to add or modify some info before submitting|'
                            r'fields to fix: ?\d+', re.I)


REFUSAL_JS = r"""() => { const t = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  const out = [];
  document.querySelectorAll('.input-row--invalid').forEach(r => { out.push('field: ' + t(r).slice(0, 140)); });
  document.querySelectorAll('.apply-flow-profile-item-tile').forEach(x => { if (/fields to fix/i.test(t(x))) out.push('card: ' + t(x).slice(0, 140)); });
  document.querySelectorAll('.beautiful-timeline-item').forEach(x => { if (x.querySelector('.beautiful-timeline-item--invalid-block')) out.push('timeline card: ' + t(x).slice(0, 140)); });
  document.querySelectorAll('[role=alert], .notifications, .cx-notification, .toast, .apply-flow-errors').forEach(x => { if (t(x)) out.push('message: ' + t(x).slice(0, 200)); });
  return [...new Set(out)]; }"""


def refusal_issues(page):
    """Everything the page marks after Oracle refused Submit: invalid rows, cards with "Fields to fix", timeline cards
    with the red "!", alert / toast texts — so a refusal says which item it was (the tab closes after the run)."""
    try:
        return page.evaluate(REFUSAL_JS)
    except Exception as e:
        return [f'could not read the page ({type(e).__name__})']


def submit_refused(text):
    """Pure (tested). Oracle's own "not submitted" signals after Submit (an employer 11-04, JSA-147): the toast "You have 2 issues
    that need to be fixed before you can submit your application", "You need to add or modify some info before submitting
    your job application", a card's "Fields to fix: 2". → the matching sentence, or ''."""
    m = SUBMIT_REFUSED.search(N(text))
    return m.group(0) if m else ''


def profile_lists(text, job_id, title=None):
    """Pure (tested). My Profile → Active job applications shows this job: its requisition number as a whole word
    ("Ricoh Careers 8491") or its title, on a line block that also says "Applied on <date>"."""
    t = N(text)
    if not re.search(r'\bapplied on \d{1,2}/\d{1,2}/\d{2,4}\b', t, re.I):
        return False
    if job_id and re.search(r'(?<!\d)' + re.escape(str(job_id)) + r'(?!\d)', t):
        return True
    return bool(title) and N(title).lower() in t.lower()


def page_job_id(url, res):
    return res.get('job_id') or ''


def submit_final(ox, page, res, btn, n, log, out):
    """Press the final button (JSA-147) and confirm: a thank-you / applied page, else the receipt e-mail (read-only)."""
    import gmail_code
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    page.locator('.apply-flow-pagination button').filter(has_text=re.compile('^\\s*' + re.escape(btn) + '\\s*$', re.I)).first.click()
    log(f'section {n}: "{btn}" clicked (submit)')
    for _ in range(15):
        time.sleep(2)
        if captcha_up(page) and not hold_for_captcha(page, out, 'the submit', log):
            res['status'] = 'captcha'; res['problems'].append('CAPTCHA at submit not solved in time'); return res
        k = classify(page.url, page.inner_text('body'))
        if k == 'done' and '/my-profile' in page.url and not profile_lists(page.inner_text('body'), page_job_id(page.url, res), (JOB or {}).get('title')):
            k = 'unknown'                                     # My Profile lists other applications, not this one (yet)
        if k in ('done', 'applied'):
            res['status'], res['confirmed_by'] = 'submitted', 'page'
            try: page.screenshot(path=os.path.join(out, 'submitted_confirmation.png'), full_page=True)
            except Exception: pass
            return res
        refused = submit_refused(page.inner_text('body')[:30000])
        if refused and not res.get('cards_fixed') and fix_tiles(page, visible_only=False).count():
            res['cards_fixed'] = True                         # one retry: fill the imported cards, press Submit again (an employer 11-04)
            fx = fix_education_cards(page, log)
            if fx:
                res['status'] = 'needs-user'; res['problems'] += fx; return res
            page.locator('.apply-flow-pagination button').filter(has_text=re.compile('^\\s*' + re.escape(btn) + '\\s*$', re.I)).first.click()
            log(f'section {n}: cards fixed — "{btn}" clicked again'); continue
        st = ox.state()
        if refused or st.get('errors'):
            res['status'] = 'blocked'
            issues = refusal_issues(page)                     # what the page marks, read before the tab closes (an employer 11-05, JSA-226)
            try: page.screenshot(path=os.path.join(out, 'submit_refused.png'), full_page=True)
            except Exception: pass
            res['refusal_issues'] = issues
            res['problems'].append('submit refused by Oracle (nothing sent): ' + (refused or '') +
                                   (' | ' + ' | '.join(st['errors'][:4]) if st.get('errors') else '') +
                                   (' | marked on the page: ' + ' | '.join(issues[:6]) if issues else '') + ' (screenshot submit_refused.png)')
            log('submit refused — page issues: ' + ('; '.join(issues[:6]) or 'none found'))
            return res
    company = (JOB or {}).get('company') or ''
    log('no thank-you page — waiting up to 180 s for the receipt e-mail (Gmail read-only)')
    subj = gmail_code.wait_for_mail(since, company, timeout=180) if company else None
    if subj:
        res['status'], res['confirmed_by'] = 'submitted', 'email'; log(f'company e-mail: {subj[:100]}'); return res
    res['status'] = 'unconfirmed'; res['problems'].append('clicked Submit but no confirmation page and no company e-mail — check Gmail')
    return res


def sections_loop(ox, page, res, resume, log, out, overrides):
    for _ in range(10):
        time.sleep(2)
        m = re.search(r'/apply/section/(\d+)', page.url)
        n = int(m.group(1)) if m else len(res['sections']) + 1
        rows, problems, unknown, st = fill_section(ox, overrides or {}, resume, log)
        if fix_tiles(page).count():                           # imported cards with "Fields to fix" on this section: the dry
            fx = fix_education_cards(page, log)               # run fixes them too (an employer 11-05: only the Submit found them, JSA-226)
            rows.append({'key': 'education-cards', 'label': 'Imported education cards', 'kind': 'cards', 'required': True,
                         'want': 'fixed', 'page': 'fixed' if not fx else '; '.join(fx)[:120], 'ok': not fx})
            problems += fx
        try:
            page.screenshot(path=os.path.join(out, f'section_{n}.png'), full_page=True)
        except Exception:
            pass
        fwd = [b for b in st['buttons'] if not re.search(r'^(back|previous|cancel)$', N(b['text']), re.I)]
        btn = fwd[-1]['text'] if fwd else None
        res['sections'].append({'section': n, 'steps': st['steps'][:200], 'blocks': sorted({r.get('block') or 'file-upload' for r in rows}),
                                'fields': rows, 'problems': problems, 'unknown': unknown, 'button': btn, 'errors': st['errors']})
        if st.get('esign'):
            res['esign_text'] = st['esign'][:1500]
        if st.get('agreements'):
            res['agreements_text'] = st['agreements'][:800]
        for r in rows:
            log(f"  [{n}] {'ok ' if r.get('ok') else 'BAD'} {str(r['label'])[:52]:52s} → {str(r.get('page'))[:40]}" + (f"  ({r['error']})" if r.get('error') else ''))
        if unknown:
            res['unknown'] += [f'section {n}: {u}' for u in unknown]
        if problems or unknown:
            res['status'] = 'needs-user'; res['problems'] += [f'section {n}: {p}' for p in problems]
            return res
        if not btn:
            res['problems'].append(f'section {n}: no forward button'); return res
        if NO_ADVANCE or is_final(btn):
            res['status'] = 'dry-run'
            pre = submit_refused(page.inner_text('body')[:30000])   # an imported card already says "Fields to fix" (an employer 11-04)
            if not pre and fix_tiles(page, visible_only=False).count():   # one on an earlier section, hidden now (an employer 11-05)
                pre = f'{fix_tiles(page, visible_only=False).count()} imported card(s) on an earlier section still say "Fields to fix"'
            if pre and re.search(r'fields to fix', pre, re.I):
                fx = fix_education_cards(page, log)
                pre = '; '.join(fx) if fx else submit_refused(page.inner_text('body')[:30000])
            if pre:
                res['status'] = 'needs-user'; res['problems'].append(f'section {n}: {pre} — not submitted'); return res
            if not SUBMIT or NO_ADVANCE or not is_final(btn):
                log(f'section {n}: every field filled and read back — stop BEFORE "{btn}" (dry-run, not submitted)')
                return res
            if RUN is not None and not RUN.gate_inside(res):  # JSA-186/187: canon + approval, right before Submit
                log(f'section {n}: common gate — NOT submitted'); return res
            if RUN is not None:
                RUN.mark('submit')
            return submit_final(ox, page, res, btn, n, log, out)
        log(f'section {n} → "{btn}"')
        page.locator('.apply-flow-pagination button').filter(has_text=re.compile('^\\s*' + re.escape(btn) + '\\s*$', re.I)).first.click()
        for _ in range(15):
            time.sleep(2)
            m2 = re.search(r'/apply/section/(\d+)', page.url)
            if m2 and int(m2.group(1)) != n:
                break
        else:
            st3 = ox.state()
            res['status'] = 'needs-user'; res['problems'].append(f'section {n} did not advance: ' + ' | '.join(st3['errors'][:5]))
            return res
        if classify(page.url, page.inner_text('body')) == 'done':
            res['problems'].append('a thank-you page appeared — the application may have been submitted'); return res
    res['problems'].append('more than 10 sections'); return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url'); ap.add_argument('--job'); ap.add_argument('--resume'); ap.add_argument('--track'); ap.add_argument('--out')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222'); ap.add_argument('--wait-code', type=float, default=3)
    ap.add_argument('--attach', help='reuse the open tab whose URL contains this text'); ap.add_argument('--keep-tab', action='store_true')
    ap.add_argument('--no-advance', action='store_true', help='fill and read back the current section, press nothing')
    ap.add_argument('--answers', help='JSON file {label: {"status": "ok", "value": …}} for answers Joey gave')
    ap.add_argument('--wait-captcha', type=float, default=0, help='minutes to wait for Joey to clear a CAPTCHA in the tab')
    ap.add_argument('--cover', help='cover letter PDF for a cover-letter slot'); ap.add_argument('--folder', help='application folder (its *Cover_Letter*.pdf)')
    ap.add_argument('--consent-ok', default='', help='text of an e-mail-step consent Joey approved (ticked only when the box contains it)')
    ap.add_argument('--submit', action='store_true', help='press the final button when every gate passes (needs --folder)')
    a = ap.parse_args()
    import run_form as RF                                       # shared gates and tab cleanup (JSA-145 / 147)
    folder = jpaths.folder(a.folder) if a.folder else None   # as typed, else under the data home (ADR-0008)
    if folder and os.path.exists(os.path.join(folder, 'job.json')):
        fj = json.load(open(os.path.join(folder, 'job.json')))
        a.job = a.job or fj.get('id'); a.url = a.url or fj.get('url'); a.track = a.track or fj.get('track')
        pdfs = sorted(x for x in os.listdir(folder) if x.lower().endswith('.pdf') and 'resume' in x.lower())
        a.resume = a.resume or (os.path.join(folder, pdfs[0]) if pdfs else None); a.out = a.out or folder
        if RF.already_submitted(folder):
            print(f'{os.path.basename(folder)}: already submitted — nothing to do'); print('STATUS already-submitted'); return
    if a.submit and not (folder and os.path.exists(os.path.join(folder, 'job.json'))):
        sys.exit('--submit needs --folder with job.json (approval, tailored resume and the tracker row come from it)')
    job = {}
    if a.job:
        for line in open(jpaths.data('store', 'jobs.jsonl'), encoding='utf-8'):
            r = json.loads(line)
            if r.get('id') == a.job:
                job = r; break
    posting = a.url or job.get('ats_url') or job.get('url')
    p = parse_posting(posting)
    if not p:
        sys.exit(f'not an Oracle posting: {posting}')
    track = a.track or TRACKS.get(job.get('track'), 'Data_Analyst')
    resume = a.resume or jpaths.resume('2026-10', f'Alex_Rivera_Resume_{track}_A-Classic.pdf')
    out = os.path.abspath(a.out or os.path.join(DATA, 'dryrun', 'oracle', p['host'].split('.')[0] + '_' + p['job']))
    os.makedirs(out, exist_ok=True)
    over = json.load(open(a.answers)) if a.answers else {}
    global NO_ADVANCE, WAIT_CODE, WAIT_CAPTCHA, CONSENT_OK, COVER, JOB, SUBMIT, RUN
    JOB = job
    if folder and os.path.exists(os.path.join(folder, 'job.json')) and fj.get('company') and not JOB.get('company'):
        JOB = dict(JOB, company=fj['company'])                 # referral questions (JSA-195) + the receipt e-mail
    SUBMIT = bool(a.submit and RF.approved_for(folder))
    if a.submit and not SUBMIT:
        print('NOT submitting: batch not approved (data/runner/approved_batches.json) — dry-run only')
    NO_ADVANCE, WAIT_CODE, WAIT_CAPTCHA, CONSENT_OK = a.no_advance, a.wait_code, a.wait_captcha, a.consent_ok
    COVER = a.cover or find_cover(a.folder)
    t0 = time.time()
    logf = open(os.path.join(out, 'run_log.md'), 'a', encoding='utf-8')
    def log(msg): logf.write(f'- {now()} {msg}\n'); logf.flush(); print(msg)
    log(f'start oracle {"submit" if SUBMIT else "dry-run"} {posting} (resume {os.path.basename(resume)})')
    RUN = R = RC.Run('oracle', posting, folder, out, submit=bool(a.submit), log=log, label='Oracle', data_dir=DATA)
    if not R.opening(resume):                                    # submit + materials problem: stopped before filling
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp(a.cdp).contexts[0]
        page = next((pg for pg in ctx.pages if a.attach and a.attach in pg.url), None) or ctx.new_page()
        R.mark('page')
        try:
            r = run(page, posting, resume if os.path.exists(resume) else None, log, out, over)
        except Exception as e:
            r = {'status': 'blocked', 'problems': [f'runner error {type(e).__name__}: {str(e)[:200]}'], 'sections': [], 'unknown': []}
        R.report(r)                                              # dry run / stopped early: the common checks, for the record
        fields = [f for s in r['sections'] for f in s['fields']]
        n, ok = len(fields), len([f for f in fields if f.get('ok')])
        json.dump({'at': now(), 'posting': posting, 'job': a.job, 'resume': os.path.basename(resume), **r, 'readback': f'{ok}/{n}'},
                  open(os.path.join(out, 'form_check.json'), 'w'), indent=1, ensure_ascii=False)
        log(('problems: ' + ' | '.join(r['problems'] + r.get('unknown', []))) if (r['problems'] or r.get('unknown'))
            else ('CONFIRMED by ' + r.get('confirmed_by', '') if r['status'] == 'submitted' else 'all sections read back — dry-run, NOT submitted'))
        R.finish(r, ctx=ctx, page=page, confirmed_by=r.get('confirmed_by'), keep_tab=a.keep_tab)

if __name__ == '__main__':
    main()
