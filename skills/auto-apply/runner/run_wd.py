#!/usr/bin/env python3
"""Workday applications (Joey 2026-10-28). Same rules as run.py: dry-run by default; --submit only when every gate passes.

  python3 run_wd.py "<app folder>" --attach cx=<marker> [--submit]

Flow: job page (forced to /en-US/) → Apply → "Autofill with Resume" → sign-in / create-account wall = JOEY (Claude never types
passwords or creates accounts): the runner queues it and waits in the same tab until he is signed in → then page by page:
  read every field (wd_page.js) → answer it (repeat blocks Work Experience / Education from wd_profile.json; everything else with
  plan_build.build: answers.json → open_answers.md → answer_rules.js) → fill with real clicks/keys → re-read each field (our check)
  → wrong fields go up the ladder (DeepSeek, max 3 tries; then handoff.json for Claude in Chrome in the same tab)
  → dropdown/prompt whose planned answer is not offered: collect the COMPLETE option list, DeepSeek picks one exact option
    from it (or NONE: optional → empty, required → Joey); the script clicks it (no DeepSeek click loop for pickers)
  → required field with no answer: DeepSeek triage first (maps it to a SAVED fact → ds_answers.json, audit ds_used.json);
    only UNKNOWN reaches Joey: wd_needs.json + queue, status.txt = needs-user, the runner WAITS (polls answers.json every 3 s,
    --wait-min 20) and continues on the same page when every need has an answer; timeout → exit (rerun with --attach)
  → status.txt in the folder: running | signin | needs-user | handoff | review | done | captcha (+ time) — Claude waits on it
  → "Save and Continue"; Workday's own error messages are a failed check too.
Review page: every answer we set must appear on the review page; then the gate (batch approved, no needs, no failed field,
no CAPTCHA) → Submit → confirmation text/screenshot → application_record.md.
Writes <app>/wd_log.json (every page: fields, answers, sources, check result) + run_log.md + results.jsonl/queue.md like run.py.
"""
import argparse, json, os, re, sys, time
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
import canon
import ladder
import plan_build as PB
import materials_gate, decide, wd_signin, human_check
from run import approved_for, queue, now, DATA, CAPTCHA_SEL

PAGE_JS = open(os.path.join(HERE, 'wd_page.js'), encoding='utf-8').read()
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077: personal facts in config/)
PROFILE = json.load(open(jsa_profile.data_file('wd_profile.json', 'JSA_WD_PROFILE'), encoding='utf-8'))   # Workday blocks (work / education / languages)
DONE_RE = re.compile(r'(application (was )?submitted|thank you for (applying|your application)|successfully submitted|'
                     r'we have received your application|congratulations)', re.I)
N = lambda s: re.sub(r'\s+', ' ', str(s or '')).strip()
PREF_STOP = {'', 'other'}


DEGREE_SPECIAL = re.compile(r'\blaws?\b|\bLL\.?M\b|\bJ\.?D\b|executive|\bE\.?M\.?B\.?A\b|fine arts|\bM\.?F\.?A\b|\beducation\b|\bM\.?Ed\b|'
                            r'social work|\bM\.?S\.?W\b|divinity|theolog|nursing|\bM\.?S\.?N\b|public (health|admin|policy)|\bM\.?P\.?[HAP]\b|'
                            r'architecture|\bmusic\b|pharmac|physician|occupational|physical therapy|\bengineering\b|\bM\.?Eng\b|technology', re.I)


def degree_special(o):
    """A master's that is not his (M.S. Applied Data Science): law, executive, education, engineering, … (NJM "MS-Law",
    a Workday employer "Executive Master", 2026-11-01). "Science or Engineering" style combined options stay allowed."""
    combined = re.search(r'\bscience or\b|\bor science\b', o, re.I)        # "Master of Science or Engineering" (KLA-style combined option)
    return bool(DEGREE_SPECIAL.search(o)) and not combined or bool(re.search(r'\blaws?\b|executive', o, re.I))


def degree_rank(o):
    """Master options, best first: "Master of Science" / "M.S." → a plain "Master's (Degree)" / "Masters" → any other."""
    t = o.strip()
    if re.search(r'\bor\b', t, re.I): return 2                               # combined options rank last
    if re.search(r'^master\S* (of|in) science\b|^M\.?S\.?c?\.?$|^M\.?S\.? degree$', t, re.I): return 0
    if re.search(r"^masters?'?s?( degree)?( \(.*\))?$|^master'?s?'? degree$|^graduate degree", t, re.I): return 1
    return 2


def master_options(opts):
    """Pure (tested): his master's options from a Degree list, best first (degree_rank); specialty masters and MBA-only dropped."""
    is_mba_only = lambda o: bool(re.search(r'\bMBA\b|business admin', o, re.I)) and not re.search(r'science', o, re.I)
    rx = r'master|^m\.?s\.?c?$|^m\.?a\.?$|^ms\b|^msc\b'
    out = [o for o in (opts or []) if re.search(rx, o.strip(), re.I) and not is_mba_only(o) and not degree_special(o)]
    return sorted(out, key=degree_rank)


def in_signin_step(page):
    """The wizard's active step is "Create Account/Sign In" (Workday puts sign-in inside the progress bar on some tenants)."""
    try:
        loc = page.locator('[data-automation-id="progressBarActiveStep"]')
        return bool(loc.count()) and bool(re.search(r'sign ?in|create account', loc.first.inner_text(timeout=2000), re.I))
    except Exception:
        return False


def salary_number(label):
    """Pure (tested). The number for a salary question when the box accepts digits only (Joey 2026-11-01:
    hourly 25 / annual 52000; current salary 0 — full-time student). None = not a salary question."""
    l = str(label or '')
    if not re.search(r'salary|compensation|\bpay\b|\bwage|\brate of pay|hourly rate', l, re.I):
        return None
    if re.search(r'\b(current|present|most recent|previous|last)\b[^?]{0,30}(salary|compensation|pay|wage)', l, re.I):
        return '0'
    if re.search(r'hour|hourly|/\s*hr\b|per hr', l, re.I):
        return '25'
    return '52000'


BACHELOR_SPECIAL = re.compile(r'fine arts|\bB\.?F\.?A\b|\bmusic\b|\bB\.?Mus|architecture|\bB\.?Arch|nursing|\bB\.?S\.?N\b|education|\bB\.?Ed\b|'
                              r'engineering|\bB\.?E(ng)?\b|social work|\bB\.?S\.?W\b|business admin|\bB\.?B\.?A\b|pharmac|technology|law\b|\bLL\.?B\b|divinity|theolog|applied science', re.I)


def bachelor_options(opts):
    """Pure (tested): his bachelor's (B.A. Economics, UIUC) options from a Degree list, best first: "Bachelor of Arts" /
    "B.A." → a plain "Bachelor's (Degree)" / "Bachelors" → a combined option naming Arts; a Bachelor of Science alone is never his. Specialty
    bachelor's (fine arts, music, nursing, engineering, BBA, …) dropped (a Workday employer "Bachelor of Fine Arts" 2026-11-01)."""
    rx = r'bachelor|^b\.?s\.?$|^b\.?a\.?$|baccalaureate'
    out = [o for o in (opts or []) if re.search(rx, o.strip(), re.I) and not BACHELOR_SPECIAL.search(o)]
    def rank(o):
        t = o.strip()
        if re.search(r'\bor\b', t, re.I): return 2
        if re.search(r'^bachelor\S* (of|in) arts\b|^B\.?A\.?$|^B\.?A\.? degree$', t, re.I): return 0
        if re.search(r"^bachelors?'?s?( degree)?( \(.*\))?$|^bachelor'?s?'? degree$|^baccalaureate", t, re.I): return 1
        return 2
    return sorted([o for o in out if rank(o) < 2 or re.search(r'\barts\b', o, re.I)], key=rank)   # never a B.S. for his B.A.


def tab_should_close(status):
    """Pure (tested). Joey 2026-11-01 (memory): close the tab when a run ends, except while someone acts on it right away —
    a question for Joey (needs-user), Claude's Review check (blocked / dry-run → review), a CAPTCHA. A stopped run is
    retried fresh later anyway (the Workday session expires in ~20 min)."""
    import tab_policy                                   # Joey 2026-11-05: dry-run / stopped tabs close too; only a CAPTCHA stays
    return not tab_policy.keep_open(status)


def has_education_section(answered_keys, review_text):
    """Pure (tested). Does this tenant have an education section? Then every school must appear on Review.
    Yes when an answered key is an education block ("Education 1||School or University") or the Review text shows an
    education heading / "School or University" field. Some tenants (2026-11-01) have none: only work or languages."""
    if any(re.match(r'(Education|Academic Experience) \d', str(k)) for k in (answered_keys or [])):
        return True
    return bool(re.search(r'\beducation\b|academic experience|school or university', review_text or '', re.I))


def assign_languages(blocks, entries):
    """Pure (tested). blocks = [(section, language value on the page)], entries = profile languages ({'match': regex}).
    → {section: entry index or None}. Named blocks take the entry their language matches (each once); then empty blocks
    (just added with "Add") take the unused entries in profile order; a block with another language, a duplicate,
    or an empty block with nothing left → None (deleted). Voya / an employer / a Workday employer 2026-11-02: only English was parsed."""
    out, used = {}, set()
    for sec, val in blocks:
        if str(val or '').strip():
            i = next((i for i, e in enumerate(entries) if i not in used and re.search(e['match'], str(val), re.I)), None)
            out[sec] = i
            if i is not None: used.add(i)
    for sec, val in blocks:
        if not str(val or '').strip():
            i = next((i for i in range(len(entries)) if i not in used), None)
            out[sec] = i
            if i is not None: used.add(i)
    return out


def language_option(match, options):
    """Pure (tested). The tenant's option for a profile language: Mandarin before plain Chinese before other Chinese
    options; never Cantonese / Taiwanese / sign language; English: plain English first."""
    opts = [o for o in (options or []) if str(o).strip() and not re.search(r'^select', str(o), re.I)]
    hits = [o for o in opts if re.search(match, o, re.I) and not re.search(r'cantonese|hakka|taiwanese|wu\b|min\b|sign', o, re.I)]
    if not hits: return None
    rank = lambda o: (0 if re.search(r'mandarin', o, re.I) else 1 if re.fullmatch(r'\s*(chinese|english)\s*', o, re.I) else 2, len(o))
    return sorted(hits, key=rank)[0]


# a source option that claims a person, a job, a contact or an event he never had (Joey 2026-11-01: 「跳过声称有人推荐的选项」 —
# 16 submitted applications had picked e.g. "Current Temporary Employee", "Employee Referral", "Recruiter", "Arrowstreet Contacted Me")
SOURCE_CLAIM = re.compile(r'alumni|referr|employee|(?<!zip)(?<!zip )recruit|friend|family|colleague|career fair|job fair|campus|event|conference|'
                          r'university|college|school|professor|agency|search firm|staffing|direct contact|contacted|headhunt|sourcer|'
                          r'contingent|contractor|temporary|\btemp\b|in-person|program\b|workshop|info(rmation)? session|alma mater', re.I)


def source_option_ok(option):
    """Pure (tested). May the agent pick this "How did you hear about us" option for him?"""
    return bool(str(option or '').strip()) and not SOURCE_CLAIM.search(str(option))


SOURCE_NEUTRAL = re.compile(r'website|career site|job board|online|internet|social|linkedin|indeed|glassdoor|search engine|google|^other\b', re.I)
PLACEHOLDER_RX = re.compile(r'^(select one|select|choose one|--+|选择一个|请选择|請選擇|選擇一個|sélectionnez|seleccione)\.?$', re.I)


def source_pick(options):
    """Pure (tested, JSA-067). The truthful "How did you hear about us" option from a complete list, or None:
    placeholders and claims (source_option_ok) are dropped, neutral channels (website / job board / social / Other) first."""
    ok = [str(o).strip() for o in (options or []) if str(o).strip() and not PLACEHOLDER_RX.match(str(o).strip()) and source_option_ok(o)]
    ok.sort(key=lambda o: 0 if SOURCE_NEUTRAL.search(o) else 1)
    return ok[0] if ok else None


def real_options(options):
    """Pure (tested). Options minus placeholders ("Select One", "选择一个") — an empty result = the tenant's list is empty."""
    return [o for o in (options or []) if str(o).strip() and not PLACEHOLDER_RX.match(str(o).strip())]


ERROR_PAGE_RX = re.compile(r'something went wrong|session (has )?(expired|timed out)|an error (has )?occurred|page (is )?(not available|unavailable)', re.I)


def zero_field_experience(sections, upload_ok, body_text):
    """Pure (tested, JSA-065). An experience page planned 0 fields → 'error' (Workday error page: an old draft / expired
    session), 'resume-only' (the tenant shows only the résumé upload: no work / education / language section, upload done —
    VSP 2026-11-02, nothing to check) or 'empty' (sections exist but nothing rendered → stop, never advance unchecked)."""
    if ERROR_PAGE_RX.search(body_text or ''): return 'error'
    if upload_ok and not any(re.search(r'\bwork|employ|experience|educat|academic|school|language', s or '', re.I)   # \b: "Social Network URLs" is not work
                             and not re.search(r'resume|cv\b|curriculum|attachment', s or '', re.I) for s in (sections or [])):
        return 'resume-only'
    return 'empty'


