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
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import argparse, json, os, re, sys, time
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import datetime, timedelta, timezone
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
import canon
import ladder
import plan_build as PB
import materials_gate, decide, wd_signin, human_check
import field_limits as FL  # JSA-312: the box's own length / format limits
from run import approved_for, queue, now, DATA, CAPTCHA_SEL

PAGE_JS = open(os.path.join(HERE, 'wd_page.js'), encoding='utf-8').read()
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077: personal facts in config/)
PROFILE = json.load(open(jsa_profile.data_file('wd_profile.json', 'JSA_WD_PROFILE'), encoding='utf-8'))   # Workday blocks (work / education / languages)
DONE_RE = re.compile(r'(application (was |has been )?submitted|thank you for (applying|your application)|successfully submitted|'
                     r'we have received your application|congratulations)', re.I)


def norm_step(name):
    """Pure (tested, JSA-392). A progress-bar step name normalised: the screen-reader prefix ("current step 3 of 6") out, spaces collapsed, lower case."""
    t = re.sub(r'^\s*(?:current|completed)?\s*step\s+\d+\s+of\s+\d+\s*', '', str(name or ''), flags=re.I)
    return re.sub(r'\s+', ' ', t).strip().lower()


def checkpoint_update(cp, step, at):
    """Pure (tested). The checkpoint after `step` was saved: {'done': [normalised names in save order, no duplicates], 'at'}; `cp` is not changed."""
    done = list((cp or {}).get('done') or [])
    n = norm_step(step)
    if n and n not in done: done.append(n)
    return {'done': done, 'at': at}


def resume_target(done, bar):
    """Pure (tested). The progress-bar entry to jump to on a rerun: the first application page that is not saved yet; None when nothing
    is saved, everything is saved, or that page is the first one anyway (nothing would be skipped). Sign-in / account steps are not pages."""
    saved = {norm_step(x) for x in done or []}
    pages = [b for b in bar or [] if not re.match(r'(create account|sign ?-?in)', norm_step(b))]
    if not saved:
        return None
    for i, b in enumerate(pages):
        if norm_step(b) not in saved:
            return b if i > 0 else None
    return None


def bar_steps(page):
    """The progress bar's step names in bar order ([] when it has none)."""
    try:
        return [re.sub(r'\s+', ' ', x.inner_text(timeout=2000)).strip() for x in page.locator('[data-automation-id="progressBar"] li').all()]
    except Exception:
        return []


def jump_to_step(page, name, log, wait=8):
    """Click the progress-bar step `name` and wait for it to become the active step. True when it did; False → the caller walks every page."""
    try:
        for item in page.locator('[data-automation-id="progressBar"] li').all():
            if norm_step(item.inner_text(timeout=2000)) == norm_step(name):
                item.click(timeout=3000)
                end = time.time() + wait
                while time.time() < end:
                    time.sleep(0.3)
                    act = page.locator('[data-automation-id="progressBarActiveStep"]')
                    if act.count() and norm_step(act.first.inner_text(timeout=2000)) == norm_step(name): return True
                log(f'resume: clicked "{name}" but the page did not move — walking every page')
                return False
        log(f'resume: no progress-bar step "{name}" — walking every page')
    except Exception as e:
        log(f'resume: jump failed ({type(e).__name__}) — walking every page')
    return False


def should_jump(current, target, bar):
    """Pure (tested, JSA-392 review). Only FORWARD: the target must come after the current page in the bar. A jump back (a checkpoint that lags the tab —
    Joey saved a page himself, a crash between the save and the checkpoint) would make the forward pass save an already saved page again
    (My Experience → the second school is lost, JSA-032). Unknown names → False."""
    names = [norm_step(b) for b in bar or []]
    c, t = norm_step(current), norm_step(target)
    return c in names and t in names and names.index(t) > names.index(c)


def load_checkpoint(folder):
    try:
        with open(os.path.join(folder, 'checkpoint.json'), encoding='utf-8') as f: d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get('done', []), list) else {}
    except (OSError, ValueError):
        return {}