def file_kind(label):
    """Pure (tested, JSA-068). A Workday file field's label → 'cover' | 'reference' | 'transcript' | 'resume'
    (the default: "Resume/CV", "Upload a file", "Attachments")."""
    t = str(label or '')
    if re.search(r'cover ?letter|motivation(al)? letter|letter of (interest|motivation)', t, re.I): return 'cover'
    if re.search(r'reference|recommendation', t, re.I): return 'reference'
    if re.search(r'transcript', t, re.I): return 'transcript'
    return 'resume'


def files_for_field(kind, field_text, resume, cover, want_cover, multiple):
    """Pure (tested, JSA-068). File names to upload into one file field (those not already shown in it):
    resume field → the résumé, plus the cover letter when the application wants one (JD / form / answers.json) and the
    input takes several files; cover field → the cover letter; reference / transcript → [] (Joey's documents)."""
    t = str(field_text or '')
    shown = [x for x in re.findall(r'[^\s/]+\.(?:pdf|docx?)\b', t, re.I) if x != cover]
    has_file = bool(shown) or (not re.findall(r'\.(?:pdf|docx?)\b', t, re.I) and bool(re.search(r'successful', t, re.I)))   # a résumé is already there (draft / autofill step): no second one
    if kind == 'cover': want = [cover]
    elif kind == 'resume': want = ([] if has_file else [resume]) + ([cover] if want_cover and multiple else [])
    else: want = []
    return [x for x in want if x and x not in t]


JOEY_STEP_RX = re.compile(r'assessment|questionnaire|\bwotc\b|tax credit|screening test|skills? test|测评|評估', re.I)


def joey_step(step):
    """Pure (tested). A wizard step that is a third-party assessment / questionnaire (Allison "Take Assessment" 2026-11-03,
    WOTC) — handed to Joey by design (type O), never clicked through."""
    return bool(JOEY_STEP_RX.search(re.sub(r'^current step \d+ of \d+\s*', '', str(step or ''), flags=re.I)))


EEO_TOPIC_RX = re.compile(r'gender|\bsex\b|\brace\b|ethnic|veteran|disabilit|hispanic|latino', re.I)
# an instruction NOT to disclose the categories, up to ")" or the end of its sentence (Central Hudson 11-05: "civic
# activities … (Exclude those which would reveal sex, race, … disability or other protected status)", JSA-206)
EEO_EXCLUDE_RX = re.compile(r"(\bexclud(e|es|ing)\b|\b(do not|don'?t|don’t)\s+(include|list|mention|disclose|provide|reveal|share)\b|"
                            r"\b(which|that) (would|might|may|could) (reveal|indicate|identify|disclose)\b|"
                            r"\bother protected (status|characteristics?|class(es)?)\b)[^)]*?(\)|[.?!;](?=\s|$)|$)", re.I)


def eeo_label(label):
    """Pure (tested). The label asks for gender / sex / race / ethnicity / Hispanic-Latino / veteran / disability — topic
    words inside a do-not-disclose instruction do not count (JSA-206)."""
    return bool(EEO_TOPIC_RX.search(EEO_EXCLUDE_RX.sub(' ', N(label))))


def eeo_left_empty(review_text, free_text_labels=()):
    """Pure (tested, JSA-206). Labels of REAL EEO questions the Review page shows as "No Response" (label line, then the
    answer line; or both on one line). A free-text box (the runner recorded it as textarea / text — first 60 characters
    match) is never an EEO question, whatever its label lists."""
    key = lambda s: N(s).rstrip('*').strip().lower()[:60]
    free = {key(x) for x in (free_text_labels or ()) if N(x)}
    lines = [N(x) for x in str(review_text or '').splitlines()]
    lines = [x for x in lines if x]
    out = []
    for i, ln in enumerate(lines):
        if ln.lower() == 'no response':
            label = lines[i - 1] if i else ''
        elif re.search(r'\sno response$', ln, re.I):
            label = ln[:-len('no response')]
        else:
            continue
        label = N(label).rstrip('*').strip()
        if label and label.lower() != 'no response' and eeo_label(label) and key(label) not in free:
            out.append(label)
    return out


COVER_ASKED_RX = re.compile(r'uploaded (both )?(my |a |your )?cover ?letter', re.I)


def block_kind_of(section):
    """Pure (tested). Workday repeat-block heading → languages / education / work / None (WD.block_kind uses the same order)."""
    section = str(section or '')
    return ('languages' if re.search(r'language', section, re.I) else 'education' if re.search(r'educat|academic', section, re.I)
            else 'work' if re.search(r'work|experience|employment', section, re.I) else None)


def pick_by_prefs(opts, prefs):
    """Deterministic pick from the COMPLETE option list along the ordered preference list.

    Joey 2026-10-28: the model must not have discretion over this order (it picked "Statistics"
    while CS/IS options were on the list). Per preference, in order: exact -> substring -> all
    tokens present ("Computer Science" also matches "Computer and Information Science", and
    "Information Systems" matches "Management Information Systems"). The first preference that
    matches anything wins, so a lower preference can never jump the queue.
    None = nothing fits -> DeepSeek picks (or the field stays empty / Joey decides).
    """
    STOPW = {'and', 'of', 'the', 'a', 'an', 'or', 'in', 'for'}
    key = lambda s: re.sub(r'\s+', ' ', str(s or '')).strip().lower().rstrip('.')
    toks = lambda s: {w for w in re.findall(r'[a-z0-9]+', s) if w not in STOPW}
    pairs = [(o, key(o)) for o in (opts or [])]
    clean = [key(p) for p in (prefs or []) if key(p) not in PREF_STOP]
    for pn in clean:
        for o, on in pairs:                                  # 1 exact
            if on == pn:
                return o
        if len(pn) < 4:
            continue
        for o, on in pairs:                                  # 2 substring
            if pn in on or (on in pn and len(toks(on)) >= 2):   # a bare "Science" is not "Data Science" (Central Hudson 2026-11-01)
                return o
        pt = toks(pn)
        if pt:
            for o, on in pairs:                              # 3 every token of the preference present
                if pt <= toks(on):
                    return o
    return None


SCROLL_FIND_JS = '''async (want) => {
  const norm = s => String(s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  document.querySelectorAll('[data-cx-opt]').forEach(x => x.removeAttribute('data-cx-opt'));
  const opts = () => [...document.querySelectorAll('[data-automation-id="promptOption"]')].filter(o => o.getClientRects().length);
  const pop = opts().filter(o => !o.closest('[data-automation-id^="formField-"]'));       // the popup list, not the field's own pills
  if (!pop.length) return { hit: false, seen: [] };
  let sc = document.querySelector('[data-automation-id="activeListContainer"]');            // Workday's virtualized list (a Workday employer: 320 items, 13 rendered)
  if (!sc || !sc.contains(pop[0])) { sc = pop[0].parentElement; while (sc && sc !== document.body && sc.scrollHeight <= sc.clientHeight + 2) sc = sc.parentElement; }
  if (sc === document.body) sc = null;
  sc && (sc.scrollTop = 0);
  const seen = new Set();
  for (let i = 0; i < 250; i++) {
    for (const x of opts().filter(o => !o.closest('[data-automation-id^="formField-"]'))) { const t = norm(x.textContent); seen.add(t);
      if (t === norm(want)) { x.setAttribute('data-cx-opt', '1'); x.scrollIntoView({ block: 'center' }); return { hit: true, seen: [] }; } }
    if (!sc) break;
    const before = sc.scrollTop; sc.scrollTop += Math.max(60, sc.clientHeight * 0.8);
    await new Promise(r => setTimeout(r, 200));
    if (sc.scrollTop === before) break;
  }
  return { hit: false, seen: [...seen].slice(0, 8), total: seen.size };
}'''


SUBMIT_RX = re.compile(r'\b(submit|send application)\b|提交|送出|递交|遞交|enviar|soumettre|absenden|invia', re.I)
REVIEW_RX = re.compile(r'^(review|审查|审阅|審查|審閱|检查|確認|revis|überprüf|examen|riepilogo)', re.I)


HUMAN_CHECK_RX = re.compile(r'verify (that )?you are (a )?human|are you (a )?(human|robot)\b(?!\s+[a-z])|not a robot|captcha|prove you.{0,20}human', re.I)


def push(title, body):
    """Phone + Mac push to Joey (scripts/daily/notify.py); never fails the run."""
    try:
        import subprocess
        root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
        subprocess.run(['/opt/homebrew/bin/python3', os.path.join(root, 'scripts', 'daily', 'notify.py'), title, body[:600]],
                       capture_output=True, timeout=40)
    except Exception:
        pass


def is_review(step):
    step = re.sub(r'^(current step \d+ of \d+|当前步骤\s*\d+\s*/\s*\d+|目前步驟\s*\d+\s*/\s*\d+)\s*', '', (step or '').strip(), flags=re.I)
    return bool(REVIEW_RX.search(step))


def is_review_page(step, fields):
    """Pure (tested, JSA-071). Review only when the progress bar's current step is Review AND the page no longer shows
    the previous step's form fields (C&S 2026-11-02: the bar said Review while Voluntary Disclosures' 5 fields were
    still on screen, and Review was "missing" the address)."""
    return is_review(step) and not [f for f in (fields or []) if f.get('type') != 'file']


def step_changed(before_step, before_keys, after_step, after_keys):
    """Pure (tested, JSA-071). Did Save and Continue take effect? The new step must be non-empty and different, and the
    page must not still show the same fields (data-cx-k keys stamped on the old page)."""
    if not after_step or after_step == before_step: return False
    return not (before_keys and set(after_keys or ()) == set(before_keys))


def en_us(url):
    return re.sub(r'(myworkday(jobs|site)\.com/)(?:[a-z]{2}-[A-Z]{2}/)?', r'\1en-US/', url, count=1)


COLLECT_JS = '''async () => {          // every option of the open (virtualized) prompt / listbox
  const norm = s => String(s || '').replace(/\\s+/g, ' ').trim();
  const opts = () => [...document.querySelectorAll('[data-automation-id="promptOption"], [role="listbox"] [role="option"]')]
      .filter(o => o.getClientRects().length && !o.closest('[data-automation-id^="formField-"]'));
  const first = opts(); if (!first.length) return [];
  let sc = document.querySelector('[data-automation-id="activeListContainer"]');
  if (!sc || !sc.contains(first[0])) { sc = first[0].parentElement; while (sc && sc !== document.body && sc.scrollHeight <= sc.clientHeight + 2) sc = sc.parentElement; }
  if (sc === document.body) sc = null;
  sc && (sc.scrollTop = 0); await new Promise(r => setTimeout(r, 150));
  const seen = new Set();
  for (let i = 0; i < 300; i++) {
    opts().forEach(o => { const t = norm(o.textContent); if (t) seen.add(t); });
    if (!sc || seen.size > 800) break;
    const before = sc.scrollTop; sc.scrollTop += Math.max(60, sc.clientHeight * 0.8);
    await new Promise(r => setTimeout(r, 150));
    if (sc.scrollTop === before) break;
  }
  return [...seen];
}'''
FINAL_STATE = {'submitted': 'done', 'already-submitted': 'done', 'dry-run': 'review', 'blocked': 'review', 'handoff': 'handoff',
               'unconfirmed': 'handoff', 'needs-user': 'needs-user', 'captcha': 'captcha', 'login-timeout': 'signin-timeout',
               'filled': 'review'}


def set_status(folder, state, note=''):
    """One line Claude can wait on with a single shell loop (handoff 2026-10-28b)."""
    try:
        with open(os.path.join(folder, 'status.txt'), 'w', encoding='utf-8') as fh:
            fh.write(f"{state} {datetime.now().strftime('%H:%M:%S')} {note}".strip() + '\n')
    except Exception: pass


def read_json(path, default):
    try: return json.load(open(path, encoding='utf-8'))
    except Exception: return default


MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}
def date_parts(t):
    """'12/01/2027' → [12, 1, 2027]; 'December 2027' → [12, 2027] (month names become numbers)."""
    t = re.sub(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?', lambda m: str(MONTHS[m.group(1).lower()]), str(t), flags=re.I)
    return [int(x) for x in re.findall(r'\d+', t)]


def date_digits(ans, has_day):
    """Digits to type into a Workday date box. Month-year box: 06/14/2027 → 062027. Box with a day and only month + year
    given (12/2027, December 2027): the first of the month (a Workday employer 2026-11-02 typed 122027 → 12/20/2027)."""
    parts = date_parts(ans)
    if len(parts) == 3: m, d, y = parts
    elif len(parts) == 2: (m, y), d = parts, 1
    else: return re.sub(r'\D', '', str(ans))
    return f'{m:02d}{d:02d}{y:04d}' if has_day else f'{m:02d}{y:04d}'


def ov_lookup(ov, label, key=None):
    """answers.json-style dict → (True, value) when a key equals the field key / label or matches the label as a regex."""
    for k, v in ov.items():
        if k.startswith('edu:'): continue
        try: hit = k == key or k == label or bool(re.search(k, label, re.I))
        except re.error: hit = False
        if hit: return True, v
    return False, None


class WD:
    def __init__(self, folder, page, log):
        self.folder, self.page, self.log = folder, page, log
        self.VERIFY_SRC = ''                   # ladder compatibility; we use check_one instead
        self.problems, self.needs, self.failed, self.record = [], [], [], []
        self.answered = {}                     # label/section → answer, for the review-page check
        self.extra_blocks = []                 # résumé-parsed repeat blocks with no profile entry → deleted
        self.fill_err = {}                     # key → 'not_offered' | other exception name
        self.ds_used = []                      # DeepSeek picks / triage answers → ds_used.json, Claude spot-checks them on Review
        self.triaged = set()                   # labels already sent to DeepSeek triage (one try each)
        self.cover_uploaded = bool(read_json(os.path.join(folder, 'uploads.json'), {}).get('cover'))   # JSA-068, survives reruns

    # ---------- page access ----------
    def js(self, expr, arg=None):
        # Workday navigates while we read: "Execution context was destroyed" is a race, not a page error (#50)
        for attempt in range(4):
            try:
                return self.page.evaluate('([src, expr, arg]) => { eval(src); return eval(expr); }', [PAGE_JS, expr, arg])
            except Exception as e:
                if 'Execution context was destroyed' in str(e) and attempt < 3:
                    try: self.page.wait_for_load_state('domcontentloaded', timeout=15000)
                    except Exception: pass
                    time.sleep(0.8); continue
                raise

    def extract(self):
        return self.js('__wdExtract()')

    def settle(self, tries=20):
        """Wait until the page's field list stops changing (Workday renders sections lazily)."""
        last = -1
        for _ in range(tries):
            info = self.extract(); n = len(info['fields'])
            if n and n == last: return info
            last = n; time.sleep(0.7)
        return info

    def errors(self):
        return self.js('__wdErrors()')

    def field_now(self, f):
        xs = self.extract()['fields']
        for x in xs:
            if x['key'] == f['key']: return x
        same = [x for x in xs if x.get('panel') == f.get('panel') and x['label'] == f['label']]   # re-rendered → find by block + label
        if same:
            f['key'], f['sel'] = same[0]['key'], same[0]['sel']
            return same[0]
        return None

    def relocate(self, f):
        if not self.page.locator(f['sel']).count(): self.field_now(f)
        return None

    # ---------- answers ----------
    def missing_entries(self, fields):
        """Kinds (work / education / languages) that have fewer blocks on this page than profile entries — only on pages that show that section."""
        out = []
        for kind in ('work', 'education', 'languages'):    # "Your Experience N", "Professional Experience N", "Academic Experience N" (RBC, Ryan, KBR 2026-11-01); languages: Voya 2026-11-02
            secs = {f['section'] for f in fields if re.search(r'\d+\s*$', f['section'] or '') and block_kind_of(f['section']) == kind}
            shown = self.section_group(kind).count()
            if shown and len(secs) < len(PROFILE[kind]): out.append(kind)
        return out

    def section_group(self, kind):
        """The whole Work Experience / Work History / Education section (aria-labelledby '<Heading>-section')."""
        g = self.page.locator('[role="group"][aria-labelledby$="-section"]').filter(has=self.page.locator('h3, h4, legend'))
        if kind == 'work':                                 # any "… Experience" / Work / Employment section that is not the education one
            return g.filter(has_text=re.compile('Work|Employment|Experience', re.I)).filter(has_not_text=re.compile('Educat|Academic|School or University|Fluent', re.I)).first
        if kind == 'languages':
            return g.filter(has_text=re.compile('Language', re.I)).filter(has_not_text=re.compile('Educat|Academic|School or University|Job Title', re.I)).first
        return g.filter(has_text=re.compile('Education|Academic', re.I)).first

    def block_kind(self, section):
        return ('languages' if re.search(r'language', section, re.I) else 'education' if re.search(r'educat|academic', section, re.I)
                else 'work' if re.search(r'work|experience|employment', section, re.I) else None)   # "Academic Experience N" is education (KBR, Ryan 2026-11-01)

    def block_entry(self, section, fields_in_block, used):
        """Work Experience N / Education N → the N-th profile entry (résumé order; Workday autofill keeps it).
        Languages N → the entry whose name matches the block's Language value. No entry → None (block is deleted)."""
        kind = ('languages' if re.search(r'language', section, re.I) else 'education' if re.search(r'educat|academic', section, re.I)
                else 'work' if re.search(r'work|experience|employment', section, re.I) else None)   # "Academic Experience N" is education (KBR, Ryan 2026-11-01)
        if not kind: return None, None
        if kind == 'languages':
            lang = ' '.join(N(x['value']) for x in fields_in_block if re.search(r'^language', x['label'], re.I))
            return kind, next((e for e in PROFILE['languages'] if lang and re.search(e['match'], lang, re.I)), None)
        m = re.search(r'(\d+)\s*$', section)
        i = int(m.group(1)) - 1 if m else -1
        return kind, (PROFILE[kind][i] if 0 <= i < len(PROFILE[kind]) else None)

    def block_answer(self, kind, e, f):
        lab = f['label']
        if kind == 'languages':
            if re.search(r'^language', lab, re.I): return f['value'] or language_option(e['match'], f.get('options'))
            if re.search(r'fluent', lab, re.I): return 'checked' if e['fluent'] else ''
            if re.search(r'comprehension|overall|reading|speaking|writing|listening|proficien', lab, re.I):
                opts = [o for o in (f.get('options') or []) if not re.search(r'^select', o, re.I)]
                pick = (next((o for o in opts if re.search(r'fluent', o, re.I)), None) or next((o for o in opts if re.search(r'native|expert', o, re.I)), None)
                        or next((o for o in opts if re.search(r'high|advanced', o, re.I)), None)
                        or (max(opts, key=lambda o: int(re.match(r'\s*(\d+)', o).group(1))) if opts and all(re.match(r'\s*\d+', o) for o in opts) else None))   # highest level (Joey: all top level)
                return pick or (e['level'] if not opts else None)       # tenant wording differs: "4 - Fluent" / "Fluent" 
            return None
        if kind == 'work':
            for k, rx in (('Job Title', r'job title|position|title'), ('Company', r'company|employer'), ('Location', r'location|city'),
                          ('From', r'^from|start'), ('To', r'^to\b|end')):
                if re.search(rx, lab, re.I): return e[k]
            if re.search(r'currently work', lab, re.I): return 'checked' if e['current'] else ''
            if re.search(r'description|responsibilit', lab, re.I): return e.get('Description') or f['value'] or None   # approved résumé wording
        else:
            if re.search(r'school|university|institution', lab, re.I):
                f['alts'] = e.get('School_alts', []); return e['School']      # tenant spellings (a Workday employer: "University of Illinois at Urbana - Champaign")
            if re.search(r'^degree', lab, re.I):
                try: ovd_ = json.load(open(os.path.join(self.folder, 'answers.json'), encoding='utf-8'))
                except Exception: ovd_ = {}
                if ovd_.get('edu:' + e['School'] + ':Degree'): f['_src'] = 'answers.json'; return ovd_['edu:' + e['School'] + ':Degree']
                if not f['options']: f['_no_ds'] = True; return None   # never the shared-label ds answer (a Workday employer: both blocks became Undergraduate)
                deg_rx = {'master': r'master|^m\.?s\.?c?$|^m\.?a\.?$|^ms\b|^msc\b', 'bachelor': r'bachelor|^b\.?s\.?$|^b\.?a\.?$'}.get(e['Degree'], e['Degree'])
                is_mba_only = lambda o: bool(re.search(r'\bMBA\b|business admin', o, re.I)) and not re.search(r'science', o, re.I)   # a Workday employer: "Masters of Arts or Science or Business Administration" is the M.S. option
                if e['Degree'] == 'master':
                    pref = master_options(f['options'])
                elif e['Degree'] == 'bachelor':
                    pref = bachelor_options(f['options'])
                else:
                    pref = [o for o in f['options'] if re.search(deg_rx, o.strip(), re.I) and not is_mba_only(o)]
                if not pref:   # level-only lists: "Post Graduate Degree" / "Undergraduate Degree" (a Workday employer 2026-10-30)
                    lvl = {'master': r'post ?-?grad|^graduate\b|graduate degree', 'bachelor': r'under ?-?grad'}.get(e['Degree'])
                    pref = [o for o in f['options'] if lvl and re.search(lvl, o.strip(), re.I) and not is_mba_only(o)]
                if not pref: f['_no_ds'] = True   # never fall back to ds_answers by the shared label "Degree": both blocks got the UIUC answer
                return pref[0] if pref else None
            if re.search(r'field of study|major|discipline', lab, re.I):
                try: ov = json.load(open(os.path.join(self.folder, 'answers.json'), encoding='utf-8'))
                except Exception: ov = {}
                if ov.get('edu:' + e['School'] + ':Field'):              # per-application choice by Joey (a Workday employer 10-28: UChicago = Applied Statistics)
                    f['alts'] = []; f['_src'] = 'answers.json'; return ov['edu:' + e['School'] + ':Field']
                f['alts'] = e.get('Field_alts', []); return e['Field']
            if re.search(r'gpa|overall result|grade', lab, re.I):
                try: ov = json.load(open(os.path.join(self.folder, 'answers.json'), encoding='utf-8'))
                except Exception: ov = {}
                if ov.get('edu:' + e['School'] + ':GPA'): f['_src'] = 'answers.json'; return ov['edu:' + e['School'] + ':GPA']   # Joey per application
                if not e['GPA'] and f.get('required'): f['_src'] = 'decisions-log 2026-10-30 (required M.S. GPA = N/A)'; return 'N/A'
                return e['GPA']   # '' = keep empty: no M.S. GPA yet; None let DeepSeek copy the UIUC GPA into UChicago (AMAT 2026-10-30)
            if re.search(r'^from|start', lab, re.I): return e['From']
            if re.search(r'^to\b|end|graduat', lab, re.I): return e['To']
        return None

    def plan_page(self, fields, step):
        """→ list of fields with answer/status/source (same shape as plan.json fields)."""
        out, blocks, used = [], {}, set()
        for f in fields:
            if f['section'] and re.search(r'work|experience|employment|educat|language', f['section'], re.I) and re.search(r'\d+\s*$', f['section']):
                blocks.setdefault(f['section'], []).append(f)
        handled = set()
        # match blocks to profile entries: 1) by company/school name, 2) empty (just-added) blocks in order; anything else = extra
        kinds = {sec: self.block_kind(sec) for sec in blocks}
        assign, taken = {}, set()
        lang_secs = [(sec, ' '.join(N(x['value']) for x in fl if re.search(r'^language', x['label'], re.I))) for sec, fl in blocks.items() if kinds[sec] == 'languages']
        for sec, i in assign_languages(lang_secs, PROFILE['languages']).items():
            assign[sec] = PROFILE['languages'][i] if i is not None else None
        for sec, fl in blocks.items():
            k = kinds[sec]
            if k == 'languages': continue
            names = ' '.join(N(x['value']) for x in fl if re.search(r'company|employer|school|university|institution', x['label'], re.I))
            for i, e in enumerate(PROFILE.get(k, [])):
                if names and (k, i) not in taken and re.search(e['match'], names, re.I):
                    assign[sec] = e; taken.add((k, i)); break
        for sec, fl in blocks.items():
            k = kinds[sec]
            if sec in assign or k == 'languages': continue
            names = ' '.join(N(x['value']) for x in fl if re.search(r'company|employer|school|university|institution', x['label'], re.I))
            if not names:
                free = [(i, e) for i, e in enumerate(PROFILE.get(k, [])) if (k, i) not in taken]
                if free: assign[sec] = free[0][1]; taken.add((k, free[0][0]))
        ovj = read_json(os.path.join(self.folder, 'answers.json'), {}); ovd = read_json(os.path.join(self.folder, 'ds_answers.json'), {})
        for sec, fl in blocks.items():
            kind, e = kinds[sec], assign.get(sec)
            if e is None:
                self.extra_blocks.append((sec, fl[0].get('panel'), ' / '.join(N(x['value']) for x in fl if x['value'])[:120]))
                for f in fl: handled.add(f['key'])
                continue
            used.add(id(e))
            for f in fl:
                a = self.block_answer(kind, e, f)
                handled.add(f['key'])
                src = f.pop('_src', None) or ('wd_profile:' + kind)
                if a is None:                                  # not in wd_profile → Joey's answers.json, then DeepSeek triage answers
                    for name, ov in (('answers.json', ovj),) + ((() if f.pop('_no_ds', False) else (('ds_answers.json', ovd),))):
                        hit, v = ov_lookup(ov, f['label'], f['key'])
                        if hit and v: a, src = v, name; break
                if a is None:
                    if f['required'] and not f['value']:
                        self.needs.append({'step': step, 'section': sec, 'label': f['label'], 'options': f['options'], 'type': f['type'],
                                           'key': f['key'], 'sel': f['sel'], 'why': 'not in wd_profile'})
                    out.append(dict(f, status='keep', source='page'))
                else:
                    out.append(dict(f, answer=a, status='ok', source=src, alts=f.get('alts', []), entry=e, kind=kind))
        for f in fields:                                   # phone extension: always empty (10-28: the number went into it)
            if f['key'] not in handled and re.search(r'extension', f['label'], re.I) and f['type'] == 'text':
                handled.add(f['key']); out.append(dict(f, answer='', status='ok', source='no extension'))
            elif f['key'] not in handled and (re.search(r'middleName', f.get('aid') or '') or re.search(r'^(preferred )?middle name$', f['label'], re.I)):
                handled.add(f['key']); out.append(dict(f, answer='', status='ok', source='no middle name (Workday shows it inside the name)'))
            elif f['key'] not in handled and re.search(r'preferredName--lastName', f.get('aid') or ''):
                handled.add(f['key']); out.append(dict(f, answer='Sun', status='ok', source='preferred last name'))
        ov = {}
        try: ov = json.load(open(os.path.join(self.folder, 'answers.json'), encoding='utf-8'))
        except Exception: pass
        for f in fields:                                   # low-stakes source question: pick automatically (Joey 10-28: "随便选")
            if f['key'] in handled or not re.search(r'how did you (hear|find|learn)|^source$|referral source', f['label'], re.I): continue
            if any(re.search(k, f['label'], re.I) for k in ov): continue
            handled.add(f['key'])
            if f['type'] in ('multi', 'radio') or (f['type'] == 'select' and (f['options'] or f.get('opts_read'))):
                # JSA-067: the options are already read (checkbox list on PIMCO, a select) → pick here, no menu to open
                pick, real = source_pick(f['options']), real_options(f['options'])
                if pick:
                    out.append(dict(f, answer=pick, status='ok', source='auto source pick (truthful channel)')); continue
                why = ('the menu has no options on this tenant (only a placeholder) — nothing truthful to pick' if not real
                       else 'every option claims a referral / event / employment — never picked (Joey 2026-11-01)')
                if f['required'] and not f['value']:
                    self.needs.append({'step': step, 'section': f['section'], 'label': f['label'], 'options': f['options'], 'type': f['type'],
                                       'key': f['key'], 'sel': f['sel'], 'why': why, 'no_triage': True})   # a model must not pick a claim
                out.append(dict(f, status='needs_user' if f['required'] else 'skip', source=why)); continue
            out.append(dict(f, answer='SOURCE_AUTO', status='ok', source='auto source pick'))
        for f in fields:                                   # "I have uploaded both my cover letter and resume" (JSA-068)
            if f['key'] in handled or not COVER_ASKED_RX.search(f['label']) or ov_lookup(ov, f['label'], f['key'])[0]: continue
            if self.cover_uploaded:
                yes = next((o for o in real_options(f.get('options')) if re.match(r'\s*yes\b', o, re.I)), None)
                if yes or f['type'] == 'checkbox':
                    handled.add(f['key']); out.append(dict(f, answer=yes or 'checked', status='ok', source='cover letter uploaded (uploads.json)'))
        rest = [f for f in fields if f['key'] not in handled and f['type'] != 'file']
        if rest:
            pf = [{'key': f['key'], 'label': f['label'], 'type': {'select': 'combo', 'prompt': 'combo'}.get(f['type'], f['type']),   # date stays date: the rule's date, not "Summer 2027" (BCBS NE 2026-11-01)
                   'required': f['required'], 'options': [] if f['type'] == 'date' else f['options'], 'sel': f['sel']} for f in rest]
            plan = PB.build(self.folder, pf, self.page.url, 'workday')
            byk = {p['key']: p for p in plan['fields']}
            for f in rest:
                p = byk[f['key']]
                if p.get('status') == 'ok':
                    ans = p['answer']
                    if f['type'] == 'checkbox':
                        ans = '' if str(ans).lower() in ('no', 'false', '') else 'checked'
                    out.append(dict(f, answer=ans, status='ok', source=p.get('source')))
                elif f['type'] == 'checkbox' and f['required'] and p.get('source') == 'consent':
                    out.append(dict(f, answer='checked', status='ok', source='required consent (batch approved)'))
                elif f['type'] == 'date' and re.search(r'^(today.?s )?date$|signature date', f['label'], re.I):
                    out.append(dict(f, answer=datetime.now().strftime('%m/%d/%Y'), status='ok', source='today'))
                elif f['value'] and not f['required']:
                    out.append(dict(f, status='keep', source='page'))
                elif f['value'] and f['required']:
                    out.append(dict(f, status='keep', source='page (prefilled)'))    # e.g. email from the account
                else:
                    if f['required']:
                        self.needs.append({'step': step, 'section': f['section'], 'label': f['label'], 'options': f['options'], 'type': f['type'],
                                           'key': f['key'], 'sel': f['sel'], 'why': p.get('source') or 'no rule',
                                           'no_triage': bool(p.get('no_triage'))})   # a rule said "Joey decides" (JSA-105) → no DeepSeek triage
                    out.append(dict(f, status='needs_user' if f['required'] else 'skip', source=p.get('source')))
        return out

    # ---------- fill (real clicks / keys) ----------
    def open_options(self, f):
        box = self.page.locator(f['sel']).first
        box.locator('button[aria-haspopup="listbox"]').first.click()
        self.page.wait_for_selector('[role="listbox"] [role="option"], [data-automation-id="promptOption"]', timeout=5000)
        time.sleep(0.3)
        opts = self.page.evaluate('''() => [...document.querySelectorAll('[role="listbox"] [role="option"]')]
            .filter(o => o.getClientRects().length && !o.closest('[data-automation-id^="formField-"]'))   // the popup only, not pills
            .map(o => o.textContent.replace(/\\s+/g, ' ').trim())''')
        return [o for o in opts if o and not PLACEHOLDER_RX.match(o)]

    def read_select_options(self, fields):
        """Open each select once and keep its options; opts_read = the menu opened (an empty list is then real, JSA-067)."""
        for f in fields:
            if f['type'] == 'select' and not f['options']:
                try: f['options'] = self.open_options(f); f['opts_read'] = True; self.page.keyboard.press('Escape'); time.sleep(0.2)
                except Exception: pass

    def pick_source(self, f):
        """Source menu (Joey 2026-10-30: 「直接选拉开表单的第一个即可」): the FIRST option at every level, skipping only
        options that claim a person (referral / employee / alumni / recruiter / agency) — those would be untrue."""
        p = self.page
        box = p.locator(f['sel']).first
        bad = SOURCE_CLAIM.pattern
        cur = [N(x) for x in box.locator('[data-automation-id="selectedItem"]').all_inner_texts()]
        # Joey 2026-10-30: first option at every level; Joey 2026-11-01 (PIMCO got "Referred by a PIMCO Recruiter"): 「跳过声称有人推荐的选项」 — skip person / event claims again
        if cur and not re.search(bad, cur[0], re.I): f['answer'] = cur[0]; return
        if cur:   # résumé autofill pre-selected an untrue source ("Agency / Search Firm", a Workday employer 2026-10-30) → remove it
            for d in box.locator('[data-automation-id="DELETE_charm"], [data-automation-id="selectedItem"] [role="button"], [data-automation-id="selectedItem"] button').all():
                try: d.click(); time.sleep(0.5)
                except Exception: pass
            self.log(f"  source: removed pre-selected '{cur[0]}'")
        opener = box.locator('button[aria-haspopup="listbox"]')
        (opener.first if opener.count() else box.locator('input').first).click()   # a select's hidden text input does not open it (JSA-067)
        try: p.wait_for_selector('[data-automation-id="promptOption"], [role="listbox"] [role="option"]', timeout=5000)
        except Exception: pass
        time.sleep(1.0)
        opts_js = '''() => [...document.querySelectorAll('[data-automation-id="promptOption"], [role="listbox"] [role="option"]')]
            .filter(o => o.getClientRects().length && !o.closest('[data-automation-id="selectedItem"]')).map(o => o.textContent.replace(/\\s+/g, ' ').trim())
            .filter(t => t && !/^select one$|\\(\\+\\d+\\)$/i.test(t))'''
        for depth in range(3):
            opts = p.evaluate(opts_js)
            if not opts: break
            if not real_options(opts):                       # only "Select One" / "选择一个": the tenant's list is empty (Tencent 2026-11-03)
                p.keyboard.press('Escape'); raise ValueError('source menu: no options on this tenant (only a placeholder)')
            # neutral channels first, so a vague top level ("Direct Source") whose sub-options are all claims is not taken (PIMCO 2026-11-01)
            pick = source_pick(opts)
            if not pick:                                     # every option claims a person / event: never pick one (Joey 2026-11-01)
                p.keyboard.press('Escape'); raise ValueError('source menu: every option claims a referral / event / employment')
            p.locator('[data-automation-id="promptOption"], [role="listbox"] [role="option"]').filter(has_text=re.compile('^\\s*' + re.escape(pick) + '\\s*$')).last.click()
            time.sleep(1.2)
            cur = [N(x) for x in p.locator(f['sel']).first.locator('[data-automation-id="selectedItem"]').all_inner_texts()]
            sel_btn = p.locator(f['sel']).first.locator('button[aria-haspopup="listbox"]')
            if cur or (sel_btn.count() and N(sel_btn.first.inner_text()) == pick):
                f['answer'] = cur[0] if cur else pick; p.keyboard.press('Escape'); self.log(f"  source → {f['answer']}"); return
        p.keyboard.press('Escape')
        raise ValueError('source menu: nothing selectable')

    def fill_one(self, f):
        self.relocate(f)
        if f.get('answer') == 'SOURCE_AUTO':
            return self.pick_source(f)
        p, box, ans = self.page, self.page.locator(f['sel']).first, str(f['answer'])
        box.scroll_into_view_if_needed()
        t = f['type']
        if t in ('text', 'textarea'):
            el = box.locator('textarea' if t == 'textarea' else 'input').first
            el.click(); el.fill(ans); el.press('Tab')
            num = salary_number(f['label']) if not re.search(r'\d', ans) else None   # text or textarea (Central Hudson 2026-11-01: textarea)
            if num and not el.input_value().strip():   # a digits-only salary box drops "Open" (Axos, BCBS NE, an employer 2026-11-01)
                el.click(); el.fill(num); el.press('Tab')
                self.log(f"  {f['label'][:50]}: digits-only box — typed {num} (Joey 2026-11-01)")
                f['answer'] = num; f['source'] = 'decisions-log 2026-11-01 (salary number)'
        elif t == 'select':
            opts = self.open_options(f)
            if ans not in opts:
                p.keyboard.press('Escape'); raise ValueError(f"option '{ans}' not offered")
            p.locator('[role="listbox"] [role="option"]:visible').filter(has_text=re.compile('^\\s*' + re.escape(ans) + '\\s*$')).last.click()
        elif t == 'prompt':
            texts = []
            okv = [x.lower() for x in [ans] + f.get('alts', [])]
            for _ in range(5):                                # clear wrong pre-filled (résumé-parsed) selections; the widget re-renders each time
                self.relocate(f); box = p.locator(f['sel']).first
                wrong = [x for x in box.locator('[data-automation-id="selectedItem"]').all() if N(x.inner_text()).lower() not in okv]
                if not wrong: break
                try: wrong[0].locator('[data-automation-id="DELETE_charm"], [aria-label*="delete" i], [aria-label*="remove" i]').first.click(); time.sleep(0.6)
                except Exception: break
            tries = []
            for want in [ans] + [x for x in f.get('alts', []) if x != ans]:
                tries.append((want, want))
                if re.search(r'\s\(', want): tries.append((want, want.split(' (')[0]))   # search finds nothing for "Python (Programming Language)" (a Workday employer 2026-10-30)
            for want, query in tries:
                self.relocate(f); box = p.locator(f['sel']).first
                inp = box.locator('input').first
                inp.click(); inp.fill(''); p.keyboard.type(query, delay=30); p.keyboard.press('Enter')   # Enter = search (some tenants filter, some don't)
                try: p.wait_for_selector('[data-automation-id="promptOption"]', timeout=5000)
                except Exception: continue
                time.sleep(0.8)
                found = p.evaluate(SCROLL_FIND_JS, want)     # virtualized list: scroll until the exact option is rendered
                texts = found.get('seen', [])
                if found.get('hit'):
                    p.locator('[data-cx-opt="1"]').first.click(); time.sleep(0.4); p.keyboard.press('Escape')
                    if want != ans: f['answer'] = want; self.log(f"  {f['label']}: '{ans}' not offered → used '{want}'")
                    return
                p.keyboard.press('Escape')
            raise ValueError(f"no prompt option for '{ans}' or alts (saw {texts[:5]})")
        elif t == 'radio':
            box.locator('label').filter(has_text=re.compile('^\\s*' + re.escape(ans) + '\\s*$')).first.click()
        elif t == 'checkbox':
            cb = box.locator('input[type="checkbox"]').first
            if cb.is_checked() != (ans == 'checked'): cb.click()
        elif t == 'multi':
            want = [w.strip() for w in ans.split(' | ')]
            for lab in box.locator('label').all():
                txt = N(lab.inner_text()); cid = lab.get_attribute('for')
                cb = box.locator(f'[id="{cid}"]') if cid else None
                if cb is not None and cb.count() and cb.is_checked() != (txt in want): lab.click()
        elif t == 'date':
            digits = date_digits(ans, bool(box.locator('[data-automation-id^="dateSectionDay"]').count()))
            first = box.locator('[data-automation-id="dateSectionMonth-display"], [data-automation-id="dateSectionDay-display"], [data-automation-id="dateSectionYear-display"]').first
            (first if first.count() else box.locator('[data-automation-id="dateInputWrapper"]').first).click()   # the real inputs are visually hidden
            p.keyboard.type(digits, delay=60); p.keyboard.press('Tab')
        time.sleep(0.25)

    def check_one(self, f):
        """Our own check: re-read the field from the page and compare with the answer → (ok, {'page': value})."""
        x = self.field_now(f)
        if x is None: return False, {'page': 'MISSING'}
        got, want = N(x['value']), N(f['answer'])
        if f['type'] == 'checkbox': ok = (got == 'checked') == (want == 'checked')
        elif f['type'] == 'date': ok = date_parts(got) == date_parts(want) or (len(date_parts(want)) == 2 and len(date_parts(got)) == 3 and [date_parts(got)[0], date_parts(got)[2]] == date_parts(want))   # "December 2027" = 12/01/2027 (a Workday employer, GE 2026-10-30)
        elif re.search(r'phone', f['label'], re.I) and f['type'] == 'text': ok = re.sub(r'\D', '', got)[-10:] == re.sub(r'\D', '', want)[-10:]
        elif f['type'] == 'multi': ok = sorted(got.split(' | ')) == sorted(want.split(' | '))
        elif f['type'] == 'prompt': ok = bool(got) and any(w and (got.lower() == w.lower() or w.lower() in got.lower()) for w in [want] + list(f.get('alts') or []))   # alts = tenant spellings / approved fallbacks
        else: ok = got == want
        return ok, {'page': got, 'framework': 'n/a'}

    # ---------- one page ----------
    def do_page(self, usage):
        info = self.settle(); step = info['step']
        if re.search(r'autofill', step, re.I) or (not info['fields'] and self.page.locator('input[type="file"]').count()):
            self.upload_resume(); return step, [], True
        fields = [f for f in info['fields']]
        self.read_select_options(fields)                   # read option lists of dropdowns once
        n_needs = len(self.needs)
        files = [f for f in fields if f['type'] == 'file']
        if files: self.upload_files(files, step)       # résumé, cover letter (JSA-068); Joey's documents → needs
        self.extra_blocks = []
        plan = self.plan_page(fields, step)
        if self.extra_blocks:                              # delete parsed blocks that are not in wd_profile (truth rule), then re-read
            for sec, panel, content in reversed(self.extra_blocks):
                try:   # the Delete button sits in the block's header, outside the role=group element → walk up from the heading
                    ok = self.page.evaluate('''(pid) => { document.querySelectorAll('[data-cx-del]').forEach(x => x.removeAttribute('data-cx-del'));
                        let e = document.getElementById(pid); const q = 'button[data-automation-id="panel-set-delete-button"], button[aria-label*="Delete" i]';
                        const find = n => n.querySelector(q) || [...n.querySelectorAll('button')].find(b => /^delete$/i.test(b.textContent.trim()));
                        while (e && !find(e)) e = e.parentElement; if (!e) return false; find(e).setAttribute('data-cx-del', '1'); return true; }''', panel)
                    if not ok: raise RuntimeError('no Delete button near the block heading')
                    self.page.locator('[data-cx-del="1"]').first.click(); time.sleep(1.2)
                    self.log(f'  deleted extra block "{sec}" (not in the profile): {content}')
                except Exception as e:
                    self.log(f'  COULD NOT delete extra block "{sec}": {type(e).__name__}: {str(e)[:80]}')
                    self.failed.append({'step': step, 'section': sec, 'label': '(extra block — delete by hand)', 'want': 'deleted', 'content': content})
            self.needs = self.needs[:n_needs]
            fields = self.settle()['fields']
            self.read_select_options(fields)
            self.extra_blocks = []
            plan = self.plan_page(fields, step)
        for _ in range(4 if re.search(r'experience', step, re.I) else 0):   # profile entries missing on the page → "Add" / "Add Another" in that section
            missing = self.missing_entries(fields)
            if not missing: break
            try:
                grp = self.section_group(missing[0])
                grp.locator('button:has-text("Add Another"), button:has-text("Add")').last.click(); time.sleep(1.5)
                self.log(f'  added an empty {missing[0]} block')
            except Exception as e:
                self.log(f'  could not add a {missing[0]} block: {type(e).__name__}'); break
            self.needs = self.needs[:n_needs]
            fields = self.settle()['fields']
            self.read_select_options(fields)
            plan = self.plan_page(fields, step)
        todo = [f for f in plan if f['status'] == 'ok']
        for f in sorted(todo, key=lambda f: 1 if f['type'] in ('text', 'textarea') else 0):   # widgets first, text last
            ok, _ = self.check_one(f)
            if ok: continue
            for attempt in (1, 2):                           # Workday re-renders a block after each change → relocate and retry once
                try: self.fill_one(f); break
                except Exception as e:
                    if attempt == 2 or isinstance(e, ValueError):
                        self.fill_err[f['key']] = 'not_offered' if isinstance(e, ValueError) else type(e).__name__
                        self.log(f"  {step} | {f['section']} {f['label'][:40]}: script fill failed: {type(e).__name__}: {str(e)[:90]}"); break
                    time.sleep(1); self.page.keyboard.press('Escape'); self.field_now(f)
        self.page.mouse.click(2, 2); time.sleep(0.6)
        known = {f['key'] for f in fields}
        for _level in range(8):                            # conditional questions can chain (a Workday employer 2026-11-02: citizenship → PR → visa details)
            new = [x for x in self.settle(8)['fields'] if x['key'] not in known and x['type'] != 'file']
            if not new: break                              # conditional questions that appear after an answer (preferred name, race after ethnicity …)
            known |= {x['key'] for x in new}
            self.read_select_options(new)
            extra = self.plan_page(new, step); plan += extra
            for f in [x for x in extra if x['status'] == 'ok']:
                todo.append(f)
                try: self.fill_one(f)
                except Exception as e: self.log(f"  {step} | {f['label'][:40]}: script fill failed: {type(e).__name__}")
            self.page.mouse.click(2, 2); time.sleep(0.4)
        bad = [f for f in todo if not self.check_one(f)[0]]
        for f in [x for x in bad if x['type'] in ('prompt', 'select') and self.fill_err.get(x['key']) == 'not_offered']:
            if str(f.get('source', '')).startswith('answers.json'):   # Joey's own value is not offered → ask him again (never overrule him)
                bad.remove(f); f['status'] = 'needs_user'
                self.needs.append({'step': step, 'section': f['section'], 'label': f['label'], 'type': f['type'], 'key': f['key'], 'sel': f['sel'],
                                   'options': self.field_options(f), 'why': f"your answer '{f['answer']}' is not offered — pick one of the options",
                                   'answer_key': self.answer_key(f)})
                continue
            r = self.pick_with_deepseek(f, step, usage)           # B: 'ok' | 'none' | 'fail'
            if r == 'ok': bad.remove(f); continue
            if r == 'none' and f['required']:
                bad.remove(f); f['status'] = 'needs_user'
                self.needs.append({'step': step, 'section': f['section'], 'label': f['label'], 'type': f['type'], 'key': f['key'], 'sel': f['sel'],
                                   'options': f.get('all_options') or [], 'why': f"'{f['answer']}' not offered; DeepSeek found no truthful option",
                                   'answer_key': self.answer_key(f)})
        opt_empty = [f for f in bad if not f['required'] and (f['type'] == 'prompt' or self.fill_err.get(f['key']) == 'not_offered')]
        for f in opt_empty:                                # optional: script only; clear wrong selections and leave it empty (Joey 10-28)
            x = self.field_now(f) or {}
            if x.get('value') and f['type'] == 'prompt':
                for _ in range(5):
                    pills = self.page.locator(f['sel']).first.locator('[data-automation-id="selectedItem"]')
                    if not pills.count(): break
                    try: pills.first.locator('[data-automation-id="DELETE_charm"], [aria-label*="delete" i], [aria-label*="remove" i]').first.click(); time.sleep(0.6); self.relocate(f)
                    except Exception: break
            self.log(f"  {f['section']} {f['label']}: optional, could not set '{f['answer']}' ({self.fill_err.get(f['key'], 'check')}) → left empty for review")
            f['status'] = 'skip'
        bad = [f for f in bad if f not in opt_empty]
        for f in bad:                                       # level 2 (text/date/checkbox/radio; pickers were handled above)
            if f['type'] in ('prompt', 'select') and self.fill_err.get(f['key']) == 'not_offered': pass
            elif ladder.deepseek_fix(self, dict(f), self.log, usage): continue
            self.failed.append({'step': step, 'label': f['label'], 'section': f['section'], 'want': f['answer'], 'sel': f['sel']})
        for f in plan:
            if f['status'] == 'ok': self.answered[(f['section'], f['label'])] = f['answer']
        self.record.append({'step': step, 'fields': [{k: f.get(k) for k in ('label', 'section', 'type', 'required', 'answer', 'value', 'status', 'source')} for f in plan]})
        self.save_ds_used()
        return step, plan, (len(self.needs) == n_needs and not self.failed)

    # ---------- DeepSeek: option pick (B) · triage (C) · wait for Joey (A) ----------
    def save_ds_used(self):
        if not self.ds_used: return
        pth = os.path.join(self.folder, 'ds_used.json'); prev = read_json(pth, [])
        json.dump(prev + [u for u in self.ds_used if u not in prev], open(pth, 'w'), indent=1, ensure_ascii=False)

    def answer_key(self, f):
        e = f.get('entry')
        if f.get('kind') == 'education' and e and re.search(r'field of study|major|discipline', f['label'], re.I):
            return 'edu:' + e['School'] + ':Field'
        return '^' + re.escape(f['label']) + '$'

    def field_options(self, f, terms=()):
        """COMPLETE option list of a select (open it) or prompt (search each term, scroll the virtualized list, merge)."""
        if f['type'] == 'select':
            try: o = self.open_options(f); self.page.keyboard.press('Escape'); return o
            except Exception: return f.get('options') or []
        p, seen, inp = self.page, [], None
        for term in (list(terms) or ['']):
            try:
                self.relocate(f); box = p.locator(f['sel']).first; box.scroll_into_view_if_needed()
                inp = box.locator('input').first
                inp.click(); inp.fill('')
                if term: p.keyboard.type(term, delay=30)
                p.keyboard.press('Enter')
                p.wait_for_selector('[data-automation-id="promptOption"], [role="listbox"] [role="option"]', timeout=5000); time.sleep(0.8)
                for o in p.evaluate(COLLECT_JS):
                    if o not in seen and not re.match(r'^(select one|no items\.?)$', o, re.I): seen.append(o)
            except Exception as e:
                self.log(f"  options '{term}': {type(e).__name__}")
            finally:
                try: p.keyboard.press('Escape'); inp is not None and inp.fill('')
                except Exception: pass
        return seen

    def pick_with_deepseek(self, f, step, usage):
        e = f.get('entry') or {}
        if f.get('kind') == 'education' and re.search(r'field of study|major|discipline', f['label'], re.I):
            facts = f"{e['School']}: {e.get('Field_real') or e['Field']}"
            prefs = e.get('Field_prefs') or [e['Field']] + e.get('Field_alts', [])
            terms = e.get('Field_search') or [w[:7] for w in prefs[:3]]
        else:
            facts = f"planned answer from saved facts: {f['answer']} (source: {f.get('source')}); section: {f.get('section') or ''}"
            prefs = [f['answer']] + [a for a in f.get('alts') or [] if a != f['answer']]
            terms = list(dict.fromkeys(w[:7] for w in re.findall(r'[A-Za-z]{4,}', ' '.join(prefs[:2]))))[:4]
        opts = self.field_options(f, terms)
        f['all_options'] = opts
        if not opts:
            self.log(f"  {f['label'][:40]}: could not read the option list"); return 'fail'
        rel = [o for o in opts if re.search(r'computer|information system|data scien|statistic|analytic', o, re.I)]
        self.log(f"  {len(opts)} options; preference-relevant: " + ', '.join(rel[:8]))
        auto = pick_by_prefs(opts, prefs)                       # Joey's order wins, no model call
        if auto:
            want0 = f['answer']; f['answer'], f['alts'] = auto, []
            try: self.fill_one(f)
            except Exception as ex: self.log(f"  prefs pick '{auto}': {type(ex).__name__}: {str(ex)[:60]}")
            self.page.mouse.click(2, 2); time.sleep(0.4)
            if self.check_one(f)[0]:
                f['source'] = 'prefs-match'
                self.log(f"  prefs pick '{auto}' (was planned '{want0}') — deterministic, 0 model calls")
                return 'ok'
            self.log(f"  prefs pick '{auto}' did not stick → DeepSeek")
        ckey = canon.classify(f['label'])                       # a canonical field: its accepted option, no model call (JSA-005)
        cp = canon.pick(ckey, opts, canon.tenant_of(self.page.url)) if ckey else None
        if cp:
            want0 = f['answer']; f['answer'], f['alts'] = cp, []
            try: self.fill_one(f)
            except Exception as ex: self.log(f"  canon pick '{cp}': {type(ex).__name__}: {str(ex)[:60]}")
            self.page.mouse.click(2, 2); time.sleep(0.4)
            if self.check_one(f)[0]:
                f['source'] = 'canon:' + ckey
                self.log(f"  canon pick '{cp}' for {ckey} (was planned '{want0}') — 0 model calls")
                return 'ok'
            self.log(f"  canon pick '{cp}' did not stick → DeepSeek")
        pick = ladder.ds_pick(f['label'], f['required'], facts, prefs, opts, usage, self.log)
        if not pick: return 'none'
        want = f['answer']; f['answer'], f['alts'] = pick, []
        try: self.fill_one(f)
        except Exception as ex: self.log(f"  DS pick '{pick}' could not be clicked: {type(ex).__name__}")
        self.page.mouse.click(2, 2); time.sleep(0.4)
        if self.check_one(f)[0]:
            f['source'] = 'deepseek-pick'
            self.ds_used.append({'kind': 'pick', 'step': step, 'section': f.get('section'), 'label': f['label'], 'answer': pick,
                                 'wanted': want, 'options_seen': len(opts), 'at': now()})
            return 'ok'
        return 'fail'

    def triage_needs(self, usage):
        """C: unknown required questions → DeepSeek maps them to SAVED facts (ds_answers.json). Returns how many it mapped."""
        todo = [n for n in self.needs if n['label'] not in self.triaged and not str(n.get('answer_key', '')).startswith('edu:')
                and 'not offered' not in str(n.get('why', '')) and not n.get('no_triage') and n.get('type') != 'file'
                and not HUMAN_CHECK_RX.search(n['label'])]   # a human check is Joey's, never a model's (FHLB Indy 2026-11-03: DeepSeek answered it)
        if not todo: return 0
        for n in todo:
            self.triaged.add(n['label'])
            if n.get('type') == 'prompt' and not n.get('options') and n.get('sel'):
                n['options'] = self.field_options(dict(n), [''])
        got = ladder.ds_triage([{'label': n['label'], 'type': n.get('type'), 'options': n.get('options')} for n in todo], usage, log=self.log)
        if not got: return 0
        dp = os.path.join(self.folder, 'ds_answers.json'); ds = read_json(dp, {})
        for i, (ans, src) in got.items():
            n = todo[i]
            ds['^' + re.escape(n['label']) + '$'] = ans
            self.ds_used.append({'kind': 'triage', 'step': n.get('step'), 'section': n.get('section'), 'label': n['label'], 'answer': ans,
                                 'source_fact': src, 'at': now()})
            self.log(f"  triage: {n['label'][:50]} → {ans}  [{src[:60]}]")
        json.dump(ds, open(dp, 'w'), indent=1, ensure_ascii=False)
        self.save_ds_used()
        return len(got)

    def wait_for_answers(self, url, tried, timeout_min):
        """A: keep the tab, write wd_needs.json, poll answers.json every 3 s until every need has a NEW answer."""
        for n in self.needs: n.setdefault('answer_key', '^' + re.escape(n['label']) + '$')
        compact = [{k: (v[:40] if k == 'options' else v) for k, v in n.items() if k != 'sel'} for n in self.needs]
        json.dump({'how': 'write answers.json in this folder ON THE MAC: {"<answer_key>": "<exact option text or answer>"}; '
                          'the runner is waiting and continues by itself', 'needs': compact},
                  open(os.path.join(self.folder, 'wd_needs.json'), 'w'), indent=1, ensure_ascii=False)
        queue(self.folder, 'Workday needs answers (runner is WAITING): ' + '; '.join(n['label'][:50] for n in self.needs[:6]) + ' → answers.json', url)
        set_status(self.folder, 'needs-user', f'{len(self.needs)} question(s) in wd_needs.json')
        self.log(f'waiting up to {timeout_min} min for answers.json ({len(self.needs)} question(s)) …')
        human = self.human_needs()
        if human:
            push(*human_check.message(self.folder, [{'question': n['label'], 'options': n.get('options')} for n in human], parked=False))
        else:
            push('求职 runner 需要你', f"{os.path.basename(self.folder)[11:60]}\n" + '\n'.join('· ' + n['label'][:90] for n in self.needs[:4]) +
                 '\n回答后 runner 自动继续。')
        end, ap = time.time() + timeout_min * 60, os.path.join(self.folder, 'answers.json')
        while time.time() < end:
            self.capture_human_answers()
            if needs_answered(self.needs, read_json(ap, {}), tried):
                self.log('answers received — continuing on the same page'); set_status(self.folder, 'running', 'answers received')
                return True
            time.sleep(3)
            try: self.page.title()            # keep the CDP connection alive
            except Exception: pass
        return False

    def human_needs(self):
        return [n for n in self.needs if HUMAN_CHECK_RX.search(n['label'])]

    def capture_human_answers(self):
        """A human check Joey answered in the tab itself: take the value HE picked into answers.json (he chose it, not us)."""
        ap = os.path.join(self.folder, 'answers.json')
        for n in self.human_needs():
            n.setdefault('answer_key', '^' + re.escape(n['label']) + '$')
            if not n.get('sel'): continue
            try:
                v = N(self.page.locator(n['sel']).first.inner_text(timeout=1500))
                v = next((o for o in (n.get('options') or []) if o and re.search(r'(^|\s)' + re.escape(o) + r'($|\s)', v)), '')
                if v:
                    cur = read_json(ap, {}); k = n['answer_key']
                    if cur.get(k) != v:
                        cur[k] = v; json.dump(cur, open(ap, 'w'), indent=1, ensure_ascii=False)
                        self.log(f'human check answered by Joey in the tab: {v}')
            except Exception:
                pass

    def park_human(self, url):
        """JSA-106: a human check is Joey's — record it, push the question + options, keep the tab; the batch moves on."""
        hn = self.human_needs()
        compact = [{k: (v[:40] if k == 'options' else v) for k, v in n.items() if k != 'sel'} for n in self.needs]
        json.dump({'how': 'human check: Joey answers in the tab, then rerun run_wd.py --attach; other questions → answers.json', 'needs': compact},
                  open(os.path.join(self.folder, 'wd_needs.json'), 'w'), indent=1, ensure_ascii=False)
        queue(self.folder, 'human check (Joey, in the tab; then rerun --attach): ' + '; '.join(n['label'][:60] for n in hn[:3]), url)
        human_check.park(self.folder, 'workday', url, [{'question': n['label'], 'options': n.get('options')} for n in hn])
        self.log(f'human check → parked for Joey ({len(hn)}), tab kept, batch moves on')

    def section_names(self):
        """Headings of the page's sections ("Work Experience", "Education", "Resume/CV") — JSA-065."""
        try:
            return self.page.evaluate('''() => [...document.querySelectorAll('[role="group"][aria-labelledby$="-section"]')]
                .filter(g => g.getClientRects().length).map(g => { const h = document.getElementById((g.getAttribute('aria-labelledby') || '').split(' ')[0]);
                  return (h ? h.textContent : g.getAttribute('aria-labelledby')).replace(/\\s+/g, ' ').trim(); })''')
        except Exception:
            return []

    def upload_ok(self):
        return bool(self.page.locator('[data-automation-id="file-upload-successful"], [data-automation-id="fileUploadSuccess"]').count())

    def material(self, kind):
        """The folder's generated PDF: 'resume' | 'cover' (Alex_Rivera_Cover_Letter_*.pdf) or None."""
        rx = {'resume': r'resume', 'cover': r'cover[_ ]?letter'}[kind]
        pdfs = sorted(x for x in os.listdir(self.folder) if x.lower().endswith('.pdf') and re.search(rx, x, re.I))
        return pdfs[0] if pdfs else None

    def wants_cover(self):
        """JSA-068: the application asks for a cover letter — answers.json "files:cover_letter", or the JD mentions one."""
        ov = read_json(os.path.join(self.folder, 'answers.json'), {})
        if 'files:cover_letter' in ov: return bool(ov['files:cover_letter'])
        try: return bool(re.search(r'cover ?letter', open(os.path.join(self.folder, 'jd.md'), encoding='utf-8').read(), re.I))
        except Exception: return False

    def upload_files(self, files, step=''):
        """Every file field on the page gets its material (JSA-068): résumé (+ the cover letter when wanted and the input
        takes several files), a cover-letter field the cover-letter PDF; reference letters / transcripts → Joey."""
        resume, cover = self.material('resume'), self.material('cover')
        if not resume: self.problems.append('no resume PDF in the folder'); return
        for f in files:
            box = self.page.locator(f['sel']).first
            kind = file_kind(f['label'] + ' ' + (f.get('section') or ''))
            if kind in ('reference', 'transcript'):
                if f['required']:
                    self.needs.append({'step': step, 'section': f.get('section'), 'label': f['label'], 'type': 'file', 'key': f['key'],
                                       'sel': f['sel'], 'options': [], 'why': f'{kind} upload — Joey provides this document (type O)', 'no_triage': True})
                continue
            fin = box.locator('input[type="file"]').first
            try: multiple = bool(fin.evaluate('e => e.multiple'))
            except Exception: multiple = False
            names = files_for_field(kind, N(box.inner_text()), resume, cover, self.wants_cover(), multiple)
            if kind == 'cover' and not cover:
                if f['required']: self.needs.append({'step': step, 'section': f.get('section'), 'label': f['label'], 'type': 'file', 'key': f['key'],
                                                     'sel': f['sel'], 'options': [], 'why': 'cover-letter upload but no cover-letter PDF in the folder', 'no_triage': True})
                continue
            for nm in names:
                fin = self.page.locator(f['sel']).first.locator('input[type="file"]').first
                fin.set_input_files(os.path.join(self.folder, nm)); self.log(f'{"cover letter" if nm == cover else "resume"} uploaded: {nm}')
                for _ in range(40):
                    time.sleep(0.5)
                    if nm in N(self.page.locator(f['sel']).first.inner_text()): break
            if cover and cover in N(self.page.locator(f['sel']).first.inner_text()) and not self.cover_uploaded:
                self.cover_uploaded = True
                json.dump({'cover': cover, 'at': now()}, open(os.path.join(self.folder, 'uploads.json'), 'w'))

    def upload_resume(self):
        pdfs = sorted(x for x in os.listdir(self.folder) if x.lower().endswith('.pdf') and 'resume' in x.lower())
        if not pdfs: self.problems.append('no resume PDF in the folder'); return
        fin = self.page.locator('input[type="file"]').first
        fin.set_input_files(os.path.join(self.folder, pdfs[0])); self.log(f'resume uploaded: {pdfs[0]}')
        try: self.page.wait_for_selector('[data-automation-id="file-upload-successful"], [data-automation-id="fileUploadSuccess"]', timeout=20000)
        except Exception: time.sleep(4)

    def next_page(self):
        btn = self.page.locator('button[data-automation-id="pageFooterNextButton"], button[data-automation-id="bottom-navigation-next-button"]').first
        ex = self.extract(); before = ex['step']; before_keys = [f['key'] for f in ex.get('fields') or []]
        # HARD GUARD (a Workday employer 2026-10-30: a Review page titled in Chinese was not recognised and "next" = Submit was clicked):
        # this method never presses a button that submits; only the submit gate at the end of main() may do that.
        try:
            label = N(btn.inner_text(timeout=3000))
        except Exception:
            label = ''
        if SUBMIT_RX.search(label) or is_review(before):
            return False, [f'refused: the footer button is "{label or "?"}" on "{before}" — submitting is only done by the submit gate']
        for attempt in (1, 2):   # JSA-071: a Save that did not take (C&S 2026-11-02, after a terms box) → click it once more
            try: btn.click()
            except Exception as e: return False, [f'no Save and Continue button ({type(e).__name__})']
            hits = 0
            for _ in range(40):
                time.sleep(0.5)
                try:
                    ex = self.extract()
                    hits = hits + 1 if step_changed(before, before_keys, ex['step'], [f['key'] for f in ex.get('fields') or []]) else 0
                    if hits >= 2: return True, []          # the same new step on two reads: not a blink while loading
                except Exception: pass
            errs = self.errors()
            if errs: return False, errs
            if attempt == 1:
                self.log(f'  Save and Continue on "{before}" did not change the step — clicking it once more')
                try: label = N(btn.inner_text(timeout=3000))
                except Exception: label = ''
                if SUBMIT_RX.search(label) or is_review(self.extract()['step']):
                    return False, [f'refused: the footer button is now "{label or "?"}" — submitting is only done by the submit gate']
        return False, ['page did not change after Save and Continue (clicked twice)']

    def wait_for_joey_login(self, url, timeout_min=20, why=''):
        # JSA-207: the queue says WHY the automatic sign-in stopped (wd_signin.failure_code) and what Joey has to do
        wait = '(runner is waiting, continues by itself)' if timeout_min else '(role parked — rerun run_wd.py after)'
        queue(self.folder, f'WORKDAY SIGN-IN: {why} {wait}' if why else f'WORKDAY SIGN-IN: sign in / create the account in the job Chrome tab {wait}', url)
        self.log('waiting for Joey to sign in / create the account (password and account creation are his) …')
        set_status(self.folder, 'signin', 'sign in in the job Chrome tab')
        end = time.time() + timeout_min * 60
        while time.time() < end:
            time.sleep(5)
            try:
                if not self.extract()['auth']: self.log('signed in — continuing'); set_status(self.folder, 'running', 'signed in'); return True
            except Exception: pass
        return False


def education_problems(plan, profile, live=None):
    """Before leaving an experience page (JSA-032): every profile school is its own Education block, with the right degree
    level and its own GPA. A Back from Review drops all but one education entry on most tenants (#16 #75), so whatever
    Review would catch here must be caught on this page, where it can still be fixed without going Back.
    plan = this page's planned fields (kind / entry / section / label / answer); live(f) = the value now on the page."""
    live = live or (lambda f: f.get('answer'))
    edu = [f for f in plan if f.get('kind') == 'education' and f.get('entry') and f.get('status') != 'skip']
    if not edu:
        return []
    out, by_school = [], {}
    for f in edu:
        by_school.setdefault(f['entry']['School'], []).append(f)
    for e in profile.get('education', []):
        fl = by_school.get(e['School'])
        if not fl:
            out.append(f"education block missing for {e['School']}"); continue
        for f in fl:
            v = N(str(live(f) or ''))
            if re.search(r'^degree', f['label'], re.I) and v:
                if e['Degree'] == 'master' and re.search(r'under ?-?grad|bachelor|associate|high school|\bB\.?[AS]\b', v, re.I):
                    out.append(f"{e['School']}: degree is {v!r} (want a master's)")
                if e['Degree'] == 'bachelor' and re.search(r'master|post ?-?grad|doctor|ph\.?d|\bM\.?[AS]\b|MBA', v, re.I):
                    out.append(f"{e['School']}: degree is {v!r} (want a bachelor's)")
            if re.search(r'gpa|overall result|grade', f['label'], re.I) and v:
                others = {o['GPA'] for o in profile.get('education', []) if o is not e and o.get('GPA')}
                if v in others and v != (e.get('GPA') or ''):
                    out.append(f"{e['School']}: GPA {v!r} belongs to another school")
                elif e.get('GPA') and v not in (e['GPA'], 'N/A') and not v.startswith(e['GPA']):
                    out.append(f"{e['School']}: GPA {v!r} (want {e['GPA']})")
    return out


def page_canon_problems(plan, tenant):
    """The canonical audit (canon.py) on this page's own answers, before Save and Continue (JSA-032)."""
    recs = [{'label': f['label'], 'value': f['answer']} for f in plan if f.get('status') == 'ok' and isinstance(f.get('answer'), str)]
    return [f"{m['key']} = {m['value']!r} (want {m['want']})" for m in canon.audit(recs, tenant)]


def needs_answered(needs, ov, tried):
    """True when every need has an answer in ov that was not tried before (adds them to tried)."""
    vals = []
    for n in needs:
        k = n.get('answer_key') or '^' + re.escape(n['label']) + '$'
        hit = k in ov; v = ov.get(k) if hit else None
        if not hit: hit, v = ov_lookup(ov, n['label'], n.get('key'))
        if not hit or (n['label'], json.dumps(v)) in tried: return False
        vals.append((n['label'], json.dumps(v)))
    tried.update(vals)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--submit', action='store_true'); ap.add_argument('--attach')
    ap.add_argument('--url'); ap.add_argument('--cdp', default='http://127.0.0.1:9222'); ap.add_argument('--max-pages', type=int, default=12)
    ap.add_argument('--wait-min', type=float, default=20, help='minutes to wait for answers.json when Joey must answer (0 = exit at once)')
    ap.add_argument('--no-auto-signin', action='store_true', help='skip the Keychain sign-in / create-account step (Joey signs in)')
    ap.add_argument('--login-wait-min', type=float, default=20, help='minutes to wait for Joey when automatic sign-in fails (0 = stop at once; one-at-a-time batches)')
    ap.add_argument('--wait-human', action='store_true', help='wait in place (--wait-min) on a human check instead of parking it and moving on (JSA-106)')
    ap.add_argument('--keep-tab', action='store_true', help='leave the tab open when the run ends (Joey works in it right away, 2026-11-03)')
    ap.add_argument('--ds-ok', action='store_true', help='Claude spot-checked the DeepSeek answers (ds_used.json) on Review')
    ap.add_argument('--materials-gate', choices=materials_gate.MODES, default=materials_gate.DEFAULT_MODE,
                    help='material gate before the wizard and on every page: block (default) | warn (log only) | off')
    a = ap.parse_args(); t0 = time.time()
    import chrome_lock; chrome_lock.hold(f'run_wd.py {os.path.basename(os.path.normpath(a.folder))}')   # JSA-236
    from playwright.sync_api import sync_playwright
    folder = jpaths.folder(a.folder)   # as typed, else under the data home (ADR-0008)
    try: _only = json.load(open(os.path.join(folder, 'answers.json'), encoding='utf-8')).get('edu:only')
    except Exception: _only = None
    if _only:   # Joey's per-application choice when a tenant keeps one education entry (2026-10-30: 「第一条选 A」) — fill, add and check only these schools
        PROFILE['education'] = [e for e in PROFILE['education'] if e['School'] in _only]
    if os.path.exists(os.path.join(folder, 'submitted_confirmation.png')):
        set_status(folder, 'done', 'already-submitted'); print('STATUS already-submitted'); return
    meta = json.load(open(os.path.join(folder, 'wd_job.json'))) if os.path.exists(os.path.join(folder, 'wd_job.json')) else {}
    url = en_us(a.url or meta['url'])
    logf = open(os.path.join(folder, 'run_log.md'), 'a', encoding='utf-8')
    def log(m): logf.write(f'- {now()} {m}\n'); logf.flush(); print(m)
    import chrome_guard                                       # JSA-227: no autofill / password extension in the job Chrome
    if chrome_guard.stop(folder, url, log, queue, DATA, 'workday'): return
    usage = {'calls': 0, 'prompt': 0, 'out': 0}
    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp(a.cdp).contexts[0]
        cands = [p for p in ctx.pages if a.attach and a.attach in p.url]
        page = cands[-1] if cands else ctx.new_page()
        page.set_default_timeout(8000)
        try:   # the job Chrome profile prefers zh-CN; Workday follows Accept-Language (FHLB / a Workday employer 2026-10-30) → ask for English
            ctx.set_extra_http_headers({'Accept-Language': 'en-US,en;q=0.9'})
        except Exception:
            pass
        w = WD(folder, page, log)
        set_status(folder, 'running', 'start')
        log(f'start workday {"SUBMIT" if a.submit else "dry-run"} {url}')
        gate_mode = a.materials_gate
        ask = decide.deepseek_ask                               # problems go through decide.py (JSA-002 slice 2)
        mg = materials_gate.run_gate(folder, log, gate_mode, ask=ask, ats='workday')
        if gate_mode == 'block' and not mg['ok']:
            set_status(folder, 'needs-user', 'materials incomplete — see run_log.md')
            queue(folder, 'materials incomplete: ' + '; '.join((mg['next'] or mg['problems'])[:4]), url)
            log('stopped before the wizard: materials gate (block)')
            try: page.close()            # nothing to keep: the wizard never opened (Joey 2026-11-01: close tabs)
            except Exception: pass
            print('STATUS blocked'); return
        def start_apply():
            """Open the job and get into the wizard (Apply → Autofill/Manual, or Continue a saved draft)."""
            job_key = re.sub(r'^.*/job/', '', url).split('/')[-1]
            if '/apply' in page.url and job_key.split('_')[-1] in page.url:
                log('tab is already inside this application — continuing from the current page')
            else:
                page.goto(url, wait_until='domcontentloaded')
            try: page.wait_for_selector('a[data-automation-id="adventureButton"], [data-automation-id="progressBar"]', timeout=20000)
            except Exception: pass
            for sel in ('button[data-automation-id="legalNoticeDeclineButton"]', 'button:has-text("Decline")'):   # cookie banner: decline non-essential
                try:
                    if page.locator(sel).first.is_visible(): page.locator(sel).first.click(); log('cookie banner: declined'); break
                except Exception: pass
            if page.locator('a[data-automation-id="adventureButton"]').count():
                page.locator('a[data-automation-id="adventureButton"]').first.click(); time.sleep(2)
                try: page.wait_for_selector('a[data-automation-id="autofillWithResume"], a[data-automation-id="applyManually"], [data-automation-id="progressBar"]', timeout=10000)
                except Exception: pass
                for aid in ('autofillWithResume', 'applyManually'):
                    loc = page.locator(f'a[data-automation-id="{aid}"]')
                    if loc.count(): loc.first.click(); log(f'apply option: {aid}'); break
                try: page.wait_for_selector('[data-automation-id="progressBar"], input[type="password"]', timeout=15000)
                except Exception: pass
                time.sleep(1.5)
            if not page.locator('[data-automation-id="progressBar"]').count():
                # a saved draft turns "Apply" into "Continue Application" (2026-10-29, a Workday employer): the wizard is behind that link
                for sel in ('a:has-text("Continue Application")', 'button:has-text("Continue Application")',
                            '[data-automation-id="adventureButton"]:has-text("Continue")'):
                    try:
                        loc = page.locator(sel)
                        if loc.count() and loc.first.is_visible():
                            loc.first.click(); log('saved draft: clicked Continue Application'); time.sleep(3)
                            page.wait_for_selector('[data-automation-id="progressBar"]', timeout=15000)
                            break
                    except Exception:
                        continue
        start_apply()
        status = 'filled'
        for _ in range(8):                                   # the sign-in form can render seconds after the progress bar (Voya 2026-11-02)
            ex0 = w.extract()
            if ex0['auth'] or (ex0['step'] and ex0['fields']): break
            time.sleep(1.5)
        if not w.extract()['step'] and not w.extract()['auth']:
            log('not on a Workday application page (no progress bar) — handoff'); w.failed.append({'step': '', 'label': 'apply flow did not start', 'want': ''}); status = 'handoff'
        signin_why = ''
        if w.extract()['auth'] and not a.no_auto_signin:           # Joey 2026-10-30: password from the Keychain, never seen by a model
            set_status(folder, 'signin', 'automatic sign-in / create account')
            ok_si, why_si = wd_signin.auto_signin(page, log, folder, is_auth=lambda: w.extract()['auth'])
            log(f'auto sign-in: {"ok" if ok_si else "handed to Joey — " + why_si}')
            if ok_si: set_status(folder, 'running', 'signed in (automatic)')
            else: signin_why = why_si
        if w.extract()['auth'] and not w.wait_for_joey_login(url, a.login_wait_min, signin_why):
            status = 'login-timeout'
        if status != 'login-timeout' and not w.extract()['auth'] and not page.locator('[data-automation-id="progressBar"]').count():
            # some tenants land on Candidate Home after signing in (a Workday employer 2026-10-30): go back to the job and start again
            log(f'after sign-in the tab is not in the application ({page.url[:80]}) — reopening the job')
            start_apply()
            status = 'filled' if (w.extract()['step'] or page.locator('[data-automation-id="progressBar"]').count()) else 'handoff'
            if status == 'filled':
                w.failed = [x for x in w.failed if x.get('label') != 'apply flow did not start']
        if status == 'filled' and not a.no_auto_signin and in_signin_step(page):   # the wizard's own "Create Account/Sign In" step (an employer, Mets, an employer 2026-11-01)
            set_status(folder, 'signin', 'automatic sign-in inside the application')
            ok_si, why_si = wd_signin.auto_signin(page, log, folder, is_auth=lambda: w.extract()['auth'] or in_signin_step(page))
            log(f'auto sign-in (wizard step): {"ok" if ok_si else "handed to Joey — " + why_si}')
            if ok_si:
                set_status(folder, 'running', 'signed in (automatic)')
                if not page.locator('[data-automation-id="progressBar"]').count() or in_signin_step(page): start_apply()
        if status == 'filled' and ERROR_PAGE_RX.search(N(page.inner_text('body'))):
            # VSP 2026-11-03: signing in from Apply started a second application over a saved draft → "Something went wrong";
            # the job page now offers "Continue Application" (start_apply clicks it)
            log('Workday error page after sign-in (a saved draft exists?) — reopening the job to continue the draft')
            page.goto(url, wait_until='domcontentloaded'); time.sleep(3); start_apply()
        steps, tried, loops = [], set(), 0
        while status == 'filled' and len(steps) < a.max_pages and loops < a.max_pages + 10:
            loops += 1
            if page.locator(CAPTCHA_SEL).count() and any(l.is_visible() for l in page.locator(CAPTCHA_SEL).all()):
                status = 'captcha'; queue(folder, 'CAPTCHA on Workday — solve it in the job Chrome tab', url)
                human_check.park(folder, 'workday', page.url, [{}]); break
            pg = materials_gate.page_check(folder, page, w.extract().get('step') or '', log, ask, gate_mode)
            if pg is not None and gate_mode == 'block' and not pg['ok']:      # a page asks for a file we do not have
                status = 'needs-user'
                set_status(folder, 'needs-user', 'new material requirement — see run_log.md')
                queue(folder, 'materials: a Workday page asks for more: ' + '; '.join((pg['next'] or pg['problems'])[:4]) +
                      ' (the tab keeps the filled pages; rerun run_wd.py --attach after)', url)
                log('stopped on this page: new material requirement (block)'); break
            st0 = w.extract().get('step') or ''
            if joey_step(st0):                               # type O: an assessment is Joey's (Allison 2026-11-03)
                if not steps or steps[-1] != st0: steps.append(st0)
                log(f'page "{st0}": a third-party assessment / questionnaire step — handed to Joey (type O), nothing clicked')
                w.failed.append({'step': st0, 'label': f'"{st0}" is an assessment step — Joey completes it (type O); the draft keeps the filled pages', 'want': ''})
                status = 'handoff'; break
            step, plan, clean = w.do_page(usage)
            if not steps or steps[-1] != step: steps.append(step)
            log(f'page "{step}": {len(plan)} fields, clean={clean}')
            if not plan and re.search(r'experience|education|经历|經歷', step, re.I):
                # a Workday employer 2026-10-30: My Experience read as 0 fields and was passed unchecked; education / work must be verified
                time.sleep(3); step, plan, clean = w.do_page(usage)
                log(f'page "{step}" re-read: {len(plan)} fields')
                if not plan:
                    kind0 = zero_field_experience(w.section_names(), w.upload_ok(), N(page.inner_text('body')))
                    if kind0 == 'resume-only':
                        log(f'page "{step}": this tenant shows only the résumé upload (no work / education / language section) — nothing else to check')
                    elif kind0 == 'error':
                        w.failed.append({'step': step, 'want': '', 'label': 'Workday shows an error page instead of the form (old draft / expired session, JSA-065) — '
                                         'rerun fresh in a new tab; if it repeats, Joey: withdraw the draft in Candidate Home, then rerun'})
                    else:
                        w.failed.append({'step': step, 'label': '0 fields read on an experience page — not advancing unchecked', 'want': ''})
            if w.failed: status = 'handoff'; break
            if w.needs:
                if w.triage_needs(usage):                    # C: some mapped to saved facts → re-plan this page with them
                    w.needs = []; continue
                if w.human_needs() and not a.wait_human:     # JSA-106: never answered by a model; park it, next application
                    w.capture_human_answers()                  # resumed after Joey answered in the tab → his value, go on
                    if needs_answered(w.needs, read_json(os.path.join(folder, 'answers.json'), {}), tried):
                        w.needs = []; continue
                    w.park_human(page.url); status = 'captcha'; break
                if a.wait_min > 0 and w.wait_for_answers(url, tried, a.wait_min):   # A: wait for Joey instead of exiting
                    w.needs = []; continue
                status = 'needs-user'; break
            if is_review(step):
                if is_review_page(step, plan): break
                left = plan
                for _ in range(6):                             # JSA-071: the bar may say Review before the old page is gone
                    time.sleep(1.5); ex_ = w.extract(); left = ex_['fields']
                    if is_review_page(ex_['step'], left): break
                if is_review_page(w.extract()['step'], w.extract()['fields']):
                    continue                                   # re-read it as the real Review page
                log(f'page "{step}": the progress bar says Review but {len(left)} form field(s) are still on screen — the last Save did not take')
                w.failed.append({'step': step, 'label': 'progress bar says Review but the previous page is still shown (JSA-071) — rerun --attach', 'want': ''})
                status = 'handoff'; break
            # check this page against Joey's facts BEFORE leaving it: a fix later means a Back, and a Back loses schools (JSA-032)
            pre = education_problems(plan, PROFILE, lambda f: (w.field_now(f) or {}).get('value', f.get('answer'))) + page_canon_problems(plan, canon.tenant_of(url))
            if pre:
                log(f'page "{step}" not left — fix it here, no Back needed: ' + '; '.join(pre))
                for p_ in pre:
                    w.failed.append({'step': step, 'label': 'before leaving: ' + p_, 'want': ''})
                push('求职 runner：先在本页改正', os.path.basename(folder)[11:60] + f' — "{step}": ' + '; '.join(pre)[:150])
                status = 'handoff'; break
            ok, errs = w.next_page()
            if not ok:
                log(f'Workday errors on "{step}": {errs}')
                w.failed.append({'step': step, 'label': 'page errors', 'want': '', 'errors': errs}); status = 'handoff'; break
        json.dump({'url': url, 'steps': steps, 'pages': w.record, 'needs': w.needs, 'failed': w.failed, 'deepseek': usage},
                  open(os.path.join(folder, 'wd_log.json'), 'w'), indent=1, ensure_ascii=False)
        if status == 'needs-user':
            for n in w.needs: n.setdefault('answer_key', '^' + re.escape(n['label']) + '$')
            json.dump({'how': 'answers.json in this folder, then rerun run_wd.py --attach (the tab keeps the filled pages)',
                       'needs': [{k: (v[:40] if k == 'options' else v) for k, v in n.items() if k != 'sel'} for n in w.needs]},
                      open(os.path.join(folder, 'wd_needs.json'), 'w'), indent=1, ensure_ascii=False)
            queue(folder, 'Workday needs answers (runner timed out): ' + '; '.join(n['label'][:50] for n in w.needs[:6]) + ' (wd_needs.json → answers.json, rerun)', url)
        elif status == 'handoff':
            json.dump({'url': url, 'page_url': page.url, 'tab_marker': a.attach, 'fields': w.failed,
                       'how': 'Claude in Chrome fixes ONLY these fields in this tab, then rerun run_wd.py (it re-reads and continues)'},
                      open(os.path.join(folder, 'handoff.json'), 'w'), indent=1, ensure_ascii=False)
        elif status == 'filled':
            txt, prev_len = N(page.inner_text('body')), -1
            for _ in range(8):                              # Review renders section by section (RBC 2026-11-01: My Information was still empty) — wait until stable
                if len(txt) == prev_len: break
                prev_len = len(txt); time.sleep(1.5); txt = N(page.inner_text('body'))
            ap = os.path.join(folder, 'wd_answered.json')       # answers from every run of this application (resumes start mid-way)
            prev = json.load(open(ap)) if os.path.exists(ap) else {}
            prev.update({f'{s}||{l}': v for (s, l), v in w.answered.items()})
            json.dump(prev, open(ap, 'w'), indent=1, ensure_ascii=False)
            want = {k: v for k, v in prev.items() if not re.search(r'^(Education|Academic Experience|Work Experience) \d', k)}   # blocks: checked by name below
            want = {k: v for k, v in want.items() if not re.search(r'\|\|County$', k)}   # Review prints the address without the county (Regeneron 2026-10-30)
            want.update({'essential||name': jsa_profile.get('name.full'), 'essential||phone': re.sub(r'\D', '', jsa_profile.get('contact.phone') or '')[-7:]})
            # companies are essential only where the tenant has a work section (GM 2026-10-30: education + resume only)
            if any(re.match(r'(Work Experience|Work History)', k) for k in prev) or re.search(r'work (experience|history)', txt, re.I):
                want.update({f'essential||work {e["Company"]}': e['Company'] for e in PROFILE['work']})
            if any(re.match(r'Languages \d', k) for k in prev):   # every profile language where the tenant has a languages section (Voya 2026-11-02)
                for e in PROFILE['languages']:
                    hit = re.search(e['match'], txt, re.I)
                    want[f'essential||language {e["match"]}'] = hit.group(0) if hit else e['match'].split('|')[0].capitalize()
            has_edu = has_education_section(prev, txt)
            for e in (PROFILE['education'] if has_edu else []):   # schools only where the tenant has an education section (some have none, 2026-11-01)
                hit = next((n for n in [e['School']] + e.get('School_alts', []) if N(n).lower() in txt.lower()), e['School'])
                want[f'essential||school {e["School"]}'] = hit
            flat = txt.lower(); digits = re.sub(r'\D', '', txt)
            missing = []
            listed = [x.strip().lower() for x in re.findall(r'School or University\*?\n+([^\n]+)', page.inner_text('body'))]
            for sch, deg in re.findall(r'School or University\*?\n+([^\n]+)\n+Degree\*?\n+([^\n]+)', page.inner_text('body')):   # degree level next to each school, from the PAGE (a Workday employer 2026-10-30: UChicago = Undergraduate passed canon)
                for ed in jsa_profile.get('education', []):   # profile education: match_re names the school, level = master / bachelor
                    if not re.search(ed['match_re'], sch, re.I):
                        continue
                    if ed['level'] == 'master' and re.search(r'under ?-?grad|bachelor|associate|high school', deg, re.I): missing.append(f'{ed["short"]} degree on Review is "{deg}"')
                    if ed['level'] == 'bachelor' and re.search(r'master|post ?-?grad|doctor|ph\.?d', deg, re.I): missing.append(f'{ed["short"]} degree on Review is "{deg}"')
            for e in PROFILE['education']:   # each school must be an Education ENTRY, not just a word elsewhere on Review (AMAT 2026-10-30: UChicago entry gone, name still in a question)
                if listed and not any(N(n).lower() in l or l in N(n).lower() for n in [e['School']] + e.get('School_alts', []) for l in listed):
                    missing.append(f'education entry missing: {e["School"]} (Review lists {listed})')
            for k, v in want.items():
                s = str(v)
                if len(s) >= 80 or s in ('checked', ''):
                    continue
                if re.search(r'phone|mobile', k, re.I) and re.search(r'\d', s):   # the NUMBER, not "Phone Device Type: Mobile"
                    d = re.sub(r'\D', '', s)
                    if d and d[-10:] in digits:
                        continue
                    missing.append(f'{k.replace("||", " ")}: {v}'); continue
                if N(s).lower() in flat:
                    continue
                if re.search(r'\(\+1\)$', s) and '+1' in txt:    # country phone code option name vs "+1"
                    continue
                if ' | ' in s and all(N(x).lower() in flat for x in s.split(' | ')):   # multi-select: Review lists each choice on its own line (a Workday employer cities)
                    continue
                dp = date_parts(s)
                if re.fullmatch(r'[A-Za-z]+\.? \d{4}', s.strip()) and len(dp) == 2 and re.search(r'\b0?%d/\d{1,2}/%d\b' % (dp[0], dp[1]), txt):   # "December 2027" shown as 12/02/2027 (GE 2026-10-30)
                    continue
                missing.append(f'{k.replace("||", " ")}: {v}')
            if re.search(r'masters? of technology|master of business administration \(|(?<!non-)\bMBA\b', txt, re.I):   # "(non-MBA)" is fine (AMAT)
                missing.append('degree: Joey holds a Master of Science (Review shows Technology/MBA)')
            if re.search(r'x\s*447', txt): missing.append('phone extension contains the phone number')
            free_text = [f.get('label') for pg in w.record for f in pg['fields'] if f.get('type') in ('textarea', 'text')]
            for lab in eeo_left_empty(page.inner_text('body'), free_text):   # real EEO questions only, not a free-text box that lists categories (JSA-206)
                missing.append(f'EEO question left empty on Review: "{lab[:70]}" (2026-10-30)')
            if re.search(r'minor outlying islands', txt, re.I):     # HPE 2026-10-30: '^united states' picked the islands
                missing.append('country: Review shows United States Minor Outlying Islands (want United States of America)')
            # canonical audit (canon.py): the answers we recorded against Joey's facts, independent of the plan
            recs = [{'label': k.split('||', 1)[-1], 'value': v} for k, v in prev.items()
                    if not k.startswith('essential||') and isinstance(v, str)]
            cbad = canon.audit(recs, canon.tenant_of(url))
            json.dump(cbad, open(os.path.join(folder, 'canon.json'), 'w'), indent=1, ensure_ascii=False)
            if cbad:
                w.problems.extend(canon.block(cbad))          # a wrong answer is not a "Review lacks" item
                log('canonical audit FAILED: ' + '; '.join(f"{m['key']}={m['value']!r}" for m in cbad))
            page.screenshot(path=os.path.join(folder, 'filled_check.png'), full_page=True)
            reasons = []
            if not is_review(steps[-1] if steps else ''): reasons.append('did not reach the Review page')
            if missing: reasons.append('review page lacks: ' + '; '.join(missing[:6]))
            if w.problems: reasons.append('problems: ' + '; '.join(w.problems))
            if not a.submit: reasons.append('dry-run')
            if not approved_for(folder): reasons.append('batch not approved')
            ds_all = read_json(os.path.join(folder, 'ds_used.json'), [])
            if ds_all and not a.ds_ok: reasons.append(f'{len(ds_all)} DeepSeek answer(s) to spot-check (ds_used.json; rerun with --ds-ok)')
            json.dump({'pass': not missing and bool(steps) and is_review(steps[-1]), 'missing_on_review': missing,
                       'deepseek_answers': [{k: u.get(k) for k in ('kind', 'label', 'answer', 'source_fact', 'wanted')} for u in ds_all],
                       'checked_at': now()}, open(os.path.join(folder, 'verify.json'), 'w'), indent=1, ensure_ascii=False)
            if reasons:
                log('NOT submitted: ' + ' | '.join(reasons)); status = 'dry-run' if not a.submit else 'blocked'
                if a.submit: queue(folder, 'not submitted: ' + ' | '.join(reasons), url)
            else:
                page.locator('button[data-automation-id="pageFooterNextButton"]').first.click(); log('submit clicked')
                ok = False
                for _ in range(60):
                    time.sleep(0.5)
                    t = page.inner_text('body')
                    if DONE_RE.search(t) or '/userHome' in page.url: ok = True; break
                if ok:
                    page.screenshot(path=os.path.join(folder, 'submitted_confirmation.png'), full_page=True); status = 'submitted'
                    log('CONFIRMED | ' + page.url)
                    with open(os.path.join(folder, 'application_record.md'), 'a', encoding='utf-8') as rec:
                        rec.write(f"\n## Submitted by run_wd.py {now()}\n- URL: {url}\n- Pages: {' → '.join(steps)}\n- Review-page check: pass\n- Confirmation: submitted_confirmation.png\n- Details: wd_log.json\n")
                else:
                    status = 'unconfirmed'; page.screenshot(path=os.path.join(folder, 'after_submit.png'), full_page=True)
                    queue(folder, 'clicked Submit but no confirmation seen — see after_submit.png', url)
        set_status(folder, FINAL_STATE.get(status, status), f'{status} · needs {len(w.needs)} · failed {len(w.failed)} · DS calls {usage["calls"]}')
        log(f'STATUS {status} · pages {" → ".join(steps)} · needs {len(w.needs)} · failed {len(w.failed)} · DeepSeek {usage}')
        os.makedirs(DATA, exist_ok=True)
        with open(os.path.join(DATA, 'results.jsonl'), 'a') as out:
            out.write(json.dumps({'at': now(), 'folder': os.path.basename(folder), 'url': url, 'ats': 'workday', 'status': status,
                                  'steps': steps, 'needs': len(w.needs), 'failed': len(w.failed), 'deepseek': usage,
                                  'secs': round(time.time() - t0, 1)}) + '\n')
        if status == 'submitted':        # JSA-014: Applied row in data/store + queue lines ticked, no hand edit
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'scripts', 'store'))
            import sync_results; sync_results.sync_folder(folder, log)
        if status != 'captcha': human_check.resolve(folder, status)
        if tab_should_close(status) and not a.keep_tab:     # Joey 2026-10-28 / 2026-11-01: close the page when the application ends (memory); --keep-tab: Joey acts in it now
            try: page.close()
            except Exception: pass
        print('STATUS', status); print(f'TIME {round(time.time() - t0, 1)}s')


if __name__ == '__main__':
    main()