def _write_json(p, obj):
    with open(p + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(p + '.tmp', p)


def save_checkpoint(folder, cp):
    _write_json(os.path.join(folder, 'checkpoint.json'), cp)


def clear_checkpoint(folder):
    try: os.remove(os.path.join(folder, 'checkpoint.json'))
    except OSError: pass


def merge_answered(folder, answered):
    """(tested, JSA-392 review) Persist this run's page answers into wd_answered.json (merged with earlier runs) as soon as a page is saved — a run that
    stops before Review used to lose them, and a resume that skips the page then has nothing to check that page against on Review."""
    ap = os.path.join(folder, 'wd_answered.json')
    try:
        with open(ap, encoding='utf-8') as f: prev = json.load(f)
        if not isinstance(prev, dict): prev = {}
    except (OSError, ValueError):
        prev = {}
    prev.update({f'{s}||{l}': v for (s, l), v in (answered or {}).items()})
    _write_json(ap, prev)
    return prev


def wd_already_submitted(folder):
    """(tested, JSA-306) The folder's application went through: a confirmation page shot, or — when only the company e-mail confirmed it —
    the "## Submitted by run_wd.py" section in application_record.md. A rerun must never click Submit again."""
    if os.path.exists(os.path.join(folder, 'submitted_confirmation.png')): return True
    try: return bool(re.search(r'^## Submitted by run_wd\.py', open(os.path.join(folder, 'application_record.md'), encoding='utf-8').read(), re.M))
    except OSError: return False


def wd_mail_receipt(meta, since, wait, waiter, log):
    """(tested, JSA-306) After Submit with no confirmation on the page: the company's application-received e-mail (Gmail, read-only)
    is the second proof. → its subject, or None (no wait, no company, no mail, any mail error — never raises)."""
    if not wait: return None
    company = str((meta or {}).get('company') or '').strip()
    if not company:
        log('no company name in wd_job.json — cannot look for the receipt e-mail'); return None
    try:
        log(f'no confirmation on the page — waiting up to {wait}s for the {company} receipt e-mail (Gmail read-only)')
        subj = waiter(since - timedelta(seconds=30), company, timeout=wait)
        return subj if subj and str(subj).strip() else None
    except BaseException as e:
        log(f'e-mail check failed: {type(e).__name__} {str(e)[:100]}'); return None


def wd_done(before, after):
    """Pure (tested). (confirmed, why) after Submit on the Review page (JSA-299): the page changed (the footer Submit
    button gone or the URL changed) and shows a new success sentence, or it moved to the candidate home (/userHome) or …/jobTasks/completed/application (every past confirm)."""
    import confirm_page as CP
    return CP.judge(before, after, done_re=DONE_RE, extra=lambda s: bool(re.search(r'/userHome|/jobTasks/completed/', str(s.get('url') or ''))))
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


def degree_full(o):
    """Pure. "M.S. - Master of Science" → "Master of Science" (the full name after an abbreviation prefix, canon.abbr_rest;
    Vanguard 2026-11-10 ranked every prefixed option the same, so page order picked "M.S.T. - … in Taxation", JSA-282)."""
    t = str(o or '').strip()
    m = canon.ABBR_RX.match(canon.norm(t))
    return t[len(t) - len(m.group(2)):].strip() if m and canon.abbr_rest(canon.norm(t)) else t


def degree_rank(o):
    """Master options, best first: "Master of Science" / "M.S." → a plain "Master's (Degree)" / "Masters" → "Master of
    Science in <his field>" → any other. A "… in <another field>" option never gets here (master_options drops it)."""
    t = degree_full(o)
    if re.search(r'^master\S* (of|in) science in\b|^m\.?s\.?c?\.? in\b', t, re.I): return 2
    if re.search(r'\bor\b', t, re.I): return 3                               # combined options rank last
    if re.search(r'^master\S* (of|in) science\b|^M\.?S\.?c?\.?$|^M\.?S\.? degree$', t, re.I): return 0
    if re.search(r"^masters?'?s?( degree)?( \(.*\))?$|^master'?s?'? degree$|^graduate degree", t, re.I): return 1
    return 3


def master_options(opts):
    """Pure (tested): his master's options from a Degree list, best first (degree_rank); specialty masters and MBA-only dropped."""
    is_mba_only = lambda o: bool(re.search(r'\bMBA\b|business admin', o, re.I)) and not re.search(r'science', o, re.I)
    rx = r'master|^m\.?s\.?c?\.?( degree)?$|^m\.?s\.?c?\.? in\b|^m\.?a\.?$|^ms\b|^msc\b|^graduate degree$'
    out = [o for o in (opts or []) if re.search(rx, o.strip(), re.I) and not is_mba_only(o) and not degree_special(o)
           and canon.degree_field_ok(o)]
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


def LEVEL_BACHELOR(t):
    """Pure. A plain bachelor's option worded as a level: "bachelor" plus only filler words (level, degree, year(s), 4, four, undergraduate; the lone letters "s" of "Bachelor's" and "a")."""
    w = re.findall(r"[a-z0-9]+", str(t or '').lower())
    return any(x in ('bachelor', 'bachelors') for x in w) and all(x in ('bachelor', 'bachelors', 's', 'level', 'degree', 'year', 'years', '4', 'four', 'a', 'undergraduate') for x in w)


def bachelor_options(opts):
    """Pure (tested): his bachelor's (B.A. Economics, UIUC) options from a Degree list, best first: "Bachelor of Arts" /
    "B.A." → a plain "Bachelor's (Degree)" / "Bachelors" → a combined option naming Arts; a Bachelor of Science alone is never his. Specialty
    bachelor's (fine arts, music, nursing, engineering, BBA, …) dropped (a Workday employer "Bachelor of Fine Arts" 2026-11-01)."""
    rx = r'bachelor|^b\.?s\.?$|^b\.?a\.?$|^b\.?a\.? in\b|baccalaureate'
    out = [o for o in (opts or []) if re.search(rx, o.strip(), re.I) and not BACHELOR_SPECIAL.search(o) and canon.degree_field_ok(o)]
    def rank(o):
        t = degree_full(o)
        if re.search(r'^bachelor\S* (of|in) arts in\b|^b\.?a\.? in\b', t, re.I): return 1
        if re.search(r'\bor\b', t, re.I): return 2
        if LEVEL_BACHELOR(t): return 1   # JSA-327: "Bachelor's Level Degree" (Micron), "4-year Degree (Bachelor's)" (Entrust)
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
    if any(re.match(r'(Education|Academic Experience|Schools? Attended) \d', str(k)) for k in (answered_keys or [])):
        return True
    return bool(re.search(r'\beducation\b|academic experience|school or university|schools? attended', review_text or '', re.I))


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


def skill_items(label, answer):
    """Pure (tested, JSA-372). The skills box ("Type to Add Skills") takes ONE skill per search: a qa answer listing several
    ("Python, SQL, R" / "Python | SQL") → the separate skills, in order, no duplicates. Any other field / a single value → [answer]."""
    ans = str(answer or '').strip()
    if not re.search(r'skill', str(label or ''), re.I) or not re.search(r',|\||;', ans): return [ans] if ans else []
    out = []
    for x in re.split(r'\s*(?:\||,|;)\s*', ans):
        if x.strip() and x.strip().lower() not in {y.lower() for y in out}: out.append(x.strip())
    return out


def skills_present(chips, items):
    """Pure (tested, JSA-372). Is every wanted skill among the chips the box shows (' | '-joined)? A chip may carry the tenant's
    qualifier ("Python (Programming Language)"); the skill itself must match whole, never as a part of another ("R" ≠ "Rust")."""
    have = [re.sub(r'\s*\(.*?\)\s*$', '', c).strip().lower() for c in str(chips or '').split(' | ') if c.strip()]
    have += [c.strip().lower() for c in str(chips or '').split(' | ') if c.strip()]
    return bool(items) and all(str(i).strip().lower() in have for i in items)


def reread_empty_page(read, tries=3, wait=3, sleep=time.sleep):
    """Tested (JSA-371). A page that reads 0 fields right after a rerun / attach is usually still rendering (Midland 11-01, a Workday employer
    11-12: "My Information: 0 fields" → "no Save and Continue button"). Wait and read it again, up to `tries` times, until it has
    fields. read() → (step, fields); returns the last read and how many re-reads it took. Only a read-only read belongs here: do_page also uploads
    the résumé, so the caller never passes it."""
    out = read(); n = 0
    while not out[1] and n < tries:
        sleep(wait); out = read(); n += 1
    return out, n


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


def joey_step_result(step):
    """Pure (tested, JSA-374). What a run records when it stops on a third-party assessment step (type O): its own status
    'assessment' (a task for Joey, state needs-user — not a failure, no handoff.json, no failed entry) and the queue line that
    says what to do. The draft keeps the filled pages; he takes the assessment in the tab, then the run is resumed."""
    st = re.sub(r'^current step \d+ of \d+\s*', '', str(step or ''), flags=re.I).strip() or 'assessment'
    return {'status': 'assessment', 'state': 'needs-user',
            'note': f'JOEY TASK: "{st}" is a third-party assessment — open the saved draft (Continue Application; the tab is closed after the run, the draft keeps the filled pages) and take it, '
                    f'then rerun run_wd.py to continue; the runner did not click it (type O, not a failure)'}


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
    return ('languages' if re.search(r'language', section, re.I) else 'education' if re.search(r'educat|academic|\bschools?\b', section, re.I)
            else 'work' if re.search(r'work|experience|employment', section, re.I) else None)


def blocks_of(fields, kind):
    """Pure (tested). The number of numbered repeat blocks ("Schools Attended 2") of one kind among a page's fields."""
    return len({f.get('section') for f in fields or [] if re.search(r'\d+\s*$', f.get('section') or '') and block_kind_of(f.get('section')) == kind})


def zero_rejected(errs, fields):
    """Pure (tested). Workday page errors "The field <Q> is required and must have a value." on a box we filled with 0 → those
    fields. The box keeps digits only and the tenant counts 0 as empty (BCBS NE current salary 11-10, JSA-272): no true number
    fits, so it goes to Joey instead of a generic page failure."""
    out = []
    for e in errs or []:
        m = re.search(r'field (.+?) is required and must have a value', re.sub(r'\s+', ' ', str(e)), re.I)
        if not m: continue
        q = re.sub(r'\s+', ' ', m.group(1)).strip().lower()
        f = next((f for f in fields or [] if re.sub(r'\s+', ' ', str(f.get('label') or '')).strip().lower() == q
                  and re.fullmatch(r'0+(\.0+)?', str(f.get('answer') or '').strip())), None)
        if f: out.append(f)
    return out


def filled_but_rejected(errs, fields):
    """Pure (tested). Workday page errors "The field <Q> is required and must have a value." on a text box we DID fill with a real
    answer (Micron Self Identify 11-11, JSA-369: Name = "<the profile name>" read back, page still says required — the value was in the
    box, not in the form's state, or the error was stale). Those fields: they get typed in again, key by key, then Save once more.
    Zero answers belong to zero_rejected(); fields we left empty are not here."""
    out = []
    for e in errs or []:
        m = re.search(r'field (.+?) is required and must have a value', re.sub(r'\s+', ' ', str(e)), re.I)
        if not m: continue
        q = re.sub(r'\s+', ' ', m.group(1)).strip().lower()
        f = next((f for f in fields or [] if re.sub(r'\s+', ' ', str(f.get('label') or '')).strip().lower() == q
                  and f.get('type') in ('text', 'textarea') and f.get('status') == 'ok'
                  and str(f.get('answer') or '').strip() and not re.fullmatch(r'0+(\.0+)?', str(f.get('answer')).strip())), None)
        if f: out.append(f)
    return out


# JSA-370: well-known short names for schools — general alias table, applied only when the profile's own school matches the
# pattern (never a guess about a school the user did not list). Workday's search matches word starts, so a tenant that lists
# "University of Illinois Urbana-Champaign" under another spelling answers to a shorter query.
SCHOOL_ALIAS_TABLE = [
    (r'illinois.*urbana|urbana.*champaign|\buiuc\b',
     ['UIUC', 'University of Illinois at Urbana-Champaign', 'University of Illinois - Urbana-Champaign', 'Illinois Urbana-Champaign', 'Urbana-Champaign']),
    (r'^(the )?university of chicago$|\buchicago\b', ['UChicago', 'The University of Chicago']),
]
_SCHOOL_STOP = {'of', 'at', 'the', 'and', 'in'}


def _school_key(s):
    return frozenset(w for w in re.findall(r'[a-z0-9]+', str(s or '').lower()) if w not in _SCHOOL_STOP)


def school_queries(school, alts=()):
    """Pure (tested). Names to search a Workday school list with, in order: the facts' name, its tenant spellings (School_alts),
    then the general alias table's names for that school, then the name without a leading "University of". No duplicates."""
    out = []
    names = [school] + list(alts or [])
    for rx, al in SCHOOL_ALIAS_TABLE:
        if any(re.search(rx, n or '', re.I) for n in names): names += al
    for n in names:
        if n and n.strip().lower() not in {x.lower() for x in out}: out.append(n.strip())
    return out


def same_school(option, names):
    """Pure (tested). Is a tenant's option one of these names? Same words in any order, ignoring "of / at / the" and punctuation
    ("University of Illinois - Urbana Champaign" = "...at Urbana-Champaign"); 'University of Illinois Chicago' is another school."""
    k = _school_key(option)
    return bool(k) and any(k == _school_key(n) for n in names)


def pick_by_prefs(opts, prefs):
    """Deterministic pick from the COMPLETE option list along the ordered preference list.

    Joey 2026-10-28: the model must not have discretion over this order (it picked "Statistics"
    while CS/IS options were on the list). Per preference, in order: exact, else the CLOSEST of the
    substring / all-tokens candidates (JSA-283: fewest words apart — "Computer Science" → "Computer and
    Information Science", not "Computer Sciences, Technology, or Business"; "Information Systems" matches
    "Management Information Systems"). The first preference that matches anything wins, so a lower
    preference can never jump the queue.
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
        pt = toks(pn)
        cand = []                                            # 2 substring / 3 every token present — then the CLOSEST wins (JSA-283)
        for o, on in pairs:
            if pn in on or (on in pn and len(toks(on)) >= 2) or (pt and pt <= toks(on)):   # a bare "Science" is not "Data Science" (Central Hudson 2026-11-01)
                cand.append((len(pt ^ toks(on)), len(cand), o))
        if cand:                                             # "Computer and Information Science" (1 word apart) before "Computer Sciences, Technology, or Business" (4)
            return min(cand)[2]
    return None


def prompt_queries(want):
    """Pure (tested, JSA-283). The search texts a Workday prompt is tried with, in order: the wanted text, its head before a comma /
    bracket / colon, its first two words, its first word, then '' (no search — scroll the whole list). A long text with commas
    (Vanguard "Computer Sciences, Technology, or Business") is not always found by the full string."""
    w = re.sub(r'\s+', ' ', str(want or '')).strip()
    out = [w]
    head = re.split(r'[,(:;/]', w, maxsplit=1)[0].strip() if re.search(r'[,(:;/]', w) else ''
    if len(head) >= 3: out.append(head)
    words = [x for x in (re.sub(r'[^\w]', '', y) for y in w.split()) if x]
    if len(words) >= 2: out.append(' '.join(words[:2]))
    if words and len(words[0]) >= 4: out.append(words[0])
    out.append('')
    seen, res = set(), []
    for q in out:
        if q.lower() not in seen: seen.add(q.lower()); res.append(q)
    return res


SCROLL_FIND_JS = '''async (want) => {
  const norm = s => String(s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const stop = new Set(['of', 'at', 'the', 'and', 'in']);       // JSA-370: want may be {names:[...]} for a school (same words, any order)
  const key = s => [...new Set(String(s || '').toLowerCase().match(/[a-z0-9]+/g) || [])].filter(w => !stop.has(w)).sort().join(' ');
  const wantKeys = want && want.names ? want.names.map(key) : null;
  const isWant = t => wantKeys ? wantKeys.includes(key(t)) : t === norm(want);
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
      if (isWant(t)) { x.setAttribute('data-cx-opt', '1'); x.scrollIntoView({ block: 'center' }); return { hit: true, seen: [], text: x.textContent.trim() }; } }
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


def unplanned_fields(planned_keys, fields):
    """Pure (tested, JSA-273). Fields on the page now that the page plan never saw (rendered after it was read) → their
    labels. Files and unlabeled fields are ignored. planned_keys None = no plan known → []."""
    if planned_keys is None: return []
    return [f.get('label') for f in fields or [] if f.get('key') not in planned_keys and f.get('type') != 'file' and (f.get('label') or '').strip()]


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
               'filled': 'review', 'assessment': 'needs-user'}


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
US_STATES = {'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA', 'colorado': 'CO',
             'connecticut': 'CT', 'delaware': 'DE', 'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI',
             'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA',
             'maine': 'ME', 'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
             'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
             'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
             'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD',
             'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
             'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'}


def state_on_review(value, txt):
    """A State answer ("Illinois") shown on Review as its postal code inside the address line ("<City>, <ST> <ZIP>"):
    ', <CODE> <5-digit zip>' or ', <CODE>' at a line end. Pure (tested)."""
    code = US_STATES.get(re.sub(r'\s+', ' ', str(value or '')).strip().lower())
    if not code:
        return False
    return bool(re.search(r',\s*' + code + r'(\s+\d{5}(-\d{4})?\b|\s*$)', str(txt or ''), re.M))


def expand_review(page):
    """Click every "MORE (n)" toggle on the Review page so folded multi-select answers are in the text (RGA 11-10)."""
    for _ in range(6):
        try:
            more = page.locator('button, [role="button"], a').filter(has_text=re.compile(r'^\s*\+?\s*more\s*\(\d+\)\s*$', re.I))
            if not more.count():
                return
            more.first.click(); time.sleep(0.5)
        except Exception:
            return


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



def box_limits(f):
    """Pure (tested, JSA-312). A Workday text box's limits: maxlength / minlength / pattern attributes, its hint text, a url
    label or type=url (field_limits)."""
    if f.get('type') not in ('text', 'textarea'):
        return None
    lim = FL.merge({'max': f.get('maxlength'), 'min': f.get('minlength'), 'pattern': f.get('pattern') or None,
                    'format': 'url' if FL.url_box(f.get('label') or '', f.get('input_type')) else None, 'source': 'the box'},
                   FL.limits_from_text(f.get('hint') or ''))
    return lim if (lim['max'] or lim['min'] or lim['format'] or lim['pattern']) else None


def limit_gate(plan, step):
    """Pure (tested, JSA-312). Planned text answers that break the box's own limits (too long — Workday cuts it; too short;
    not a full http(s) address; the page's pattern) → status needs_user (required) / skip (optional), never typed in.
    Returns (plan, needs) with needs in self.needs' shape."""
    out, needs = [], []
    for f in plan:
        lim = box_limits(f) if f.get('status') == 'ok' and f.get('answer') not in (None, '', 'SOURCE_AUTO') else None
        if lim and isinstance(f.get('answer'), str):
            fx = FL.fix_url(f['answer'], lim, f.get('label') or '', f.get('input_type'))   # a bare address in a url box → https://
            if fx != f['answer']:
                f = dict(f, answer=fx, source=f"{f.get('source')} + https:// (the box wants a full address)")
        bad = FL.check(str(f['answer']), lim, f.get('label') or '') if lim else None
        if not bad:
            out.append(f); continue
        why = f"the answer breaks the box's limit — {FL.why(bad, f['answer'], lim)}"
        out.append(dict(f, status='needs_user' if f.get('required') else 'skip', source=why, limit_fail=bad))
        if f.get('required'):
            needs.append({'step': step, 'section': f.get('section'), 'label': f['label'], 'options': f.get('options') or [],
                          'type': f['type'], 'key': f['key'], 'sel': f.get('sel'), 'why': why, 'no_triage': True})
    return out, needs


def record_field(f):
    """Pure (tested, JSA-320). One field as wd_log.json keeps it. `page` = what the page holds after the fill (the read-back)
    and `before` = what it held when the page was first read (often the résumé parse). Until 2026-11-11 only `value`, the
    before-fill value, was kept, so the audit and the replays took the résumé parse (UIUC GPA 3.85, "Job Searching
    Agent") as the submitted answer. A field the runner did not fill (keep / skip / needs_user) holds its first value."""
    out = {k: f.get(k) for k in ('label', 'section', 'type', 'required', 'answer', 'status', 'source')}
    out['before'] = f.get('value')
    out['page'] = f['readback'] if 'readback' in f else f.get('value')
    out['value'] = out['page']
    if 'readback_ok' in f:
        out['ok'] = bool(f['readback_ok'])
    return out

class WD:
    def __init__(self, folder, page, log):
        self.folder, self.page, self.log = folder, page, log
        self.VERIFY_SRC = ''                   # ladder compatibility; we use check_one instead
        self.problems, self.needs, self.failed, self.record = [], [], [], []
        self.replanned, self.planned_keys = set(), None    # JSA-273: steps read again because fields rendered late
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
        last, same = -1, 0
        for _ in range(tries):
            info = self.extract(); n = len(info['fields'])
            same = same + 1 if n and n == last else 0
            if same >= 2: return info                       # the same count on 3 reads (~1.4 s): NCR Voluntary Disclosures showed 1 of 5 fields for 0.7 s (JSA-273)
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
            return g.filter(has_text=re.compile('Work|Employment|Experience', re.I)).filter(has_not_text=re.compile('Educat|Academic|School or University|Schools? Attended|Fluent', re.I)).first
        if kind == 'languages':
            return g.filter(has_text=re.compile('Language', re.I)).filter(has_not_text=re.compile('Educat|Academic|School or University|Job Title', re.I)).first
        return g.filter(has_text=re.compile('Education|Academic|Schools? Attended', re.I)).first   # an employer 11-10 (JSA-270)

    def block_kind(self, section):
        return ('languages' if re.search(r'language', section, re.I) else 'education' if re.search(r'educat|academic|\bschools?\b', section, re.I)
                else 'work' if re.search(r'work|experience|employment', section, re.I) else None)   # "Academic Experience N" is education (KBR, Ryan 2026-11-01)

    def block_entry(self, section, fields_in_block, used):
        """Work Experience N / Education N → the N-th profile entry (résumé order; Workday autofill keeps it).
        Languages N → the entry whose name matches the block's Language value. No entry → None (block is deleted)."""
        kind = ('languages' if re.search(r'language', section, re.I) else 'education' if re.search(r'educat|academic|\bschools?\b', section, re.I)
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
            if re.search(r'comprehension|overall|reading|speaking|writing|listening|proficien|^all$', lab, re.I):
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
        out, blocks, used, qa_try = [], {}, set(), []
        for f in fields:
            if f['section'] and block_kind_of(f['section']) and re.search(r'\d+\s*$', f['section']):   # same kinds as block_kind ("Schools Attended N" was answered as plain questions: NCR 14 UChicago blocks, JSA-272)
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
                    nods = f.pop('_no_ds', False)
                    for name, ov in (('answers.json', ovj),) + ((() if nods else (('ds_answers.json', ovd),))):
                        hit, v = ov_lookup(ov, f['label'], f['key'])
                        if hit and v:
                            if name == 'ds_answers.json' and (kind == 'languages' or f['options']): f['_ds'] = v; break   # JSA-337: qa first; PB.build below reads ds_answers.json itself, only when the rules cannot answer. (Boxes without options never reach qa_try, so the cache still wins there.)
                            a, src = v, name; break
                if a is None and not nods and (kind == 'languages' or f['options']): qa_try.append(f); continue   # JSA-365: the qa rules before Joey (a Greenhouse employer ePro Listening… = qa 274–278)
                if a is None:
                    if f['required'] and not f['value']:
                        self.needs.append({'step': step, 'section': sec, 'label': f['label'], 'options': f['options'], 'type': f['type'],
                                           'key': f['key'], 'sel': f['sel'], 'why': 'not in wd_profile'})
                    out.append(dict(f, status='keep', source='page'))
                else:
                    out.append(dict(f, answer=a, status='ok', source=src, alts=f.get('alts', []), entry=e, kind=kind))
        if qa_try:                                         # JSA-365: what the profile could not answer → the qa rules (never a company / school shared label: those carry _no_ds)
            pq = PB.build(self.folder, [{'key': f['key'], 'label': f['label'], 'type': {'select': 'combo', 'prompt': 'combo'}.get(f['type'], f['type']),
                                         'required': f['required'], 'options': f['options'], 'sel': f['sel']} for f in qa_try], self.page.url if self.page else '', 'workday')
            byq = {p['key']: p for p in pq['fields']}
            for f in qa_try:
                p = byq.get(f['key']) or {}
                if p.get('status') == 'ok':
                    out.append(dict(f, answer=p['answer'], status='ok', source=p.get('source') or 'qa', alts=f.get('alts', []), entry=assign.get(f['section']), kind=kinds.get(f['section'])))
                    continue
                if f['required'] and not f['value']:
                    self.needs.append({'step': step, 'section': f['section'], 'label': f['label'], 'options': f['options'], 'type': f['type'],
                                       'key': f['key'], 'sel': f['sel'], 'why': 'not in wd_profile'})
                out.append(dict(f, status='keep', source='page'))
        for f in fields:                                   # phone extension: always empty (10-28: the number went into it)
            if f['key'] not in handled and re.search(r'extension', f['label'], re.I) and f['type'] == 'text':
                handled.add(f['key']); out.append(dict(f, answer='', status='ok', source='no extension'))
            elif f['key'] not in handled and (re.search(r'middleName', f.get('aid') or '') or re.search(r'^(preferred )?middle name$', f['label'], re.I)):
                handled.add(f['key']); out.append(dict(f, answer='', status='ok', source='no middle name (Workday shows it inside the name)'))
            elif f['key'] not in handled and re.search(r'preferredName--lastName', f.get('aid') or ''):
                handled.add(f['key']); out.append(dict(f, answer=jsa_profile.get('name.last') or '', status='ok', source='preferred last name'))
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
                elif f['value'] and not f['required'] and not p.get('no_auto'):
                    out.append(dict(f, status='keep', source='page'))
                elif f['value'] and f['required'] and not p.get('no_auto'):   # no_auto: Joey answers it, not the tenant's prefill (JSA-361)
                    out.append(dict(f, status='keep', source='page (prefilled)'))    # e.g. email from the account
                else:
                    if f['required']:
                        self.needs.append({'step': step, 'section': f['section'], 'label': f['label'], 'options': f['options'], 'type': f['type'],
                                           'key': f['key'], 'sel': f['sel'], 'why': p.get('source') or 'no rule',
                                           'no_triage': bool(p.get('no_triage'))})   # a rule said "Joey decides" (JSA-105) → no DeepSeek triage
                    out.append(dict(f, status='needs_user' if f['required'] else 'skip', source=p.get('source')))
        out, needs = limit_gate(out, step)                 # JSA-312: an answer the box's own limits refuse is never typed in
        for n in needs:
            self.needs.append(n); self.log(f"  {step} | {n['label'][:50]}: {n['why']}")
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
            if f.get('_typed'):                              # JSA-369: the page says "required" on a box that shows the value → type it key by key
                el.click(); el.fill(''); p.keyboard.type(ans, delay=40); el.press('Tab')
            else:
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
            items = skill_items(f['label'], ans)
            if len(items) > 1 and not f.get('_one_of'):      # JSA-372: several skills in one answer → one search + pick each, none removed
                base = lambda c: re.sub(r'\s*\(.*?\)\s*$', '', N(c)).strip().lower()
                want_b = {i.lower() for i in items}
                for _ in range(10):                          # chips that are not one of the skills (résumé-parsed) go, like the single-value path
                    self.relocate(f); box_ = p.locator(f['sel']).first
                    wrong_ = [x for x in box_.locator('[data-automation-id="selectedItem"]').all() if base(x.inner_text()) not in want_b]
                    if not wrong_: break
                    try: wrong_[0].locator('[data-automation-id="DELETE_charm"], [aria-label*="delete" i], [aria-label*="remove" i]').first.click(); time.sleep(0.6)
                    except Exception: break
                added = []
                for it in items:
                    self.relocate(f)
                    have_ = [base(x.inner_text()) for x in p.locator(f['sel']).first.locator('[data-automation-id="selectedItem"]').all()]
                    if it.lower() in have_: added.append(it); continue          # already a chip (a rerun) counts as added
                    try: self.fill_one(dict(f, answer=it, alts=[], _one_of=True)); added.append(it)
                    except Exception as ex_:
                        self.log(f"  {f['label']}: skill '{it}' not added ({type(ex_).__name__}) — optional, the rest stay")
                        try: p.keyboard.press('Escape')
                        except Exception: pass
                f['_added'] = added      # partial is accepted on purpose: a tenant list may not offer every skill; the misses are in the log
                if not added: raise ValueError(f'none of the skills {items} could be added')
                return
            texts = []
            okv = [x.lower() for x in [ans] + f.get('alts', [])]
            def clear_wrong():                                # wrong pre-filled (résumé-parsed) or Enter-selected pills out; the widget re-renders each time
                for _ in range(5):
                    self.relocate(f); box = p.locator(f['sel']).first
                    wrong = [x for x in box.locator('[data-automation-id="selectedItem"]').all() if N(x.inner_text()).lower() not in okv]
                    if not wrong: return
                    try: wrong[0].locator('[data-automation-id="DELETE_charm"], [aria-label*="delete" i], [aria-label*="remove" i]').first.click(); time.sleep(0.6)
                    except Exception: return
            def have_want():                                  # JSA-283: Enter after a search can pick the single match and close the list — the wanted pill is then already there
                try:
                    self.relocate(f)
                    return any(N(x.inner_text()).lower() in okv for x in p.locator(f['sel']).first.locator('[data-automation-id="selectedItem"]').all())
                except Exception: return False
            clear_wrong()
            tries = []
            for want in [ans] + [x for x in f.get('alts', []) if x != ans]:
                tries.append((want, want))
                if re.search(r'\s\(', want): tries.append((want, want.split(' (')[0]))   # search finds nothing for "Python (Programming Language)" (a Workday employer 2026-10-30)
            if not f.get('_one_of') and not f.get('alts'):    # JSA-283: a single wanted option (Field of Study): also its head before a comma, first words, then no search (scroll the whole list) — Vanguard "Computer Sciences, Technology, or Business"
                tries += [(ans, q) for q in prompt_queries(ans) if (ans, q) not in tries]
            school_names = None
            if f.get('kind') == 'education' and re.search(r'school|university|institution', f['label'], re.I):
                school_names = school_queries(ans, f.get('alts'))      # JSA-370: every alias is a search AND an accepted spelling
                tries = [(n, n) for n in school_names]
            for want, query in tries:
                self.relocate(f); box = p.locator(f['sel']).first
                inp = box.locator('input').first
                inp.click(); inp.fill(''); p.keyboard.type(query, delay=30); p.keyboard.press('Enter')   # Enter = search (some tenants filter, some don't)
                try: p.wait_for_selector('[data-automation-id="promptOption"]', timeout=5000)
                except Exception: continue
                time.sleep(0.8)
                found = p.evaluate(SCROLL_FIND_JS, {'names': school_names} if school_names else want)     # virtualized list: scroll until the exact option is rendered
                texts = found.get('seen', [])
                if found.get('hit'):
                    p.locator('[data-cx-opt="1"]').first.click(); time.sleep(0.4); p.keyboard.press('Escape')
                    used = found.get('text') if school_names else want
                    if used and used != ans: f['answer'] = used; self.log(f"  {f['label']}: '{ans}' not offered → used '{used}'")
                    return
                p.keyboard.press('Escape'); clear_wrong()     # JSA-283: an Enter after a short search can select a single wrong match — never leave it
                if have_want(): self.log(f"  {f['label']}: '{ans}' is selected (picked by Enter after the search '{query}')"); return
            if have_want(): return
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
        if x is None:
            f['readback'], f['readback_ok'] = 'MISSING', False
            return False, {'page': 'MISSING'}
        got, want = N(x['value']), N(f['answer'])
        if f['type'] == 'checkbox': ok = (got == 'checked') == (want == 'checked')
        elif f['type'] == 'date': ok = date_parts(got) == date_parts(want) or (len(date_parts(want)) == 2 and len(date_parts(got)) == 3 and [date_parts(got)[0], date_parts(got)[2]] == date_parts(want))   # "December 2027" = 12/01/2027 (a Workday employer, GE 2026-10-30)
        elif re.search(r'phone', f['label'], re.I) and f['type'] == 'text': ok = re.sub(r'\D', '', got)[-10:] == re.sub(r'\D', '', want)[-10:]
        elif f['type'] == 'multi': ok = sorted(got.split(' | ')) == sorted(want.split(' | '))
        elif f['type'] == 'prompt' and len(skill_items(f['label'], f['answer'])) > 1: ok = skills_present(x['value'], f.get('_added') or [])   # JSA-372: every skill that was added is shown
        elif f['type'] == 'prompt': ok = bool(got) and any(w and (got.lower() == w.lower() or w.lower() in got.lower()) for w in [want] + list(f.get('alts') or []))   # alts = tenant spellings / approved fallbacks
        else: ok = got == want
        f['readback'], f['readback_ok'] = got, ok          # JSA-320: the value the page holds after the fill (wd_log 'page')
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
            before = blocks_of(fields, missing[0])
            try:
                grp = self.section_group(missing[0])
                grp.locator('button:has-text("Add Another"), button:has-text("Add")').last.click(); time.sleep(1.5)
                self.log(f'  added an empty {missing[0]} block')
            except Exception as e:
                self.log(f'  could not add a {missing[0]} block: {type(e).__name__}'); break
            self.needs = self.needs[:n_needs]
            fields = self.settle()['fields']
            if blocks_of(fields, missing[0]) <= before:   # the click added nothing this runner recognises: stop, never pile up blocks (NCR 11-10: 14 UChicago blocks, JSA-270)
                self.log(f'  the {missing[0]} block count did not grow ({before}) — stop adding; check the section heading')
                self.failed.append({'step': step, 'section': missing[0], 'label': f'(missing {missing[0]} entries — the page did not add a recognisable block)', 'want': f'{len(PROFILE[missing[0]])} blocks'})
                break
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
        for f in todo:                                       # JSA-320: a field fixed after its last check (DeepSeek pick / fix) is read again
            if f.get('status') == 'ok' and not f.get('readback_ok'):
                self.check_one(f)
        self.record.append({'step': step, 'fields': [record_field(f) for f in plan]})
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
        cp = canon.pick_for(ckey, f['label'], opts, canon.tenant_of(self.page.url)) if ckey else None   # inversion applied (JSA-267)
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
        """The folder's generated PDF: 'resume' | 'cover' (<First>_<Last>_Cover_Letter_*.pdf) or None."""
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
                late = unplanned_fields(getattr(self, 'planned_keys', None), ex.get('fields'))
                if late and before not in self.replanned:   # fields appeared after the page was read: answer them first, never click past them (NCR 11-10: Hispanic left empty, JSA-273)
                    self.replanned.add(before)
                    self.log(f'  {len(late)} field(s) appeared on "{before}" after it was read ({"; ".join(l[:40] for l in late[:4])}) — reading the page again')
                    return False, ['__replan__']
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


def education_problems(plan, profile, live=None, folder=None):
    """Before leaving an experience page (JSA-032): every profile school is its own Education block, with the right degree
    level and its own GPA. A Back from Review drops all but one education entry on most tenants (#16 #75), so whatever
    Review would catch here must be caught on this page, where it can still be fixed without going Back.
    plan = this page's planned fields (kind / entry / section / label / answer); live(f) = the value now on the page."""
    live = live or (lambda f: f.get('answer'))
    edu = [f for f in plan if f.get('kind') == 'education' and f.get('entry') and f.get('status') != 'skip']
    if not edu:
        return block_problems(plan, live, folder)
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
    return out + block_problems(plan, live, folder)


def block_problems(plan, live=None, folder=None):
    """JSA-294: every education AND work block box on this page against the entry of its block, by code (block_check.py —
    school, degree, field, dates, GPA; job title, company, location, dates, "currently work here", role description).
    a Workday employer / Adobe: the résumé parse's "Job Searching Agent" stayed in Hyde Park's Job Title box."""
    import block_check as BC
    live = live or (lambda f: f.get('answer'))
    rows = [dict(f, page=live(f)) for f in plan if f.get('kind') in ('education', 'work') and f.get('status') != 'skip']
    try:
        return ['block check: ' + p for p in BC.problems(rows, overrides=BC.load_overrides(folder))]
    except Exception as e:
        return [f'block check failed: {type(e).__name__}: {str(e)[:100]}']


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
    ap.add_argument('--no-resume', action='store_true', help='walk every page even when checkpoint.json lists saved pages (JSA-392)')
    ap.add_argument('--mail-wait', type=int, default=180, help='seconds to wait for the company receipt e-mail when the page shows no confirmation after Submit (JSA-306; 0 = off)')
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
    if wd_already_submitted(folder):
        set_status(folder, 'done', 'already-submitted'); print('STATUS already-submitted'); return
    meta = json.load(open(os.path.join(folder, 'wd_job.json'))) if os.path.exists(os.path.join(folder, 'wd_job.json')) else {}
    url = en_us(a.url or meta['url'])
    logf = open(os.path.join(folder, 'run_log.md'), 'a', encoding='utf-8')
    def log(m): logf.write(f'- {now()} {m}\n'); logf.flush(); print(m)
    import chrome_guard                                       # JSA-227: no autofill / password extension in the job Chrome
    if chrome_guard.stop(folder, url, log, queue, DATA, 'workday'): return
    import runner_common as RC                                # JSA-196: the closing books are the common ones
    R = RC.Run('workday', url, folder, folder, submit=a.submit, log=log, label='Workday')
    R.queued = True                                           # this runner queues its own stops: never twice
    R.mark('page')
    usage = {'calls': 0, 'prompt': 0, 'out': 0}
    with sync_playwright() as pw:
        ctx = cdp_connect.connect(pw, a.cdp).contexts[0]
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
        status = 'filled'; confirmed_by = None; cbad = []
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
        steps, tried, loops, retyped = [], set(), 0, {}
        cp = load_checkpoint(folder)                         # JSA-392: pages a stopped run already saved are not walked (and My Experience not re-saved) again
        if status == 'filled' and cp.get('done') and not a.no_resume:
            tgt = resume_target(cp['done'], bar_steps(page))
            if tgt and should_jump(w.extract()['step'], tgt, bar_steps(page)):   # forward only; the click may validate / auto-save the page we leave (tenant behaviour, unverified live) — the fallback covers only 'not clickable'
                log(f'resume: saved pages {cp["done"]} — jumping to "{tgt}"')
                if not jump_to_step(page, tgt, log): log('resume: not possible on this tenant — every page is walked as before')
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
                jr = joey_step_result(st0)                     # JSA-374: Joey's task, not a failure
                queue(folder, jr['note'], url)
                status = jr['status']; break
            ex0 = w.extract()
            if (not ex0.get('fields') and not is_review(st0) and not re.search(r'autofill|experience|education|经历|經歷', st0, re.I)
                    and not page.locator('input[type="file"]').count()):
                # JSA-371: 0 fields right after a rerun = still rendering. Only WAIT and read (extract), never do_page: it uploads the résumé again
                (st1, f1), n_ = reread_empty_page(lambda: (lambda e: (e.get('step') or '', e.get('fields') or []))(w.extract()))
                log(f'page "{st1 or st0}" read 0 fields — waited and re-read {n_}x: {len(f1)} fields now')
            step, plan, clean = w.do_page(usage)
            w.planned_keys = {f.get('key') for f in plan}
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
            pre = education_problems(plan, PROFILE, lambda f: (w.field_now(f) or {}).get('value', f.get('answer')), folder) + page_canon_problems(plan, canon.tenant_of(url))
            if pre:
                log(f'page "{step}" not left — fix it here, no Back needed: ' + '; '.join(pre))
                for p_ in pre:
                    w.failed.append({'step': step, 'label': 'before leaving: ' + p_, 'want': ''})
                push('求职 runner：先在本页改正', os.path.basename(folder)[11:60] + f' — "{step}": ' + '; '.join(pre)[:150])
                status = 'handoff'; break
            ok, errs = w.next_page()
            if not ok and errs == ['__replan__']:
                continue                                       # do_page again: the late fields get planned, filled and checked
            if not ok and not retyped.get(step):
                again = filled_but_rejected(errs, plan)        # JSA-369: required error on a box we filled → type it again, Save once more
                if again:                                       # other errors on the page (a summary line) do not stop the retype
                    retyped[step] = True
                    for f_ in again:
                        f_['_typed'] = True
                        try:
                            w.fill_one(f_)
                            log(f'  "{f_["label"][:50]}": page said required with the value in the box → typed it again')
                        except Exception as ex_: log(f'  re-type {f_["label"][:40]}: {type(ex_).__name__}')
                    ok, errs = w.next_page()
                    if not ok and errs == ['__replan__']: continue
            if not ok:
                log(f'Workday errors on "{step}": {errs}')
                zero = zero_rejected(errs, [x for pg in w.record for x in (pg.get('fields') or [])])
                if zero and len(zero) == len(errs):        # only "0 counts as empty" errors: Joey picks the number (JSA-272)
                    for f in zero:
                        w.needs.append({'step': step, 'section': f.get('section', ''), 'label': f['label'], 'options': [], 'type': f.get('type', 'text'),
                                        'key': f.get('key'), 'why': 'the box keeps digits only and this tenant counts 0 as empty; the true answer is 0 '
                                        '(full-time student, Joey 2026-11-01) — Joey decides: another number, or skip this job', 'no_triage': True})
                    log('  0 is refused as empty: ' + '; '.join(f['label'][:60] for f in zero) + ' → Joey decides (no true number fits)')
                    status = 'needs-user'; break
                w.failed.append({'step': step, 'label': 'page errors', 'want': '', 'errors': errs}); status = 'handoff'; break
            cp = checkpoint_update(cp, step, now()); save_checkpoint(folder, cp); merge_answered(folder, w.answered)   # JSA-392: this page is saved, its answers too
        json.dump({'url': url, 'steps': steps, 'pages': w.record, 'needs': w.needs, 'failed': w.failed, 'deepseek': usage},
                  open(os.path.join(folder, 'wd_log.json'), 'w'), indent=1, ensure_ascii=False)
        if status != 'needs-user' and os.path.exists(os.path.join(folder, 'wd_needs.json')):
            os.remove(os.path.join(folder, 'wd_needs.json'))   # a run with no open question: an old list misleads (NCR 11-10, JSA-269)
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
            expand_review(page)                             # "MORE (1)" folds a long multi-select on Review (RGA 11-10, JSA-269)
            txt, prev_len = N(page.inner_text('body')), -1
            for _ in range(8):                              # Review renders section by section (RBC 2026-11-01: My Information was still empty) — wait until stable
                if len(txt) == prev_len: break
                prev_len = len(txt); time.sleep(1.5); txt = N(page.inner_text('body'))
            prev = merge_answered(folder, w.answered)           # answers from every run of this application (resumes start mid-way)
            want = {k: v for k, v in prev.items() if not re.search(r'^(Education|Academic Experience|Schools? Attended|Work Experience) \d', k)}   # blocks: checked by name below
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
                if listed and not any(N(n).lower() in l or l in N(n).lower() for n in [e['School']] + e.get('School_alts', []) for l in listed) and not any(same_school(l, school_queries(e['School'], e.get('School_alts', []))) for l in listed):   # JSA-370: aliases + same words in any order
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
                if re.search(r'\|\|(State|State/Province|Province|Region)$', k) and state_on_review(s, txt):   # "<City>, <ST> <ZIP>" in the address block (RGA 11-10, JSA-269)
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
            import final_review                                # JSA-355: a second model re-reads the key cells
            w.problems.extend(final_review.problems(recs, log, tag=folder))
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
            if missing or w.problems or cbad: clear_checkpoint(folder)   # a wrong page must be walked and refilled again — never resume past it (JSA-392 review)
            if reasons:
                log('NOT submitted: ' + ' | '.join(reasons)); status = 'dry-run' if not a.submit else 'blocked'
                if a.submit: queue(folder, 'not submitted: ' + ' | '.join(reasons), url)
            else:
                import confirm_page as CP
                foot = page.locator('button[data-automation-id="pageFooterNextButton"]').first
                def snap():                                  # JSA-299: the page before / after the click
                    try: form = foot.is_visible()
                    except Exception: form = None
                    return {'url': page.url, 'text': page.inner_text('body'), 'form': form}
                R.mark('submit')
                before = snap()
                t_submit = datetime.now(timezone.utc)
                foot.click(); log('submit clicked')
                ok, why = False, ''
                for _ in range(60):
                    time.sleep(0.5)
                    ok, why = wd_done(before, snap())
                    if ok: break
                if ok:
                    log(f'confirmation page: {why}'); CP.settle(page)
                    page.screenshot(path=os.path.join(folder, 'submitted_confirmation.png'), full_page=True); status = 'submitted'
                    log('CONFIRMED | ' + page.url)
                    with open(os.path.join(folder, 'application_record.md'), 'a', encoding='utf-8') as rec:
                        rec.write(f"\n## Submitted by run_wd.py {now()}\n- URL: {url}\n- Pages: {' → '.join(steps)}\n- Review-page check: pass\n- Confirmation: submitted_confirmation.png\n- Details: wd_log.json\n")
                else:
                    page.screenshot(path=os.path.join(folder, 'after_submit.png'), full_page=True)
                    def mail_waiter(*args, **kw):             # JSA-306: the page proved nothing → the company's receipt e-mail (like the other runners); the import is inside wd_mail_receipt's try
                        import gmail_code; return gmail_code.wait_for_mail(*args, **kw)
                    subj = wd_mail_receipt(meta, t_submit, a.mail_wait, mail_waiter, log)
                    if subj:
                        status, confirmed_by = 'submitted', 'email'
                        log(f'CONFIRMED by e-mail: "{subj[:90]}"')
                        with open(os.path.join(folder, 'application_record.md'), 'a', encoding='utf-8') as rec:
                            rec.write(f"\n## Submitted by run_wd.py {now()}\n- URL: {url}\n- Pages: {' → '.join(steps)}\n- Review-page check: pass\n"
                                      f"- Confirmation: company e-mail \"{subj[:120]}\" (the page showed no thank-you; see after_submit.png)\n- Details: wd_log.json\n")
                    else:
                        status = 'unconfirmed'
                        queue(folder, 'clicked Submit but no confirmation page and no company e-mail — see after_submit.png, check Gmail', url)
        set_status(folder, FINAL_STATE.get(status, status), f'{status} · needs {len(w.needs)} · failed {len(w.failed)} · DS calls {usage["calls"]}')
        log(f'STATUS {status} · pages {" → ".join(steps)} · needs {len(w.needs)} · failed {len(w.failed)} · DeepSeek {usage}')
        # closing books (JSA-196): one results line (+ phases, stopped_at, tenant) and one fields.jsonl line per read-back field, the
        # tracker row for a submit (sync_results). The tab handling below stays here (tab_should_close / --keep-tab).
        R.stopped_at = None if status in ('submitted', 'dry-run', 'unconfirmed', 'filled') else (RC.COMMON if status == 'blocked' else RC.PAGE)
        rows_ = [{'step': pg.get('step'), 'fields': [dict(f, ok=(f['ok'] if f.get('ok') is not None else f.get('status') in ('ok', 'keep', 'skip')))
                                                   for f in pg.get('fields') or []]} for pg in w.record]   # kept / skipped fields are not "unconfirmed"
        R.finish({'status': status, 'problems': list(w.problems)[:8], 'steps': rows_, 'canon': cbad},
                 ctx=None, page=None, confirmed_by=confirmed_by, told=True,
                 extra={'steps': steps, 'needs': len(w.needs), 'failed': len(w.failed), 'deepseek': usage})
        if status != 'captcha': human_check.resolve(folder, status)
        if tab_should_close(status) and not a.keep_tab:     # Joey 2026-10-28 / 2026-11-01: close the page when the application ends (memory); --keep-tab: Joey acts in it now
            try: page.close()
            except Exception: pass


if __name__ == '__main__':
    main()
