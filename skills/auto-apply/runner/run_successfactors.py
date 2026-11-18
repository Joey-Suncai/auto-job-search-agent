#!/usr/bin/env python3
"""SAP SuccessFactors runner (JSA-092 / JSA-153, 2026-11-04). Career sites `careers.<company>.com/job/<slug>/<id>/`
hand "Apply now" to the legacy candidate site `career4.successfactors.com` (per-company account):

  job page → Apply now → Sign In (Keychain password) or Create Account (fbclc_ form + data privacy statement — Joey
  2026-11-04 「同意」) → one application page with sections (My Documents: resume / cover letter dialogs; Profile; …;
  Job-Specific Information; EEO; certification + electronic signature) → Apply.

Every field is answered with answer_rules.js (config/profile.json) through rules_bridge.js; the combo boxes
(`role=combobox`, options `li[role=option]` in the list named by aria-owns) are read and set by option text; every field is
read back; a required field empty on the page blocks. Dry-run by default (stops before Apply).

    ~/.job-agent-venv/bin/python run_successfactors.py --folder applications/<folder> [--submit]
    ~/.job-agent-venv/bin/python run_successfactors.py --url <job page url> [--resume <pdf>] [--out <dir>]

--submit: only when every field read back, nothing unknown, the folder is in data/runner/approved_batches.json and not
already submitted. Confirmed by the thank-you page or the receipt e-mail → submitted, tracker row (sync_results), the
posting's tabs closed. Writes <out>/run_log.md, form_check.json, page.png; one line in data/runner/results.jsonl.
"""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import argparse, json, os, re, subprocess, sys, time
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
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'config'))
import run_workable as W  # noqa: E402  (confirmed_page, required_empty, N)
import essay_step as ES  # noqa: E402  (JSA-318: the shared essay-box step)
import field_limits as FL  # noqa: E402  (JSA-312: the box's own length / format limits)
import sf_background as SB  # noqa: E402  (Previous Employment / Formal Education rows, an employer 2026-11-04)
import sf_combo_edu as CE  # noqa: E402  (education rows of School / Degree / Major combo lists, Erie 2026-11-04)
import job_board  # noqa: E402  (a source list that names job boards: the row's own board when listed)

N = W.N
JOB = {}                                                          # the store row of this job (source / url pick the job board)
SITE_BOARD = re.compile(r'\bjob\s*board\s*[-–:/]\s*\S', re.I)   # a source option that names its site: "Job Board - Indeed" (type Z)


def board_defaults():
    """The board to name when the row's own board is not in the list (config answers.how_heard_board: default, then
    fallback — Joey 2026-11-03: LinkedIn, then Indeed)."""
    import jsa_profile
    b = jsa_profile.get('answers.how_heard_board') or {}
    return [x for x in [b.get('default')] + list(b.get('fallback') or []) if x] or ['LinkedIn', 'Indeed']


BOARD_OTHER = re.compile(r'\bjob\s*boards?\b\W{0,5}(\(\s*)?other\b|\bother\W{0,5}(\(\s*)?job\s*boards?\b|\bother (online )?job (board|site|website)s?\b', re.I)


def other_board(picked, job, defaults=None):
    """Pure (tested). The text for the "specify" box after a source list answered "Job Boards-Other (specify name below)"
    (Newell 11-05, JSA-205): the row's own board (job_board.board_of: store `source`, then the URL host), else the config
    default (answers.how_heard_board: LinkedIn, then Indeed). None when the pick is not a job-board "Other" option."""
    if not BOARD_OTHER.search(str(picked or '')):
        return None
    job = job or {}
    return job_board.board_pick(list(job_board.BOARDS), job.get('source') or job.get('sources'), job.get('url'),
                                defaults if defaults is not None else board_defaults())


HEARD = re.compile(r'(how|where) (did )?you (\w+ )?(hear|heard|find|found|learn|learned) (about|of)\b', re.I)


def parse_job(url):
    """Pure (tested). A SuccessFactors career-site job URL → {'host', 'id'} (…/job/<slug>/<7+ digits>/), else None."""
    m = re.match(r'^https?://([\w.-]+)/(?:[\w-]+/)?job/[^/?#]+/(\d{7,})/?(?:[?#].*)?$', str(url or '').strip())
    return {'host': m.group(1).lower(), 'id': m.group(2)} if m else None


def clean_label(t):
    """Pure (tested). '* Are you willing to travel …?' / 'Street Address:' → the question text: the leading required star
    and the trailing colon dropped, whitespace collapsed."""
    t = N(t)
    t = re.sub(r'^\*\s*', '', t)
    t = re.sub(r'\s*\*\s*$', '', t)                               # "Address Line1*" (an employer)
    t = re.sub(r'\s*:\s*$', '', t)
    return N(t)


QROWS = r"""const qrows = e => {                      // JSA-232: the text-only table rows right above the field's row (nearest first), up to the previous field
  const tr = e.closest('tr'); const out = []; let p = tr && tr.previousElementSibling;
  const HAS = 'input,select,textarea,[role=combobox],[role=radiogroup]';
  for (let i = 0; i < 4 && p; i++, p = p.previousElementSibling) {
    if (p.querySelector(HAS)) break;
    const t = (p.innerText || '').replace(/\s+/g, ' ').trim(); if (t) out.push(t.slice(0, 2000));
  }
  if (!tr) {                                     // JSA-295 (an employer "Acknowledgement"): no table — the text-only blocks before the field, climbing up to 5 levels
    let stop = false;
    for (let a = e, d = 0; a && d < 5 && !out.length && !stop; a = a.parentElement, d++) {
      for (let q = a.previousElementSibling, i = 0; q && i < 4; q = q.previousElementSibling, i++) {
        if (q.matches(HAS) || q.querySelector(HAS)) { stop = true; break; }
        if (q.tagName === 'LABEL') continue;     // the field's own label ("* Acknowledgement"), not the text above it
        const t = (q.innerText || '').replace(/\s+/g, ' ').trim(); if (t) out.push(t.slice(0, 2000));
      }
    }
  }
  return out;
};"""


READ = r"""() => { """ + QROWS + r""" return [...document.querySelectorAll('input,select,textarea')].filter(e => e.offsetParent !== null && !['hidden','button','submit','file','password','radio'].includes(e.type)).map(e => {
  let lab = ''; if (e.labels && e.labels[0]) lab = e.labels[0].innerText;
  if (!lab) { const ids = e.getAttribute('aria-labelledby'); if (ids) lab = ids.split(' ').map(x => (document.getElementById(x) || {}).innerText || '').join(' '); }
  if (!lab) lab = e.getAttribute('aria-label') || e.getAttribute('title') || '';
  const combo = e.getAttribute('role') === 'combobox' || /_listSelect$/.test(e.getAttribute('aria-owns') || '') || /selectinput/i.test(e.className || '');   // Race has no role until Ethnicity is set
  return {id: e.id, tag: e.tagName.toLowerCase(), type: combo ? 'combo' : (e.tagName === 'TEXTAREA' ? 'textarea' : e.type === 'checkbox' ? 'checkbox' : e.tagName === 'SELECT' ? 'select' : 'text'),
          label: lab.replace(/\s+/g, ' ').trim(), required: e.required || e.getAttribute('aria-required') === 'true' || /^\s*\*/.test(lab),
          list: e.getAttribute('aria-owns') || '', value: e.type === 'checkbox' ? (e.checked ? 'checked' : '') : (e.value || ''),
          options: e.tagName === 'SELECT' ? [...e.options].map(o => o.text.trim()) : [], rows: qrows(e),
          maxlength: e.maxLength > 0 ? e.maxLength : null, minlength: e.minLength > 0 ? e.minLength : null,   // JSA-312: the box's own limits
          pattern: e.getAttribute('pattern') || '', input_type: e.type || ''};
}); }"""


def limit_gate(fields, ans):
    """Pure (tested, JSA-312). A text answer that breaks the box's own limits (maxlength — the box would cut it; minlength;
    pattern; a url label / type=url without http(s)://) → status unknown with the reason, so the row stops for Joey
    instead of being typed in. Returns the new answers."""
    out = dict(ans)
    for f in fields:
        a = out.get(f['key']) or {}
        if f.get('type') not in ('text', 'textarea') or a.get('status') != 'ok' or a.get('leave') or not str(a.get('value') or '').strip():
            continue
        lim = FL.merge({'max': f.get('maxlength'), 'min': f.get('minlength'), 'pattern': f.get('pattern') or None,
                        'format': 'url' if FL.url_box(f.get('label') or '', f.get('input_type')) else None, 'source': 'the box'})
        if isinstance(a.get('value'), str):
            fx = FL.fix_url(a['value'], lim, f.get('label') or '', f.get('input_type'))   # a bare address in a url box → https://
            if fx != a['value']:
                a = out[f['key']] = dict(a, value=fx, rule=f"{a.get('rule')}+https")
        bad = FL.check(str(a['value']), lim, f.get('label') or '')
        if bad:
            out[f['key']] = {'status': 'unknown', 'label': f['label'], 'rule': a.get('rule'),
                             'why': "the answer breaks the box's limit — " + FL.why(bad, a['value'], lim)}
    return out


PLACEHOLDER_LABEL = re.compile(r'^(please )?(select|choose)( one( of the (options|following))?| an option| from the list)?\s*:?$|^no selection$|^-+$', re.I)
QUESTION_MAX = 300


HEADING_LABEL = re.compile(r'^(i )?acknowledge?(ment)?s?\.?$|^(applicant |candidate )?(statement|attestation|certification|agreement|acknowledge?ment)s?\.?$', re.I)
STATEMENT_MAX = 1200                                              # the statement a heading-labelled box agrees to may be long; a longer row is a notice, not it


def question_label(label, rows=None, kind=None):
    """Pure (tested). The question text of a field (JSA-232). SuccessFactors templates put the question in its own
    text-only row above the field (an employer 11-06: "Are you at least 18 years of age?") and give the field itself the
    generic label "Please select one of the options". `rows` = the text-only rows above the field's row, nearest first,
    up to the previous field. A real label is kept (cleaned); a placeholder label takes the nearest row of at
    most 300 characters; when every row is longer (a whole notice), its last question sentence, else its first 300
    characters. Never returns the placeholder text when a row is there (else the placeholder, for label_from_options).
    An empty label stays empty."""
    lab = clean_label(label)
    texts = [clean_label(t) for t in rows or [] if re.search(r'[A-Za-z]{2,}', str(t or ''))]
    if lab and kind == 'checkbox' and HEADING_LABEL.match(lab):   # a one-word box label ("Acknowledgement") under the statement it agrees to (an employer 11-10, JSA-295)
        stmt = next((t for t in texts if len(t) <= STATEMENT_MAX and not HEADING_LABEL.match(t)), None)
        return stmt or lab
    if not lab or not PLACEHOLDER_LABEL.match(lab):               # an unlabeled box (a combo's search box) stays unlabeled: plan() skips it
        return lab
    short = next((t for t in texts if len(t) <= QUESTION_MAX), None)
    if short:
        return short
    if texts:
        qs = re.findall(r'[^.?!]*\?', texts[0])
        q = clean_label(qs[-1]) if qs else ''
        return q if q and len(q) <= QUESTION_MAX else texts[0][:QUESTION_MAX].rstrip()
    return lab


def plan(raw):
    """Pure (tested). READ output → fields [{key, label, type, required, options, list}] — unlabeled boxes and the
    search box of a combo list are left out; text-type options of a <select> drop the 'No Selection' placeholder."""
    out = []
    for f in raw or []:
        lab = question_label(f.get('label') or '', f.get('rows'), f.get('type'))
        if not lab or not f.get('id'):
            continue
        opts = [o for o in f.get('options') or [] if o and not re.match(r'^(no selection|select|-+|please select)', o, re.I)]
        out.append({'key': f['id'], 'label': lab, 'type': f.get('type') or 'text', 'required': bool(f.get('required')),
                    'options': opts, 'list': f.get('list') or '', 'value': f.get('value') or '',
                    'maxlength': f.get('maxlength'), 'minlength': f.get('minlength'),   # JSA-318: READ had them, plan dropped them, so limit_gate (JSA-312) never saw a limit
                    'pattern': f.get('pattern') or '', 'input_type': f.get('input_type') or ''})
    return out


def css(i):
    return '[id="' + i.replace('"', '\\"') + '"]'


def _open(page, f):
    """Open a combo and wait until its list has real options (the paginated ones load late)."""
    inp = page.locator(css(f['key'])).first
    inp.scroll_into_view_if_needed(); inp.click()
    lid = f.get('list') or ''
    sel = (css(lid) + ' li[role=option]') if lid else 'li[role=option]'
    for attempt in range(2):
        for _ in range(16):
            time.sleep(0.25)
            texts = [N(t) for t in page.locator(sel).all_inner_texts()]
            if [t for t in texts if t and not re.match(r'^no selection$', t, re.I)]:
                if lid:                                           # a paginated list loads more as it scrolls (Country stops at "Iceland")
                    for _ in range(40):
                        n = len(texts)
                        page.evaluate("(id) => { const l = document.getElementById(id); if (l) { const s = l.closest('[class*=scroll i], .sfDropDownList, ul') || l; s.scrollTop = s.scrollHeight; l.scrollTop = l.scrollHeight; const last = l.querySelector('li[role=option]:last-child'); if (last) last.scrollIntoView(); } }", lid)
                        time.sleep(0.5)
                        texts = [N(t) for t in page.locator(sel).all_inner_texts()]
                        if len(texts) == n:
                            break
                return inp, sel, texts
        page.keyboard.press('Escape'); time.sleep(0.4); inp.click()   # the list did not open (a previous one was still open): reopen
    return inp, sel, []


def combo_options(page, f):
    inp, sel, opts = _open(page, f)
    page.keyboard.press('Escape'); time.sleep(0.3)
    return [o for o in opts if o and not re.match(r'^no selection$', o, re.I)]


def combo_set(page, f, want):
    """Pick `want` in a combo by clicking its option; the list must have loaded (a dependent list such as Race reloads
    from the server after Ethnicity). A long paginated list (Country) is filtered by typing the start of the answer first.
    Up to 3 opens; True when the input then shows the value."""
    for attempt in range(3):
        inp, sel, texts = _open(page, f)
        if attempt and N(want):                                   # not among the loaded options: type to filter the list
            CE._clear(inp, N)                                     # into an EMPTY box: typing after a failed try appended ("University oUniv…", Erie 11-04)
            inp.press_sequentially(N(want)[:12], delay=60); time.sleep(2)
        opt = page.locator(sel)
        for i in range(opt.count()):
            if N(opt.nth(i).inner_text()).lower() == N(want).lower():
                opt.nth(i).scroll_into_view_if_needed(); opt.nth(i).click(); time.sleep(0.8)
                if N(page.locator(css(f['key'])).first.input_value()).lower() == N(want).lower():
                    return True
                break
        page.keyboard.press('Escape'); time.sleep(1.0 + attempt)
    raise ValueError(f'no option {want!r} (or it did not stick)')


EDU_ROWS = r"""() => [...document.querySelectorAll('input')].filter(e => e.offsetParent !== null && /Name of School/.test((e.labels && e.labels[0] && e.labels[0].innerText) || '')).map(n => {
  let a = n; for (let i = 0; i < 12 && a; i++) { a = a.parentElement; if (a && a.querySelectorAll('input').length >= 4) break; }
  const lab = e => ((e.labels && e.labels[0]) ? e.labels[0].innerText : (e.getAttribute('aria-label') || '')).replace(/\s+/g, ' ').replace(/^\*\s*/, '').trim();
  const del = [...a.querySelectorAll('*')].find(e => e.offsetParent !== null && e.children.length === 0 && /^delete row$/i.test((e.textContent || '').trim()));
  const b = del ? del.getBoundingClientRect() : null;
  return {school: n.value, fields: [...a.querySelectorAll('input,textarea')].filter(e => e.offsetParent !== null && e.type !== 'hidden').map(e => ({key: e.id, label: lab(e),
          type: (e.getAttribute('role') === 'combobox' || /_listSelect$/.test(e.getAttribute('aria-owns') || '')) ? 'combo' : 'text', list: e.getAttribute('aria-owns') || '', value: e.value})),
          del: b ? [b.x + b.width / 2, b.y + b.height / 2] : null};
})"""


def unsplit(t):
    """Pure (tested). The resume parser splits words after a capital ("U NIVERSITY OF C HICAGO", "H YDE P ARK"): a lone
    capital letter followed by a space and another capital word is joined back ("UNIVERSITY OF CHICAGO")."""
    return re.sub(r'\b([A-Z]) (?=[A-Z]{2,}\b)', r'\1', str(t or ''))   # only before an ALL-CAPS word: "<street>" stays


SPLIT_LABEL = re.compile(r'employer|company|school|college|university|institution|organi[sz]ation|job title|title', re.I)


def split_fix(f):
    """Pure (tested). True when a prefilled text box of a history row (employer / company / school / title …) holds the
    parser's split words ("HYDE P ARK INVESTMENT S ERVICES") that unsplit repairs."""
    return f.get('type') in ('text', 'textarea') and bool(f.get('value')) and unsplit(f['value']) != f['value'] and bool(SPLIT_LABEL.search(f.get('label') or ''))


def fix_split_words(page, log):
    """Repair the parser's split words in every prefilled employer / school / title box — run BEFORE the rows are matched
    to the facts (an employer 11-05). Returns the number of boxes fixed."""
    n = 0
    for f in plan(page.evaluate(READ)):
        if split_fix(f):
            try:
                page.locator(css(f['key'])).first.fill(unsplit(f['value'])); n += 1
                log(f"fixed split words: {f['value'][:40]!r} → {unsplit(f['value'])[:40]!r}")
            except Exception as e:
                log(f"split words in {f['label'][:30]}: not fixed ({type(e).__name__})")
    return n


def match_school(name, edus):
    """Pure (tested). A parsed school name (the resume parser splits words: "U NIVERSITY OF C HICAGO") → the config education
    entry whose match_re hits the name with spaces removed, else None."""
    compact = re.sub(r'[^a-z]', '', str(name or '').lower())
    if not compact:
        return None
    for e in edus or []:
        if re.search(e.get('match_re') or '$^', compact):
            return e
    return None


def edu_answers(edu, today=None):
    """Pure (tested). One config education entry → the answers for a SuccessFactors education row: Name of School, Major,
    GPA ('' when none on file), Did you graduate? (Yes when it has ended by today and is not current), Degree level
    regex, Are you currently a student?, anticipated graduation date (MM/YYYY when current)."""
    today = today or datetime.now().strftime('%Y-%m')
    current = bool(edu.get('current'))
    ended = bool(edu.get('end')) and str(edu['end']) <= today and not current
    import jsa_profile
    gpa = edu.get('gpa') or (str(jsa_profile.get('answers.gpa.text') or '') if edu.get('level') == 'bachelor' else '')   # the bachelor's GPA on file (config, JSA-077)
    end = str(edu.get('end') or '')
    return {'Name of School': edu.get('school') or '', 'Major': edu.get('major') or '', 'GPA': gpa,
            'Did you graduate?': 'Yes' if ended else 'No', 'Degree': r'master' if edu.get('level') == 'master' else r'bachelor',
            'Are you currently a student?': 'Yes' if current else 'No',
            'anticipated graduation date': f'{end[5:7]}/{end[:4]}' if current and len(end) >= 7 else ''}


def fill_education(page, log):
    """Each Education row (often created by the resume parser): matched to config education → filled with that school's
    facts; an empty, unknown or duplicate row is deleted ("Delete Row"). Returns (rows for the read-back, keys handled)."""
    import jsa_profile
    edus = jsa_profile.get('education') or []
    out, keys, seen = [], set(), set()
    for _ in range(6):                                            # delete one bad row at a time (the page re-renders)
        rows = page.evaluate(EDU_ROWS)
        bad = next((r for r in rows if not match_school(r['school'], edus) or match_school(r['school'], edus)['school'] in
                    [match_school(x['school'], edus)['school'] for x in rows[:rows.index(r)] if match_school(x['school'], edus)]), None)
        if not bad or not bad.get('del'):
            break
        log(f"education: deleting row '{bad['school'][:40]}'"); page.mouse.click(*bad['del']); time.sleep(1.5)
        ok = page.locator('#sfOverlayMgr button:has-text("OK"), #sfOverlayMgr button:has-text("Yes")')
        if ok.count() and ok.first.is_visible(): ok.first.click(); time.sleep(1.5)
    for r in page.evaluate(EDU_ROWS):
        e = match_school(r['school'], edus)
        if not e or e['school'] in seen:
            continue
        seen.add(e['school'])
        want = edu_answers(e)
        for f in r['fields']:
            keys.add(f['key'])
            lab = next((k for k in want if k.lower() in f['label'].lower()), None)
            if not lab:
                continue
            w = want[lab]
            row = {'key': f['key'], 'label': f"Education ({e.get('short') or e['school']}): {f['label']}", 'type': f['type'], 'required': False,
                   'list': f['list'], 'options': [], 'rule': 'education', 'step': 'edu'}
            try:
                if f['type'] == 'combo':
                    opts = combo_options(page, f)
                    pick = next((o for o in opts if re.search(w, o, re.I)), None) if lab == 'Degree' else w
                    row['want'] = pick
                    if pick: combo_set(page, f, pick)
                else:
                    row['want'] = w or None
                    if w: page.locator(css(f['key'])).first.fill(w)
                    elif f['value'] and lab == 'GPA': page.locator(css(f['key'])).first.fill('')   # no GPA on file for this school: leave it empty
            except Exception as ex:
                row['error'] = f'{type(ex).__name__}: {str(ex)[:100]}'
            row['required'] = bool(row.get('want'))                  # a value we mean to set must be on the page
            out.append(row)
    return out, keys


READ_EXTRA = r"""() => {
  const optC = __OPTC__;
  const out = [];
  document.querySelectorAll('[role=radiogroup]').forEach(g => {
    if (g.offsetParent === null) return;
    const lab = (document.getElementById(g.getAttribute('aria-labelledby') || '') || {}).innerText || '';
    const opts = [...g.querySelectorAll('[role=radio]')].map(r => ({id: r.id, text: (((document.getElementById(r.getAttribute('aria-labelledby') || '') || {}).innerText) || (r.labels && r.labels[0] ? r.labels[0].innerText : '') || '').trim(),
                                                            on: r.getAttribute('aria-checked') === 'true' || r.checked === true}))
                     .filter(o => o.text && !/^no selection$/i.test(o.text) || o.on && false);
    const on = (opts.find(o => o.on) || {}).text || '';
    out.push({id: g.id, type: 'radio', label: lab.replace(/\s+/g, ' ').trim(), required: /^\s*\*/.test(lab), options: opts.map(o => o.text), radios: opts, value: on});
  });
  const groups = {};
  document.querySelectorAll('input[type=radio]').forEach(r => { if (r.offsetParent !== null && r.name && !r.closest('[role=radiogroup]')) (groups[r.name] = groups[r.name] || []).push(r); });   // radios inside a role=radiogroup were read above
  Object.entries(groups).forEach(([name, rs]) => {                 // plain HTML radios (SPX questionnaire: fbjq_question_N)
    const fs = rs[0].closest('fieldset'); const lg = fs && fs.querySelector('legend');
    const li = rs[0].closest('li, .questionFieldLabel, div'); const fl = li && li.querySelector('.questionFieldLabel, [id^=fieldLabel]');
    const lab = ((fl && fl.innerText) || (lg && lg.innerText) || '').replace(/\s+/g, ' ').trim();
    const opts = rs.map((r, i) => ({id: r.id, name: r.name, value: r.value, idx: i, dup: rs.filter(x => x.value === r.value).length > 1, c: optC(r),
                                    text: ((r.labels && r.labels[0]) ? r.labels[0].innerText : r.value).trim(), on: r.checked}));   // text from the surrounding DOM: radio_texts (Python)
    const texts = []; let a = rs[0].parentElement; for (let i = 0; i < 6 && a && !lab; i++, a = a.parentElement) texts.push(a.innerText || '');   // no label of its own: the ancestors' text (radio_question)
    out.push({id: 'radio:' + name, type: 'radio', native: true, label: lab, texts, required: rs.some(r => r.required || r.getAttribute('aria-required') === 'true') || /^\s*\*/.test(lab),
              options: opts.map(o => o.text), radios: opts, value: (opts.find(o => o.on) || {}).text || ''});
  });
  const nth = {};
  document.querySelectorAll('ui5-date-picker-xweb-calendar-widget').forEach((d, i) => {
    const nm = d.getAttribute('accessible-name') || String(i); const k = nth[nm] = (nth[nm] === undefined ? 0 : nth[nm] + 1);   // "Start Date" repeats in every history row (an employer)
    if (d.offsetParent === null && !d.getClientRects().length) return;
    const sec = d.closest('.rcmFormSection');
    out.push({id: 'ui5date:' + nm + (k ? '#' + k : ''), nth: k, sec: sec ? sec.id : '', type: 'date', label: d.getAttribute('accessible-name') || '', required: d.hasAttribute('required'),
              options: [], value: d.getAttribute('value') || (d.value || ''), fmt: d.getAttribute('format-pattern') || 'MM/dd/yyyy'});
  });
  return out;
}"""


UNSEEN_REQUIRED = r"""() => {
  const out = []; const seenRadio = new Set();
  document.querySelectorAll('input, select, textarea').forEach(e => {
    if (e.offsetParent === null || ['hidden','button','submit','file','password','checkbox'].includes(e.type)) return;
    if (!(e.required || e.getAttribute('aria-required') === 'true')) return;
    const lab = ((e.labels && e.labels[0] && e.labels[0].innerText) || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
    if (e.type === 'radio') {
      if (seenRadio.has(e.name)) return; seenRadio.add(e.name);
      if ([...document.getElementsByName(e.name)].some(r => r.checked)) return;
      const fs = e.closest('fieldset'); const lg = fs && fs.querySelector('legend');
      out.push({id: 'radio:' + e.name, key: 'radio:' + e.name, label: (lg && lg.innerText || lab).trim()}); return;
    }
    if (!(e.value || '').trim()) out.push({id: e.id, key: e.id, label: lab});
  });
  return out;
}"""


def option_text(c):
    """Pure (tested). The option text of one radio input from what its surrounding DOM offers (Newell 11-05: no id, no
    <label for>, the text in an aria-label and in a loose <label> next to the input's wrapper). c = {label (its own
    <label>), labelledby (aria-labelledby text), aria (aria-label), after (the text right after the input or its wrapper,
    up to the next radio), wrap (the text of the nearest wrapper holding only this radio), value} → the first non-empty of
    label, labelledby, aria, after, wrap (whitespace collapsed, a leading required star dropped, at most 300 characters —
    a longer text is not an option), else the value; '' when none."""
    for k in ('label', 'labelledby', 'aria', 'after', 'wrap'):
        t = re.sub(r'^\*\s*', '', N((c or {}).get(k) or ''))
        if t and len(t) <= 300:
            return t
    return N((c or {}).get('value') or '')


def radio_selector(opt):
    """Pure (tested). opt = {id, name, value, idx, dup} of one radio input → [css selector, nth]: by id when it has one;
    else by name + value (`input[type=radio][name="…"][value="…"]`, nth 0) when the value is set and unique in its group
    (dup false); else by name and the input's position in its group (nth = idx). None when it has neither id nor name."""
    o = opt or {}
    q = lambda s: str(s).replace('\\', '\\\\').replace('"', '\\"')
    if o.get('id'):
        return [css(o['id']), 0]
    if not o.get('name'):
        return None
    base = f'input[type=radio][name="{q(o["name"])}"]'
    if str(o.get('value') or '') != '' and not o.get('dup'):
        return [base + f'[value="{q(o["value"])}"]', 0]
    return [base, int(o.get('idx') or 0)]


RADIO_TEXT_JS = r"""(r) => {
  const T = x => ((x && (x.innerText !== undefined ? x.innerText : x.textContent)) || '').replace(/\s+/g, ' ').trim();
  const one = a => a && a.querySelectorAll('input[type=radio]').length === 1;
  let after = ''; let n = r; for (let up = 0; up < 3 && n && !after; up++) {          // the text right after the input, else after its wrapper (Newell: <span><input></span><label>…</label>)
    for (let s = n.nextSibling; s && !after; s = s.nextSibling) {
      if (s.nodeType === 1 && (s.matches('input[type=radio]') || s.querySelector('input[type=radio]'))) break;
      after = T(s);
    }
    if (!after && one(n.parentElement)) n = n.parentElement; else break;
  }
  let w = r.parentElement; for (let i = 0; i < 3 && w && one(w.parentElement) && !T(w); i++) w = w.parentElement;
  return {label: r.labels && r.labels[0] ? T(r.labels[0]) : '', aria: r.getAttribute('aria-label') || '',
          labelledby: (r.getAttribute('aria-labelledby') || '').split(' ').map(x => T(document.getElementById(x))).join(' ').trim(),
          after, wrap: one(w) ? T(w) : '', value: r.value || ''};
}"""
READ_EXTRA = READ_EXTRA.replace('__OPTC__', RADIO_TEXT_JS)


def radio_texts(items):
    """Pure (tested through option_text). READ_EXTRA / REG_RADIOS items → the same items with each plain radio's text taken
    from its surrounding DOM (option_text of its `c`), the group's options and its value (the checked option's text) rebuilt."""
    for x in items or []:
        rs = x.get('radios') or []
        if x.get('type') != 'radio' or not any('c' in r for r in rs):
            continue
        for r in rs:
            if 'c' in r:
                r['text'] = option_text(r['c']) or r.get('text') or ''
        x['options'] = [r['text'] for r in rs]
        x['value'] = next((r['text'] for r in rs if r.get('on')), '')
    return items


def read_extra(page):
    return radio_texts(page.evaluate(READ_EXTRA))


def radio_set(page, f, want):
    """Click the option of a SuccessFactors radiogroup whose label is `want`; True when it is then checked. A plain radio
    with no id is found by name + value / position (radio_selector — Newell 11-05: `[id=""]` never matched, TimeoutError)."""
    opt = next((o for o in f.get('radios') or [] if N(o['text']).lower() == N(want).lower()), None)
    if not opt:
        raise ValueError(f'no option {want!r}')
    sel = radio_selector(opt)
    if not sel:
        raise ValueError(f'option {want!r} has no id and no name')
    el = page.locator(sel[0]).nth(sel[1])
    el.scroll_into_view_if_needed(); el.click(); time.sleep(0.4)
    if el.evaluate("e => e.tagName === 'INPUT'"):
        if not el.is_checked(): el.check(force=True)
        return el.is_checked()
    return el.get_attribute('aria-checked') == 'true'


def date_set(page, f, value):
    """Type the date into a UI5 date picker (shadow input) and leave it with Tab. The picker is found by its accessible
    name (`name`, else the label — education rows label theirs "Education (UIUC): From Date") + index."""
    name = (f.get('name') or f['label']).replace('"', '\\"')
    box = page.locator(f'ui5-date-picker-xweb-calendar-widget[accessible-name="{name}"]').nth(f.get('nth') or 0).locator('input').first
    box.scroll_into_view_if_needed(); box.click(); box.fill(value); box.press('Tab'); time.sleep(0.5)   # never Enter: it submits the whole form (Save) and the page reloads
    return True


def date_value(page, f):
    name = (f.get('name') or f['label']).replace('"', '\\"')
    loc = page.locator(f'ui5-date-picker-xweb-calendar-widget[accessible-name="{name}"]')
    n = f.get('nth') or 0
    return loc.nth(n).locator('input').first.input_value() if loc.count() > n else ''


def extra_answer(f, ans):
    """Pure (tested). The answer for a UI5 date field: "Today's Date" → today as MM/DD/YYYY; otherwise the rule's date /
    text when it looks like MM/DD/YYYY. None when there is none."""
    if re.search(r"today'?s date|^date$|date signed|signature date", f.get('label') or '', re.I):
        return datetime.now().strftime('%m/%d/%Y')
    a = ans or {}
    v = str(a.get('value') or '') if a.get('status') == 'ok' else ''
    return v if re.fullmatch(r'\d{2}/\d{2}/\d{4}', v) else None


COMPANY = ''                                                      # set by run() from company_name: referral questions vs the referrer pool (JSA-195)
def answer(fields, jd='', company=None):
    qs = [{'key': f['key'], 'label': f['label'], 'type': {'combo': 'select'}.get(f['type'], f['type']), 'options': f['options']} for f in fields]
    q = {'fields': qs, 'jd': jd, 'company': COMPANY if company is None else company}
    r = subprocess.run(['node', os.path.join(HERE, 'rules_bridge.js'), os.path.abspath(RULES)], input=json.dumps(q),
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout or '{}')


def rebind(row, fields, taken):
    """Pure (tested). The field a read-back row moves to after a re-render: only when its own key is gone from the page and
    exactly ONE field (not held by another row) has its label — three School boxes share the label "School", and
    rebinding by label sent every refill into the first one (Erie 11-04). None = keep the key."""
    if any(f['key'] == row['key'] for f in fields):
        return None
    c = [f for f in fields if f['label'] == row['label'] and f['key'] not in taken]
    return c[0] if len(c) == 1 else None


def readback(page):
    """{id: value} plus {'label:<label>': value} — a re-rendered field keeps its label but gets a new id."""
    out = {}
    for f in plan(page.evaluate(READ)):
        out[f['key']] = f['value']; out.setdefault('label:' + f['label'], f['value'])
    return out


def settle(page, secs=6):
    """After a change the form may talk to the server and re-render (fast actions then hit stale elements and every
    read-back comes back empty — an employer 11-04). Wait a moment and until no busy / loading indicator is visible."""
    time.sleep(0.6)
    end = time.time() + secs
    while time.time() < end:
        busy = page.evaluate("() => [...document.querySelectorAll('[class*=busy i], [class*=loading i], [aria-busy=true], .sfLoading, #sfOverlayMgr .overlayShim')].some(e => e.offsetParent !== null && e.getBoundingClientRect().width > 0)")
        if not busy:
            return
        time.sleep(0.3)


def applied_before(company, job_id, apps_path=None):
    """Pure-ish (tested). Has he applied to `company` before (another job id in the tracker)? Company names are compared
    loosely (case, punctuation, Inc / LLC / Corp / Group dropped). Answer for "Have you ever applied … with <company>?"
    (JSA-160)."""
    def key(c):
        c = re.sub(r'[^a-z0-9 ]', ' ', str(c or '').lower())
        c = re.sub(r'\b(inc|llc|corp|corporation|co|company|group|ltd|plc|the|holdings?)\b', ' ', c)
        return ' '.join(c.split())
    apps_path = apps_path or jpaths.data('store', 'applications.jsonl')
    k = key(company)
    for line in open(apps_path, encoding='utf-8'):
        try: a = json.loads(line)
        except ValueError: continue
        if a.get('job_id') != job_id and key(a.get('company')) == k and k:
            return True
    return False


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def page_text(page):
    """Body text plus the values of read-only boxes (SPX shows "Your application has been sent" inside an input)."""
    try:
        extra = page.evaluate("() => [...document.querySelectorAll('input[readonly], textarea[readonly], input[type=text]:disabled')].map(e => e.value).join(' ')")
        return ' '.join((page.inner_text('body') + ' ' + (extra or '')).split())
    except Exception: return ''


def _visible(page, sel, secs):
    """Wait up to `secs` for a visible `sel`; True when it is there."""
    end = time.time() + secs
    while time.time() < end:
        try:
            if page.locator(sel + ':visible').count():
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _fill(page, sel, val):
    """Fill the visible `sel` (a hidden twin or a re-render must not time the run out); one retry after a re-render."""
    for i in range(2):
        try:
            page.locator(sel + ':visible').first.fill(val, timeout=8000); return
        except Exception:
            if i or not _visible(page, sel, 10):
                raise


def pw_limits(text):
    """Pure (tested). The password length rule a register page states → (min, max), each an int or None: "between 8 and
    18 characters", "8-18 characters", "must not be longer than 18 characters" (Newell 11-05), "no more than / at most /
    up to / a maximum of N characters", "at least / a minimum of N characters"."""
    t = re.sub(r'\s+', ' ', str(text or '')).lower()
    lo = hi = None
    m = re.search(r'between (\d{1,2}) and (\d{1,3}) (?:characters|chars)|(\d{1,2}) ?(?:-|–|to) ?(\d{1,3}) (?:characters|chars)', t)
    if m:
        a, b = [int(x) for x in m.groups() if x]
        lo, hi = min(a, b), max(a, b)
    m = re.search(r'(?:not (?:be )?(?:longer|more) than|no (?:longer|more) than|at most|up to|maximum (?:of |length (?:of |is )?)?|max(?:imum)?\.? (?:of )?|cannot exceed|must not exceed|not exceed|fewer than|less than) (\d{1,3}) (?:characters|chars)|(\d{1,3}) (?:characters|chars) (?:max(?:imum)?|or (?:less|fewer))', t)
    if m:
        n = int(next(g for g in m.groups() if g))
        if re.search(r'(fewer|less) than \d', m.group(0)):
            n -= 1
        hi = n if hi is None else min(hi, n)
    m = re.search(r'(?:at least|minimum (?:of |length (?:of |is )?)?|min(?:imum)?\.? (?:of )?|no (?:fewer|less) than|not (?:be )?(?:shorter|fewer|less) than) (\d{1,2}) (?:characters|chars)|(\d{1,2}) (?:characters|chars) (?:min(?:imum)?|or more)', t)
    if m:
        n = int(next(g for g in m.groups() if g))
        lo = n if lo is None else max(lo, n)
    return lo, hi


def pick_password(text, items):
    """Pure (tested). items = [(keychain item name, password), …] in order of preference (jobagent-workday first) → the
    first (name, password) whose length fits the page's rule (pw_limits), or None when none fits. An empty password never
    fits. Passwords are never logged — callers log the item name only."""
    lo, hi = pw_limits(text)
    for name, pw in items or []:
        if pw and (lo is None or len(pw) >= lo) and (hi is None or len(pw) <= hi):
            return name, pw
    return None


def keychain_items():
    """[(name, password)] — the regular Keychain item first, then the long one (wd_signin)."""
    import wd_signin as WS
    return [(WS.SERVICE, WS.keychain_password()), (WS.LONG_SERVICE, WS.keychain_password(WS.LONG_SERVICE))]


PRIVACY_LINK = re.compile(r'(read and accept|accept|open|view|review|read)\b.{0,30}\b(data )?privacy (consent |protection )?(statement|agreement|policy|notice)|^\s*data privacy (consent |protection )?(statement|agreement)\s*$', re.I)   # + "Review and Accept Data Privacy Consent Statement" (Newell 11-05, type AA)


def privacy_link(text):
    """Pure (tested). Is this link text the register form's data-privacy link? "Read and accept the data privacy statement"
    (an employer) and "… agreement" (Newell 11-05) both are; a validation line ("Please open the data privacy agreement and
    accept it") is not a link — callers try links first."""
    return bool(PRIVACY_LINK.search(re.sub(r'\s+', ' ', str(text or '')).strip()))


TERMS_LINK = re.compile(r'\b(read and accept|accept|read & accept)\b.{0,30}\bterms (of use|and conditions|of service)\b', re.I)
ACCEPT_LINK = re.compile(PRIVACY_LINK.pattern + '|' + TERMS_LINK.pattern, re.I)


def accept_link(text):
    """Pure (tested). The link the account form makes you open and accept: a data-privacy link (privacy_link) or a
    "Read and accept terms of use" link (Danfoss 11-05, the same DPCS dialog; also "… terms and conditions / of service").
    A terms link counts only with "accept" in it — "By creating an account you agree to the Terms of use" or a footer
    "Danfoss Job Portal Terms" is not one."""
    return privacy_link(text) or bool(TERMS_LINK.search(re.sub(r'\s+', ' ', str(text or '')).strip()))


ACCEPTED_RX = re.compile(r'(data privacy|privacy statement|privacy agreement|terms of use|terms and conditions)[^.!?]{0,40}?\baccepted\b', re.I)
NOT_ACCEPTED_RX = re.compile(r'\b(not|must|should|needs? to|has to|have to|to)\s+(be\s+|been\s+)*accepted\b|\bbe accepted\b', re.I)


def privacy_accepted(text, dpcs_value=''):
    """Pure (tested). Does the page say the privacy statement / terms of use were accepted? The page text has "Data privacy
    statement has been accepted." (also "Terms of use … accepted"), or the form's hidden DPCS box (`#fbclc_dpcsId`) holds a
    value — Danfoss fills it when Accept is pressed in the dialog. A demand or a refusal ("must be accepted", "has not been
    accepted") is not an acceptance."""
    t = re.sub(r'\s+', ' ', str(text or ''))
    if any(not NOT_ACCEPTED_RX.search(m.group(0)) for m in ACCEPTED_RX.finditer(t)):
        return True
    return bool(str(dpcs_value or '').strip())


def page_kind(sig):
    """Pure (tested). What the candidate site shows after Apply / sign-in, from `sig` = {app: text has "Expand all sections"
    or "My Documents", account: a visible account box (#fbclc_userName), apply_btn: a visible #fbqa_apply / Apply submit
    button, attach: a visible attach icon (My Documents upload), upload: text "Upload a Resume" / "Upload a CV" / "Upload
    your resume", signin: a visible sign-in e-mail box (#username)} →
      'application'     the application page (account already open);
      'register_apply'  ONE page with the account fields AND the application (CV upload / Apply button) — an employer, Danfoss
                        11-05 (career2.successfactors.eu: CV, fbclc_ fields, questions, signature, terms of use, Apply);
      'register'        the account form alone (Create Account, then the application opens);
      'sign_in'         the sign-in page;
      'unknown'         none of these."""
    s = sig or {}
    if s.get('app'):
        return 'application'
    if s.get('account') and (s.get('apply_btn') or s.get('attach') or s.get('upload')):
        return 'register_apply'
    if s.get('account'):
        return 'register'
    if s.get('signin'):
        return 'sign_in'
    return 'unknown'


def radio_question(texts, options):
    """Pure (tested). The question of a radio group whose own label is missing: `texts` = the inner texts of the group's
    ancestors, innermost first; the first one that still has words once every option text is removed, required star and
    trailing colon dropped, at most 250 characters, is the question. '' when none."""
    for t in texts or []:
        t = str(t or '')
        for o in sorted((str(x or '') for x in options or []), key=len, reverse=True):
            if o.strip():
                t = t.replace(o.strip(), ' ')
        t = clean_label(t)
        if re.search(r'[A-Za-z]{2,}', t) and len(t) <= 250:
            return t
    return ''


CHAT_RX = re.compile(r'chat ?bot|chatbot|phenom.?chat|career ?bot|live ?chat|chat[-_ ]?widget|\bchat\b|intercom|drift|livechat|zendesk|messenger|ada-?embed', re.I)
NOT_CHAT_RX = re.compile(r'cookie|consent|onetrust|trustarc|privacy|gdpr|recaptcha|hcaptcha|captcha|youtube|vimeo|video|map', re.I)


def chat_overlay(el):
    """Pure (tested). el = {tag, id, cls, title, name, src} of an iframe (or its fixed wrapper) on the job page → True when it is a
    chat widget that may cover "Apply now" (Danfoss 11-05: #phenomChatbotIframe, the Phenom Career Bot). A cookie /
    consent banner, a CAPTCHA or a video is never one (the cookie banner must stay untouched — type F)."""
    s = ' '.join(str((el or {}).get(k) or '') for k in ('id', 'cls', 'title', 'name', 'src'))
    return bool(CHAT_RX.search(s)) and not NOT_CHAT_RX.search(s)


CHAT_READ = r"""() => [...document.querySelectorAll('iframe, [id*=chat i], [class*=chatbot i]')].filter(e => e.getClientRects().length && getComputedStyle(e).display !== 'none' && (e.tagName === 'IFRAME' || /fixed|sticky/.test(getComputedStyle(e).position))).map((e, i) => {
  e.setAttribute('data-cx-chat', String(i));
  return {i, tag: e.tagName.toLowerCase(), id: e.id || '', cls: String(e.className || ''), title: e.getAttribute('title') || '', name: e.getAttribute('name') || '', src: e.getAttribute('src') || ''};
})"""


def hide_chat(page, log=None):
    """Hide chat widgets (chat_overlay) that can cover the Apply button — display:none on the element only, nothing is
    clicked or closed (the cookie banner stays as it is). Returns how many were hidden."""
    try:
        els = [e for e in page.evaluate(CHAT_READ) if chat_overlay(e)]
    except Exception:
        return 0
    for e in els:
        try:
            page.evaluate("(i) => { const x = document.querySelector('[data-cx-chat=\"' + i + '\"]'); if (x) x.style.setProperty('display', 'none', 'important'); }", e['i'])
        except Exception:
            pass
    if els and log:
        log(f"hid {len(els)} chat widget(s) over the page: {', '.join((e['id'] or e['title'] or e['tag'])[:30] for e in els)}")
    return len(els)


CAPTCHA_RX = re.compile(r'recaptcha|hcaptcha|captcha', re.I)
BANNER_RX = re.compile(r'cookies?|consent|onetrust|trustarc|gdpr|cookiemanager', re.I)


def cover_action(el):
    """Pure (tested). What to do about the element on top of the Apply button's centre (or its nearest fixed / sticky
    ancestor): {self, tag, id, cls, role, title, name, src, text, fixed} or None → 'none' (nothing covers it) /
    'hide_chat' (a chat widget, chat_overlay) / 'hide_banner' (a FIXED cookie / consent banner — hidden from view for the
    one click only; its Accept / Reject / Close are never pressed, type F) / 'stop' (a CAPTCHA or anything else: a dialog,
    a session-timeout message, a page element). Danfoss 11-05: div.cookiePolicy.cookiemanager (fixed, z-index 100) over
    #fbqa_apply at the page bottom — type AF."""
    if not el or el.get('self'):
        return 'none'
    ids = ' '.join(str(el.get(k) or '') for k in ('id', 'cls', 'title', 'name', 'src'))
    if CAPTCHA_RX.search(ids):
        return 'stop'
    if chat_overlay(el):
        return 'hide_chat'
    if el.get('fixed') and BANNER_RX.search(' '.join(str(el.get(k) or '') for k in ('id', 'cls', 'role', 'title', 'text'))):
        return 'hide_banner'
    return 'stop'


PRESSED_NOTE = 'pressed the final button but no confirmation page and no company e-mail — check Gmail'


def press_result(clicked, confirmed_by, button_left):
    """Pure (tested). (status, queue note) after the final Apply: confirmed → ('submitted', None); clicked → 'unconfirmed'
    with the pressed-button note; the click never landed and the button is still there → ('blocked', 'Apply not pressed …')
    — nothing was sent, never "pressed the final button"; the click failed but the button has left the page →
    ('unconfirmed', 'the Apply click failed …') — check Gmail before any retry (Danfoss 11-05, type AF)."""
    if confirmed_by:
        return 'submitted', None
    if clicked:
        return 'unconfirmed', PRESSED_NOTE
    if not button_left:
        return 'blocked', 'Apply not pressed: the button could not be clicked (covered on the page) — nothing was submitted; rerun after the fix'
    return 'unconfirmed', ('the Apply click failed (the button then left the page) and no confirmation page or company e-mail came — '
                           'check Gmail before any retry')


COVER_AT = r"""(b) => {
  b.scrollIntoView({block: 'center', inline: 'center'});
  const r = b.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
  if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) return null;
  const top = document.elementFromPoint(x, y);
  if (!top) return null;
  if (top === b || b.contains(top)) return {self: true};
  let e = top;
  for (let a = top; a && a !== document.body; a = a.parentElement) if (/fixed|sticky/.test(getComputedStyle(a).position)) { e = a; break; }
  document.querySelectorAll('[data-cx-cover]').forEach(z => z.removeAttribute('data-cx-cover'));
  e.setAttribute('data-cx-cover', '1');
  return {self: false, tag: e.tagName.toLowerCase(), id: e.id || '', cls: String(e.className || ''), role: e.getAttribute('role') || '', title: e.getAttribute('title') || '',
          name: e.getAttribute('name') || '', src: e.getAttribute('src') || '', text: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200),
          fixed: /fixed|sticky/.test(getComputedStyle(e).position)};
}"""
HIDE_COVER = r"""() => { const e = document.querySelector('[data-cx-cover]'); if (!e) return false;
  e.setAttribute('data-cx-style', e.getAttribute('style') || ''); e.style.setProperty('visibility', 'hidden', 'important'); return true; }"""
SHOW_COVER = r"""() => { const e = document.querySelector('[data-cx-cover]'); if (!e) return false;
  const s = e.getAttribute('data-cx-style'); if (s) e.setAttribute('style', s); else e.removeAttribute('style');
  e.removeAttribute('data-cx-style'); e.removeAttribute('data-cx-cover'); return true; }"""


def press_apply(page, btn, log, tries=2):
    """Press the final Apply with the page's own click (its onclick / validation runs — never a JS .click() or a form
    submit that bypasses it). Before each try the button is scrolled to the centre and the element on top of it is read
    (cover_action): a chat widget is hidden, a fixed cookie banner is hidden from view for this one click and shown again
    right after (its choices are never touched — type F), a CAPTCHA or anything else stops. Returns (clicked, why)."""
    why = ''
    for n in range(tries):
        try:
            el = btn.evaluate(COVER_AT)
        except Exception as e:
            el, why = None, f'button not readable ({type(e).__name__})'
        act = cover_action(el)
        hidden = False
        if act == 'stop':
            why = f"Apply is covered by {(el or {}).get('tag', '?')}#{(el or {}).get('id', '')}.{str((el or {}).get('cls', ''))[:40]} — not a chat widget or a cookie banner"
            log(why + ' — stopping'); return False, why
        if act == 'hide_chat':
            hide_chat(page, log)
        elif act == 'hide_banner':
            try: hidden = page.evaluate(HIDE_COVER)
            except Exception: hidden = False
            if hidden: log(f"cookie banner over Apply ({(el.get('id') or el.get('cls'))[:40]}) hidden from view for the click — its buttons untouched")
        try:
            btn.click(timeout=10000)
            log('apply clicked'); return True, ''
        except Exception as e:
            why = f'Apply click failed ({type(e).__name__})'
            log(why + (' — retrying once' if n + 1 < tries else ''))
        finally:
            if hidden:
                try: page.evaluate(SHOW_COVER)
                except Exception: pass                            # the page has moved on (submitted): nothing to restore
        time.sleep(1.5)
    return False, why




def label_from_options(label, options):
    """Pure (tested). A list whose label is only a placeholder ("Please Select:" under Acuity's veteran paragraph, 11-05)
    gets its options as the question text, so the rules see the topic ("… Protected Veteran …"); any other label is
    returned unchanged."""
    lab = clean_label(label)
    opts = [str(o).strip() for o in options or [] if str(o or '').strip()]
    if not PLACEHOLDER_LABEL.match(lab) or not opts:
        return label
    return f"{lab} ({' / '.join(opts)})"


REG_RADIOS = r"""() => {
  const optC = __OPTC__;
  const groups = {};
  document.querySelectorAll('input[type=radio]').forEach(r => { if (r.offsetParent !== null && r.name) (groups[r.name] = groups[r.name] || []).push(r); });
  const out = Object.entries(groups).map(([name, rs]) => {
    const opts = rs.map((r, i) => ({id: r.id, name: r.name, value: r.value, idx: i, dup: rs.filter(x => x.value === r.value).length > 1, c: optC(r),
                                    text: ((r.labels && r.labels[0]) ? r.labels[0].innerText : (r.getAttribute('aria-label') || r.value || '')).trim(), on: r.checked}));
    const fs = rs[0].closest('fieldset'); const lg = fs && fs.querySelector('legend');
    const texts = []; if (lg) texts.push(lg.innerText);
    let a = rs[0].parentElement; for (let i = 0; i < 6 && a; i++, a = a.parentElement) texts.push(a.innerText || '');
    return {id: 'radio:' + name, type: 'radio', native: true, texts, options: opts.map(o => o.text), radios: opts, value: (opts.find(o => o.on) || {}).text || ''};
  });
  document.querySelectorAll('[role=radiogroup]').forEach(g => {
    if (g.offsetParent === null || g.querySelector('input[type=radio]')) return;
    const opts = [...g.querySelectorAll('[role=radio]')].map(r => ({id: r.id, text: (((document.getElementById(r.getAttribute('aria-labelledby') || '') || {}).innerText) || r.innerText || '').trim(), on: r.getAttribute('aria-checked') === 'true'}));
    const lab = (document.getElementById(g.getAttribute('aria-labelledby') || '') || {}).innerText || g.getAttribute('aria-label') || '';
    const texts = [lab]; let a = g.parentElement; for (let i = 0; i < 6 && a; i++, a = a.parentElement) texts.push(a.innerText || '');
    out.push({id: g.id, type: 'radio', texts, options: opts.map(o => o.text), radios: opts, value: (opts.find(o => o.on) || {}).text || ''});
  });
  return out;
}""".replace('__OPTC__', RADIO_TEXT_JS)


OPTION_ANSWER_KEYS = ('profile_visibility',)   # saved answers whose pick pattern may answer a register radio group with no readable question (JSA-335)


def js_pattern(s):
    """'/re/flags' (answer_rules form) → compiled Python regex; None when it does not compile."""
    m = re.fullmatch(r'/(.+)/([a-z]*)', str(s or '').strip(), re.S)
    try:
        return re.compile(m.group(1), re.I if 'i' in m.group(2) else 0) if m else None
    except re.error:
        return None


def option_answer(options, saved):
    """Pure (tested). A register-form radio group with no readable question (Arthrex 11-12): `saved` = {key: [pick
    patterns '/re/flags']} for OPTION_ANSWER_KEYS. When exactly one option of the group matches exactly one saved
    answer's pattern — and no other saved answer matches any option — returns (option text, 'answers.<key>.pick (option
    content)'); otherwise None (the group still stops for Joey)."""
    opts = [str(o or '').strip() for o in options or [] if str(o or '').strip()]
    hits = []                                                     # (key, option)
    for key, pats in (saved or {}).items():
        rxs = [r for r in (js_pattern(x) for x in (pats if isinstance(pats, (list, tuple)) else [pats])) if r]
        for o in opts:
            if any(r.search(o) for r in rxs):
                hits.append((key, o))
    if len(hits) != 1:
        return None
    return hits[0][1], f'answers.{hits[0][0]}.pick (option content)'


def saved_option_picks():
    """{key: [pick patterns]} of OPTION_ANSWER_KEYS from config (answers.<key>.pick)."""
    import jsa_profile
    out = {}
    for k in OPTION_ANSWER_KEYS:
        p = jsa_profile.get(f'answers.{k}.pick')
        if p:
            out[k] = p if isinstance(p, list) else [p]
    return out


def register_radios(page, log, need):
    """Answer every radio group on the register form (e.g. "Make My Profile Visible to" — Newell 11-05) from the rules
    (config answers.profile_visibility …); a group with no answer goes to `need` (→ needs-user). True when all are set."""
    try:
        groups = radio_texts(page.evaluate(REG_RADIOS))
    except Exception:
        return True
    fields = []
    for g in groups:
        g['label'] = radio_question(g.get('texts'), g.get('options'))
        if g['label']:
            fields.append(g)
        elif not g.get('value'):
            hit = option_answer(g.get('options'), saved_option_picks())      # JSA-335: exactly one option matches a saved pick
            if not hit:
                need.append(f"register form: a radio group with no readable question (options: {' / '.join(g.get('options') or [])[:120]})")
                continue
            val, rule = hit
            try:
                radio_set(page, g, val)
                now_v = next((x.get('value') for x in radio_texts(page.evaluate(REG_RADIOS)) if x['id'] == g['id']), '')
                if N(now_v).lower() != N(val).lower():
                    need.append(f"register form: radio group without a question — set {val[:40]!r}, page shows {str(now_v)[:40]!r}")
                else:
                    log(f"register form: radio group without a question → {val[:60]} ({rule}, read back)")
            except Exception as e:
                need.append(f"register form: radio group without a question — could not set {val[:40]!r} ({type(e).__name__})")
    if not fields:
        return not need
    ans = answer([{'key': g['id'], 'label': g['label'], 'type': 'radio', 'options': g['options']} for g in fields])
    for g in fields:
        a = ans.get(g['id']) or {}
        if a.get('status') != 'ok' or not a.get('value'):
            if not g.get('value'):
                need.append(f"register form: {g['label'][:80]} (options: {' / '.join(g['options'])[:140]}) — no answer in config")
            continue
        try:
            if N(g.get('value') or '').lower() != N(a['value']).lower():
                radio_set(page, g, a['value'])
            now_v = next((x.get('value') for x in radio_texts(page.evaluate(REG_RADIOS)) if x['id'] == g['id']), '')   # read back: the group must show the answer
            if N(now_v).lower() != N(a['value']).lower():
                need.append(f"register form: {g['label'][:80]} — set {a['value'][:40]!r}, page shows {str(now_v)[:40]!r}"); continue
            log(f"register form: {g['label'][:60]} → {a['value'][:60]} ({a.get('rule')}, read back)")
        except Exception as e:
            need.append(f"register form: {g['label'][:80]} — could not set {a['value'][:40]!r} ({type(e).__name__})")
    return not need


def sign_in(page, log, create_first=False, wait_captcha_min=0, need=None):
    """On the career4 Sign In page: e-mail + Keychain password; no account → Create Account (fbclc_ form, a Keychain
    password that fits the page's length rule, data privacy statement / agreement accepted — Joey 2026-11-04, radio groups
    answered from config). Returns True when the application page is open; what Joey must answer goes to `need`."""
    need = need if need is not None else []
    import wd_signin as WS
    pw = WS.keychain_password()
    if not pw:
        log('no Keychain password (jobagent-workday)'); return False
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import jsa_profile
    email = jsa_profile.get('email') or jsa_profile.get('contact.email') or ''
    if not create_first and page.locator('#username').count() and page.locator('#username').first.is_visible():
        page.fill('#username', email); page.fill('#password', pw)
        page.locator('button:has-text("Sign In"), input[value="Sign In"]').first.click(); time.sleep(6)
        if on_application(page):
            log('signed in'); return True
        if not re.search(r'invalid|incorrect|not (found|registered)|does not exist|failed', page_text(page), re.I):
            return on_application(page)
        log('sign-in refused — creating the account')
    a = page.locator('a').filter(has_text=re.compile(r'^\s*create an account\s*$', re.I))
    if not a.count():
        log('no Create an account link'); return False
    href = a.first.get_attribute('href') or ''
    import urllib.parse
    if href and not href.startswith(('#', 'javascript')):        # open the register URL itself: on an employer / Erie the click only re-validates the sign-in form
        page.goto(urllib.parse.urljoin(page.url, href), wait_until='domcontentloaded', timeout=60000)
    else:
        a.first.click()
    if not _visible(page, '#fbclc_userName', 20):                 # the register page can take > 10 s (Erie)
        log('register page did not open'); return False
    time.sleep(1)                                                 # let a late re-render settle before typing (an employer 11-04: the box vanished under page.fill)
    got = pick_password(page_text(page), keychain_items())        # the page's own length rule: Newell allows at most 18 characters (11-05)
    if not got:
        lo, hi = pw_limits(page_text(page))
        need.append(f'register form: no Keychain password fits the site rule ({lo or "?"}–{hi or "?"} characters) — Joey')
        log('register form: no Keychain password fits the stated length rule'); return False
    log(f'register form: password from Keychain item {got[0]} (fits the stated rule)')
    pw = got[1]
    _fill(page, '#fbclc_userName', email); _fill(page, '#fbclc_emailConf', email)
    _fill(page, '#fbclc_pwd', pw); _fill(page, '#fbclc_pwdConf', pw)
    first, last = (jsa_profile.get('name.first') or ''), (jsa_profile.get('name.last') or '')
    _fill(page, '#fbclc_fName', first); _fill(page, '#fbclc_lName', last)
    for sel, rx in (('#fbclc_ituCode', r'^United States \(\+1\)$'), ('#fbclc_country', r'^United States$')):
        if page.locator(sel).count():
            lab = next((o for o in page.locator(sel + ' option').all_inner_texts() if re.match(rx, o.strip())), None)
            if lab: page.select_option(sel, label=lab)
    phone = re.sub(r'\D', '', jsa_profile.get('phone') or jsa_profile.get('contact.phone') or '')[-10:]
    if page.locator('#fbclc_phoneNumber:visible').count(): _fill(page, '#fbclc_phoneNumber', phone)
    for cb in ('#fbclc_emailEnabled', '#fbclc_campaignEmailEnabled'):   # job-alert / marketing mails: off (they come ticked on some sites)
        if page.locator(cb).count() and page.locator(cb).first.is_checked():
            page.locator(cb).first.uncheck()
    accept_privacy(page, log)                                     # "… data privacy statement" (an employer) or "… agreement" (Newell 11-05)
    if not register_radios(page, log, need):                      # "Make My Profile Visible to" (Newell 11-05): Joey's answer from config
        log('register form: ' + ' | '.join(need)[:300]); return False
    if captcha_on(page):                                          # a reCAPTCHA on the register page (Erie): Joey ticks, the runner presses Create Account at once
        if wait_captcha_min <= 0:
            log('register page has a CAPTCHA — Joey'); return False
        import run_form as RF
        RF.push('求职 runner：人机验证', "注册页 — 勾一下「I'm not a robot」，runner 会立刻建账号")
        log(f'register CAPTCHA: waiting up to {wait_captcha_min:g} min for the tick')
        if not wait_token(page, wait_captcha_min * 60):
            log('register CAPTCHA not ticked in time'); return False
    page.locator('#fbclc_createAccountButton').click(); time.sleep(8)
    ok = on_application(page)
    log('account created' if ok else 'account form sent — application page not open: ' + page_text(page)[:200])
    return ok


def wait_token(page, secs):
    """Wait until the page's reCAPTCHA response box has a value (Joey ticked it); True then."""
    end = time.time() + secs
    while time.time() < end:
        try:
            if page.evaluate("() => { const t = document.querySelector('textarea[name=g-recaptcha-response], #g-recaptcha-response'); return !!(t && t.value); }"):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def captcha_on(page):
    return any(re.search(r'google\.com/recaptcha|recaptcha/api2|hcaptcha\.com', f.url or '') for f in page.frames)


PAGE_SIG = r"""() => {
  const vis = s => [...document.querySelectorAll(s)].some(e => e.offsetParent !== null);
  const t = document.body ? document.body.innerText : '';
  return {app: /Expand all sections|My Documents/.test(t), account: vis('#fbclc_userName'), apply_btn: vis('#fbqa_apply, [id$="_submitBtn"][role=button]'),
          attach: vis('[id$="_attachIcon"]'), upload: /Upload (a|your) (Resume|CV)\b/i.test(t), signin: vis('#username')};
}"""


def page_sig(page):
    try:
        return page.evaluate(PAGE_SIG)
    except Exception:
        return {}


def on_application(page):
    """The application is open: the application page, or the one-page register-and-apply form (an employer, Danfoss) — page_kind."""
    return page_kind(page_sig(page)) in ('application', 'register_apply')


ACCOUNT_LABELS = {'fbclc_userName': 'E-mail', 'fbclc_emailConf': 'Retype e-mail', 'fbclc_pwd': 'Password', 'fbclc_pwdConf': 'Retype password',
                  'fbclc_fName': 'First name', 'fbclc_lName': 'Last name', 'fbclc_phoneNumber': 'Phone number',
                  'fbclc_ituCode': 'Country/Region code', 'fbclc_country': 'Country/Region of residence',
                  'fbclc_emailEnabled': 'Job notifications (off)', 'fbclc_campaignEmailEnabled': 'Marketing e-mails (off)'}


def account_ok(key, want, got):
    """Pure (tested). Did the account box `key` keep what the runner typed? Phone: the last 10 digits equal; e-mail: equal
    ignoring case; a checkbox: want '' (off) = got ''; anything else: equal after whitespace is collapsed. An empty want is
    never ok (the box had to be filled), except a checkbox that must stay off."""
    w, g = N(want), N(got)
    if key in ('fbclc_emailEnabled', 'fbclc_campaignEmailEnabled'):
        return g == w
    if not w:
        return False
    if key == 'fbclc_phoneNumber':
        return re.sub(r'\D', '', g)[-10:] == re.sub(r'\D', '', w)[-10:]
    if key in ('fbclc_userName', 'fbclc_emailConf'):
        return g.lower() == w.lower()
    return g == w


def fill_account(page, log):
    """The register-and-apply page (an employer, an employer on career5.successfactors.eu, Danfoss on career2.successfactors.eu): the
    fbclc_ account fields sit on the application page. E-mail twice, a Keychain password that fits the page's length rule
    twice (pick_password, type T(c)), name, phone, country code / country; job-alert / marketing boxes off; the data privacy
    / terms-of-use link accepted. Every box is read back (the password only compared, never logged). Returns (the handled
    field ids, read-back rows of type 'account')."""
    import jsa_profile
    got = pick_password(page_text(page), keychain_items())       # the page's own length rule (Newell / Danfoss 11-05: at most 18)
    pw = got[1] if got else ''
    log(f'account fields: password from Keychain item {got[0]}' if got else 'account fields: no Keychain password fits the stated length rule — password left empty')
    email = jsa_profile.email()
    done, want = set(), {}
    for sel, val in (('#fbclc_userName', email), ('#fbclc_emailConf', email)) + ((('#fbclc_pwd', pw), ('#fbclc_pwdConf', pw)) if pw else ()) + (
                     ('#fbclc_fName', jsa_profile.get('name.first') or ''), ('#fbclc_lName', jsa_profile.get('name.last') or ''),
                     ('#fbclc_phoneNumber', re.sub(r'\D', '', jsa_profile.get('phone') or jsa_profile.get('contact.phone') or '')[-10:])):
        loc = page.locator(sel)
        if loc.count() and loc.first.is_visible():
            loc.first.fill(val); done.add(sel[1:]); want[sel[1:]] = val
    for sel, rx in (('#fbclc_ituCode', r'^United States \(\+1\)$'), ('#fbclc_country', r'^United States$')):
        if page.locator(sel).count():
            lab = next((o.strip() for o in page.locator(sel + ' option').all_inner_texts() if re.match(rx, o.strip())), None)
            if lab: page.select_option(sel, label=lab); done.add(sel[1:]); want[sel[1:]] = lab
    for cb in ('#fbclc_emailEnabled', '#fbclc_campaignEmailEnabled'):
        if page.locator(cb).count() and page.locator(cb).first.is_checked():
            page.locator(cb).first.uncheck()
        done.add(cb[1:])
        if page.locator(cb).count(): want[cb[1:]] = ''
    accept_privacy(page, log)
    rows = [{'key': k, 'label': 'Account: ' + ACCOUNT_LABELS.get(k, k), 'type': 'account', 'required': k not in CHECK_KEYS,
             'want': '(Keychain password)' if k in SECRET_KEYS else w, 'rule': 'account'} for k, w in want.items()]   # the password itself is never stored
    account_check(page, rows)
    bad = [r['label'] for r in rows if not r['ok']]
    log(f'account fields on the application page: {len(done)} set, {len(rows) - len(bad)}/{len(rows)} read back (password typed by the script)' + (f" — not kept: {', '.join(bad)}" if bad else ''))
    return done, rows


SECRET_KEYS = ('fbclc_pwd', 'fbclc_pwdConf')
CHECK_KEYS = ('fbclc_emailEnabled', 'fbclc_campaignEmailEnabled')


def account_value(page, k):
    """What account box `k` holds now: a text box's value, a select's chosen option text, a checkbox 'checked' / ''."""
    loc = page.locator('[id="' + k + '"]').first
    try:
        tag = loc.evaluate('e => e.tagName + ":" + e.type')
        if tag.endswith(':checkbox'):
            return 'checked' if loc.is_checked() else ''
        if tag.startswith('SELECT'):
            return loc.evaluate('e => (e.options[e.selectedIndex] || {}).text || ""').strip()
        return loc.input_value()
    except Exception:
        return ''


def account_check(page, rows):
    """Read the account rows back from the page (in place: row['page'], row['ok']). The two password boxes must be
    non-empty and equal — compared on the page, the value never leaves it."""
    for r in rows:
        if r.get('type') != 'account':
            continue
        g = account_value(page, r['key'])
        if r['key'] in SECRET_KEYS:
            other = account_value(page, 'fbclc_pwdConf' if r['key'] == 'fbclc_pwd' else 'fbclc_pwd')
            r['ok'] = bool(g) and g == other
            r['page'] = '(Keychain password)' if r['ok'] else ('(the two boxes differ)' if g else '')
        else:
            r['ok'] = account_ok(r['key'], r['want'], g)
            r['page'] = g or ('off' if r['key'] in CHECK_KEYS and r['ok'] else '')


def is_accepted(page):
    """privacy_accepted on the live page: its text, or the hidden DPCS box #fbclc_dpcsId (Danfoss)."""
    try:
        v = page.evaluate("() => { const e = document.getElementById('fbclc_dpcsId'); return e ? e.value : ''; }")
    except Exception:
        v = ''
    return privacy_accepted(page_text(page), v)


def accept_privacy(page, log):
    """Open the data privacy statement / agreement link or the "Read and accept terms of use" link (accept_link — Danfoss
    11-05) and press Accept in its dialog (Joey 2026-11-04 「同意」); True when the page then says it was accepted."""
    if is_accepted(page):
        log('data privacy statement / terms of use: already accepted'); return True
    link = page.locator('a:visible, [role=link]:visible, [role=button]:visible, button:visible').filter(has_text=ACCEPT_LINK)   # links first: a validation line also names the agreement (Newell 11-05)
    if not link.count():
        link = page.get_by_text(ACCEPT_LINK).filter(has_not_text=re.compile(r'^\s*please\b', re.I))
    if not link.count():
        return False
    link.first.scroll_into_view_if_needed(); link.first.click(); time.sleep(2)
    acc = page.locator('#sfOverlayMgr button:has-text("Accept"), #sfOverlayMgr input[value="Accept"]')
    if acc.count() and acc.first.is_visible():
        acc.first.click(); time.sleep(1.5)
    ok = False
    for _ in range(12):                                           # the "has been accepted" line appears a moment later (SPX)
        ok = is_accepted(page)
        if ok: break
        time.sleep(0.5)
    log('data privacy statement / terms of use: ' + ('accepted' if ok else 'Accept pressed, not confirmed on the page'))
    return ok


DOC_RX = {0: r'(?:Resume|CV)(?:\s*/\s*(?:CV|Resume))?\s+Download document\s+(\S+?\.(?:pdf|docx?|txt|rtf))', 1: r'Cover letter\s+Download document\s+(\S+?\.(?:pdf|docx?|txt|rtf))'}


def attached_name(text, index):
    """Pure (tested). The file already attached in My Documents block `index` (0 resume, 1 cover letter), read from the
    page text ("Resume Download document <name>"), or ''."""
    m = re.search(DOC_RX.get(index, r'$^'), N(re.sub(r'[\ue000-\uf8ff]', ' ', str(text or ''))), re.I)   # icon glyphs sit between the label and the link (SPX)
    return m.group(1) if m else ''


BLOCK_FILE = r"""(index) => {
  const icons = [...document.querySelectorAll('[id$="_attachIcon"]')].filter(e => e.offsetParent !== null);
  const ic = icons[index]; if (!ic) return '';
  const pre = ic.id.replace(/_attachIcon$/, '');
  const lab = document.getElementById(pre + '_attachDownloadLabel'), link = document.getElementById(pre + '_attachDownloadLabelLink');
  return lab && link && lab.offsetParent !== null ? (link.innerText || '').trim() : '';
}"""


def block_file(page, index):
    """The file name shown in upload block `index` itself (its download link — Danfoss's "CV/Resume" block, 11-05), or ''."""
    try:
        t = N(page.evaluate(BLOCK_FILE, index))
    except Exception:
        return ''
    return t if re.search(r'\.(pdf|docx?|txt|rtf)$', t, re.I) else ''


def shown_file(page, index):
    return attached_name(page_text(page), index) or block_file(page, index)


def close_overlay(page):
    for sel in ('#sfOverlayMgr button:has-text("Cancel")', '#sfOverlayMgr button[id$="closeIconBtn"]'):
        b = page.locator(sel)
        if b.count() and b.first.is_visible():
            b.first.click(); time.sleep(0.8); return


def upload(page, index, path, log, what):
    """My Documents block `index` (0 resume, 1 cover letter). Same file already attached → keep it. Another file attached →
    the icon is a delete button: confirm (OK), then upload. Empty → the icon opens the source dialog whose file box
    uploads on its own. Returns True when the file name shows in the block."""
    name = os.path.basename(path)
    cur = shown_file(page, index)
    if cur == name:
        log(f'{what}: already attached ({name})'); return True
    icons = page.locator('[id$="_attachIcon"]:visible')
    if icons.count() <= index:
        log(f'{what}: no attach icon'); return False
    if cur:                                                       # replace: delete the old file first (Resume on the account from an earlier run)
        icons.nth(index).scroll_into_view_if_needed(); icons.nth(index).click(); time.sleep(1.5)
        ok = page.locator('#sfOverlayMgr button:has-text("OK")')
        if not ok.count():
            close_overlay(page); log(f'{what}: no delete confirmation'); return False
        ok.first.click(); time.sleep(2.5)
        icons = page.locator('[id$="_attachIcon"]:visible')
    icons.nth(index).scroll_into_view_if_needed(); icons.nth(index).click(); time.sleep(2)
    fi = page.locator('#sfOverlayMgr input[type=file]')
    if not fi.count():
        close_overlay(page); log(f'{what}: no file box in the dialog'); return False
    fi.first.set_input_files(path)
    for _ in range(40):                                           # the block re-renders slowly (SPX cover letter took > 10 s)
        time.sleep(0.5)
        if shown_file(page, index) == name:
            log(f'{what}: uploaded ({name})'); return True
    close_overlay(page)
    log(f'{what}: NOT shown after upload ({name})'); return False


APPLY_LINKS_JS = r"""() => { const vis = e => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
  const sap = [...document.querySelectorAll('a[href*="/talentcommunity/apply/"]')].map(a => ({ href: a.getAttribute('href') || '', visible: vis(a) }));
  let shadow = false; const w = r => r.querySelectorAll('*').forEach(e => { if (e.shadowRoot) { e.shadowRoot.querySelectorAll('a, button').forEach(x => {
    if (/^\s*apply now/i.test(x.textContent || '') && vis(x)) shadow = true; }); w(e.shadowRoot); } });
  w(document); return { sap, shadow }; }"""

CUSTOM_WIZARD = ("the site's own Apply now (a web component) opens the company's own application wizard, not the SAP "
                 "SuccessFactors form — no runner fills it (careers.knorr-bremse.com, JSA-222)")


def custom_apply_widget(info):
    """True when the job page's SAP apply link is there only hidden (zero size) and the visible "Apply now" sits inside a
    web component's shadow root: careers.knorr-bremse.com (KB Signaling 11-05) draws its own button, which opens a
    Knorr-Bremse 4-step wizard; the hidden SAP link leads back to the home page. The visible-text fallback clicked a
    covered copy and waited 10 s twice (JSA-222). A visible SAP link, a light-DOM "Apply now" button (Celestica / an employer
    dropdown) or no SAP link at all → False (handled as before). `info` = {sap: [{href, visible}], shadow: bool}."""
    info = info or {}
    sap = [l for l in info.get('sap') or [] if re.search(r'/talentcommunity/apply/\d+', l.get('href') or '')]
    return bool(sap) and not any(l.get('visible') for l in sap) and bool(info.get('shadow'))


def click_apply(page):
    """Job page → the job's Apply: its /talentcommunity/apply/ link, else a visible "Apply now" link, else the "Apply now"
    dropdown button and its "Apply Now" item (Celestica, an employer). Returns an error text, or '' when clicked."""
    for _ in range(10):                                           # the job's own Apply link (SPX also has a header "Apply Now" that only opens the job search)
        a = page.locator('a[href*="/talentcommunity/apply/"]:visible')
        if a.count():
            break
        time.sleep(0.5)
    if not a.count():
        if custom_apply_widget(page.evaluate(APPLY_LINKS_JS)):
            return CUSTOM_WIZARD
        a = page.locator('a:visible').filter(has_text=re.compile(r'^\s*apply now', re.I))
    if a.count():
        a.first.click(); return ''
    b = page.locator('button:visible').filter(has_text=re.compile(r'^\s*apply now', re.I))
    if not b.count():
        return 'no Apply now link or button'
    b.first.click(); time.sleep(1.2)
    item = page.locator('a:visible, li:visible a').filter(has_text=re.compile(r'^\s*apply now\s*$', re.I))
    if not item.count():
        return 'Apply now dropdown: no Apply Now item'
    item.first.click(); return ''


def wait_form(page, secs=30):
    """Wait for the application form, a visible sign-in / register box or a CAPTCHA (the URL may not change: the form is
    swapped in by script; an employer's sign-in page can take > 15 s)."""
    for _ in range(int(secs * 2)):
        time.sleep(0.5)
        if on_application(page) or page.locator('#username:visible, #fbclc_userName:visible').count() or captcha_on(page):
            break
    time.sleep(1)


def run(page, job_url, resume, cover_pdf, log, out, folder=None, jd='', company_name='', job_id='', wait_captcha_min=0, new_account=False):
    global COMPANY
    COMPANY = company_name or ''                                  # referral questions (JSA-195)
    res = {'status': 'blocked', 'problems': [], 'fields': [], 'unknown': []}
    page.goto(job_url, wait_until='domcontentloaded', timeout=60000); time.sleep(4)
    if re.search(r'no longer available|page you are trying to (reach|access)|job not found', page_text(page), re.I) or '/errorpage' in page.url:
        res['status'] = 'closed'; res['problems'].append('posting closed'); return res
    # never touch the cookie banner: closing it (an employer) stops Apply from opening the form (2026-11-04)
    hide_chat(page, log)                                          # a chat widget iframe can sit over "Apply now" (Danfoss 11-05: #phenomChatbotIframe)
    try:
        err = click_apply(page)
    except Exception as e:                                        # the click timed out: something covers the button — hide chat widgets once more, retry
        log(f'Apply click failed ({type(e).__name__}) — hiding chat widgets and retrying once')
        time.sleep(2); hide_chat(page, log); err = click_apply(page)
    if err:
        res['problems'].append(err); return res
    wait_form(page)
    if 'An error occurred while processing your request' in page_text(page):   # an SAP error page now and then (an employer, Erie): open the job again and retry once
        log('SAP error page after Apply — retrying once from the job page')
        page.goto(job_url, wait_until='domcontentloaded', timeout=60000); time.sleep(4); hide_chat(page, log)
        if not click_apply(page):
            wait_form(page)
    log(f"after Apply: url {page.url[:90]} · page {page_kind(page_sig(page))} · sign-in box {page.locator('#username:visible').count()} · text {page_text(page)[:120]!r}")
    need = []                                                     # register-form questions only Joey can answer (profile visibility …)
    if new_account and not on_application(page):                 # no account yet (Joey): go straight to Create Account, skip the sign-in attempt
        if not sign_in(page, log, create_first=True, wait_captcha_min=wait_captcha_min, need=need):
            if need:
                res['unknown'] += need; res['status'] = 'needs-user'; return res
            res['problems'].append('account creation did not open the application (see run_log)'); return res
    if not on_application(page) and captcha_on(page):
        if wait_captcha_min > 0:                                  # Celestica / Erie: Joey ticks the sign-in CAPTCHA, the runner signs in at once
            import run_form as RF
            RF.push('求职 runner：人机验证', f"{company_name[:40]} 登录页 — 勾一下「I'm not a robot」，runner 会接着登录")
            log(f'sign-in CAPTCHA: waiting up to {wait_captcha_min:g} min for the tick')
            if not wait_token(page, wait_captcha_min * 60):
                res['problems'].append('CAPTCHA (reCAPTCHA) on the SuccessFactors sign-in page — not ticked in time'); res['status'] = 'captcha'; return res
            log('sign-in CAPTCHA ticked by Joey')
        else:
            res['problems'].append('CAPTCHA (reCAPTCHA) on the SuccessFactors sign-in page — Joey'); res['status'] = 'captcha'; return res
    if not on_application(page) and not sign_in(page, log, need=need):
        if need:
            res['unknown'] += need; res['status'] = 'needs-user'; return res
        res['problems'].append('sign-in / account creation did not open the application (see run_log)'); return res
    ex = page.get_by_text('Expand all sections')
    if ex.count(): ex.first.click(); time.sleep(2)
    acct, acct_rows = fill_account(page, log) if page.locator('#fbclc_userName:visible').count() else (set(), [])   # register-and-apply on one page (an employer, Danfoss 11-05)
    if acct:                                                      # the register-and-apply page refuses Apply until the privacy statement / terms of use are accepted (an employer, Danfoss)
        okp = is_accepted(page)
        res.setdefault('extra_rows', []).extend(acct_rows)
        res['extra_rows'].append({'key': 'privacy', 'label': 'Data privacy statement / terms of use accepted', 'type': 'file', 'required': True,
                                  'want': 'accepted', 'page': 'accepted' if okp else '', 'ok': okp})
        if not okp:
            res['problems'].append('data privacy statement / terms of use not accepted on the page')
        if 'fbclc_pwd' not in acct:
            res['unknown'].append('account password: no Keychain password fits the site rule — Joey')
    rows = list(res.pop('extra_rows', []))
    for idx, (lab, path) in enumerate((('Resume', resume), ('Cover letter', cover_pdf))):
        if not path:
            continue
        if idx and page.locator('[id$="_attachIcon"]:visible').count() <= idx and not attached_name(page_text(page), idx):
            log(f'{lab}: no slot on this form — skipped'); continue        # an employer has no cover-letter box
        try:
            ok = upload(page, idx, path, log, lab)
        except Exception as e:
            close_overlay(page); ok = False; log(f'{lab}: upload error {type(e).__name__}: {str(e)[:120]}')
        rows.append({'key': lab, 'label': lab, 'type': 'file', 'required': lab == 'Resume', 'want': os.path.basename(path),
                     'page': os.path.basename(path) if ok else '', 'ok': ok})
        if not ok:
            res['problems'].append(f'{lab}: file not shown after upload')
    fix_split_words(page, log)                                    # BEFORE the rows are matched to the facts (an employer 11-05: "HYDE P ARK" was repaired only after matching)
    edu_rows, edu_keys = fill_education(page, log)
    rows += edu_rows
    for _ in range(2):                                            # "If Yes, anticipated graduation date" opens after "currently a student"
        extra, k2 = fill_education(page, log)
        new = [r for r in extra if r['key'] not in {x['key'] for x in rows}]
        rows += new; edu_keys |= k2
        if not new: break
    bg_rows, bg_keys, bg_secs = SB.fill_background(page, log, combo_options, combo_set, N)   # Previous Employment / Formal Education rows from the facts (an employer)
    rows += bg_rows
    ce_rows, ce_keys = CE.fill_combo_education(page, log, plan, READ, combo_options, _open, css, N, skip=set(edu_keys) | set(bg_keys) | set(acct), date_set=date_set)   # School / Degree / Major combo rows (Erie) + their From / To Date boxes (type AE)
    rows += ce_rows
    res['unknown'] += [r['ask'] for r in ce_rows if r.get('ask')]   # a required education date with no fact on file (type AE)
    fields = [f for f in plan(page.evaluate(READ)) if f['key'] not in edu_keys and f['key'] not in acct and f['key'] not in bg_keys and f['key'] not in ce_keys and not f['key'].startswith('fbclc_')
              and not COOKIE_RX.search(f['label'])]   # cookie-consent switches are never touched (type F; Danfoss's banner panel holds checkboxes)
    for x in read_extra(page):                           # radiogroups and UI5 date pickers live outside the plain inputs
        lab = clean_label(x.get('label') or '') or (radio_question(x.get('texts'), x.get('options')) if x['type'] == 'radio' else '')
        if lab and x['id'] not in ce_keys and not (x['type'] == 'date' and x.get('sec') in bg_secs):   # education-row dates: set by sf_combo_edu (type AE)
            fields.append({'key': x['id'], 'label': lab, 'type': x['type'], 'required': bool(x.get('required')), 'options': x.get('options') or [],
                           'radios': x.get('radios') or [], 'list': '', 'value': x.get('value') or '', 'nth': x.get('nth') or 0})
    for f in fields:                                              # a box that re-rendered after the early repair (fix_split_words): repair again
        if split_fix(f):
            page.locator(css(f['key'])).first.fill(unsplit(f['value'])); log(f"fixed split words: {f['value'][:40]!r} → {unsplit(f['value'])[:40]!r}")
            f['value'] = unsplit(f['value'])
    for f in fields:
        if f['type'] == 'combo':
            try: f['options'] = combo_options(page, f)
            except Exception as e: f['error'] = f'options: {type(e).__name__}'
    for f in fields:                                              # "Please Select:" as the only label (Acuity veteran list 11-05): the options name the topic
        if f['type'] in ('combo', 'select', 'radio'):
            f['label'] = label_from_options(f['label'], f.get('options'))
    ans = answer(fields, jd)
    for f in fields:                                              # "Have you ever applied … with <company>?" — from the tracker (JSA-160)
        if (ans.get(f['key']) or {}).get('rule') == 'applied_here_before' or (ans.get(f['key']) or {}).get('why', '').endswith('applied_here_before'):
            yes = applied_before(company_name, job_id)
            pick = next((o for o in f.get('options') or [] if o.lower() == ('yes' if yes else 'no')), 'Yes' if yes else 'No')
            ans[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'applied_here_before:tracker', 'value': pick}
    for f in fields:                                              # a paginated list read only in part (Country stops at "Slovakia"): answer as text, then filter by typing
        a = ans.get(f['key']) or {}
        if f['type'] == 'combo' and len(f.get('options') or []) >= 90 and a.get('status') != 'ok':
            t = answer([{'key': 'x', 'label': f['label'], 'type': 'text', 'options': []}], jd).get('x') or {}
            if t.get('status') == 'ok' and t.get('value'):
                ans[f['key']] = dict(t, label=f['label'], rule=str(t.get('rule')) + ':typed')
    for f in fields:                                              # a source list naming boards (LinkedIn / Indeed …) with no "job board" option (an employer): the row's OWN board when listed (Kenworth came from LinkedIn); else the rule's answer stays ("Other", an employer rule D)
        a = ans.get(f['key']) or {}
        opts = f.get('options') or []
        per_site = any(SITE_BOARD.search(o) for o in opts)        # "Job Board - Glassdoor / - Indeed / - Other" + "LinkedIn" (an employer 11-05): the generic /job board/ pick took the first site
        if f['type'] in ('combo', 'select', 'radio') and (a.get('rule') == 'how_heard' or HEARD.search(f['label'])) and (per_site or not any(re.search(r'job\s*board|recruitment website', o, re.I) for o in opts)):
            pick = job_board.board_pick(opts, JOB.get('source') or JOB.get('sources'), JOB.get('url'), board_defaults() if per_site else [])
            if pick:
                ans[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'how_heard_board', 'value': pick}
    prev = None
    for f in fields:                                              # "If Other Source, specify here" after a list answered Other
        board = other_board(str((ans.get(prev['key']) or {}).get('value') or ''), JOB) if prev and f['type'] in ('text', 'textarea') and OTHER_TEXT.search(f['label']) else None
        if board:                                                 # "Job Boards-Other (specify name below)" → the board's name, not "N/A" (Newell 11-05, JSA-205)
            ans[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'other_text:job_board', 'value': board}
        elif prev and f['type'] in ('text', 'textarea') and OTHER_TEXT.search(f['label']) and str((ans.get(prev['key']) or {}).get('value') or '').lower().startswith('other'):
            t = answer([{'key': 'x', 'label': prev['label'], 'type': 'text', 'options': []}], jd).get('x') or {}
            if t.get('status') == 'ok' and t.get('value') and not str(t['value']).lower().startswith('other'):
                ans[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'other_text:' + str(t.get('rule')), 'value': t['value']}
        prev = f if f['type'] in ('combo', 'select', 'radio') else (prev if f['type'] in ('text', 'textarea') and IF_FOLLOW.search(f['label']) else None)
    ans, essay_problem = ES.step([dict(f, kind=f['type']) for f in fields], ans, folder, prefix='sf_')   # JSA-318: prose boxes from open_answers.md, else questions.json
    if essay_problem:
        res['problems'].append(essay_problem); log(essay_problem)
    ans = limit_gate(fields, ans)                                 # JSA-312: an answer the box's own limits refuse is never typed in
    for f in fields:
        if f['type'] == 'date':                                   # UI5 date picker: today / the rule's MM/DD/YYYY
            row = dict(f); v = extra_answer(f, ans.get(f['key']))
            row['want'] = v; row['rule'] = 'date'
            if v:
                try: date_set(page, f, v)
                except Exception as e: row['error'] = f'{type(e).__name__}: {str(e)[:100]}'
            elif f['required']:
                res['unknown'].append(f['label'])
            rows.append(row); continue
        row = dict(f); a = ans.get(f['key']) or {}
        if f.get('value') and a.get('status') != 'ok':           # already filled from the account (name, e-mail, phone)
            row['want'] = f['value']; row['rule'] = 'prefilled'; rows.append(row); continue
        try:
            if a.get('status') != 'ok' or a.get('leave'):
                row['want'] = None; row['why'] = a.get('why')
                if f['required'] and not a.get('leave'):
                    res['unknown'].append(f['label'] + (f" (options: {' / '.join(f['options'][:6])})" if f['options'] else '') +
                                          (f" — {a['why']}" if "breaks the box's limit" in str(a.get('why') or '') else ''))
                rows.append(row); continue
            want = a.get('value'); row['want'] = want; row['rule'] = a.get('rule')
            if f.get('value') and N(f['value']).lower() == N(want).lower():   # already right: never touch it (re-picking Country reloads the whole form)
                rows.append(row); continue
            if f['type'] == 'radio':
                radio_set(page, f, want)
            elif f['type'] == 'combo':
                combo_set(page, f, want)
                if re.search(r'race|ethnic', f['label'], re.I): log(f"set {f['label']}: {page.locator(css(f['key'])).first.input_value()!r}")
            elif f['type'] == 'select':
                page.select_option(css(f['key']), label=want)
            elif f['type'] == 'checkbox':
                cb = page.locator(css(f['key'])).first
                if not cb.is_checked(): cb.check(force=True)
                row['want'] = 'checked'
            else:
                page.locator(css(f['key'])).first.fill(str(want))
        except Exception as e:
            row['error'] = f'{type(e).__name__}: {str(e)[:120]}'
        rows.append(row)
        if row.get('want') is not None and not row.get('error'):
            settle(page)
    time.sleep(1.2)
    back = readback(page)
    for x in read_extra(page):
        back[x['id']] = x.get('value') or ''
    for row in rows:
        if row['type'] == 'date': back[row['key']] = date_value(page, row)
    for row in rows:                                              # one more pass: a dependent list re-rendered (new id) or cleared by a later answer (Race after Ethnicity)
        if row['type'] in ('combo', 'select') and row.get('want') and not N(back.get(row['key']) or back.get('label:' + row['label'], '')) and row.get('rule') != 'prefilled' and not row.get('nofill'):   # nofill: no single list option fits (Acuity school lists) — never type the name in
            now_f = plan(page.evaluate(READ))
            fresh = rebind(row, now_f, {r['key'] for r in rows if r is not row})
            try:
                if fresh: row['key'], row['list'] = fresh['key'], fresh['list']
                if row.get('query'): CE.combo_pick(page, row, row['want'], N, css, query=row['query'])   # a searched list (School): clear, type, pick
                else: (combo_set(page, row, row['want']) if row['type'] == 'combo' else page.select_option(css(row['key']), label=row['want']))
                row.pop('error', None)
                log(f"refill {row['label'][:40]}: now {page.locator(css(row['key'])).first.input_value()!r}")
            except Exception as e:
                row['error'] = f'{type(e).__name__}: {str(e)[:120]}'
    time.sleep(0.8)
    back = readback(page)
    for x in read_extra(page):
        back[x['id']] = x.get('value') or ''
    for row in rows:
        if row['type'] == 'date': back[row['key']] = date_value(page, row)
    SB.bg_readback(page, rows, N)
    account_check(page, rows)                                     # the account boxes of a register-and-apply page, read again at the end (Danfoss 11-05)
    for row in rows:
        if row['type'] == 'account':
            if not row['ok']:
                res['problems'].append(f"{row['label']}: want {str(row['want'] or 'off')[:40]!r}, page {str(row['page'])[:40]!r}")
            continue
        if row.get('bg'):
            if not row.get('ok'):
                w = row.get('want')
                res['problems'].append(f"{row['label'][:80]}: " + (f"want {str(w)[:40]!r}, page {str(row.get('page'))[:40]!r}" if w is not None else 'no fact on file — Joey') + (f" ({row['error']})" if row.get('error') else ''))
            continue
        if row['type'] == 'file':
            continue
        got = back.get(row['key']) or back.get('label:' + row['label'], '')
        row['page'] = got
        w = row.get('want')
        row['ok'] = (w is None and not row['required']) or (w is not None and bool(N(got)) and (N(got).lower() == N(w).lower() or (row['type'] == 'checkbox' and got == 'checked')
                    or (re.search('phone', row['label'], re.I) and re.sub(r'\D', '', got)[-10:] == re.sub(r'\D', '', str(w))[-10:])))
        if not row['ok'] and w is not None:
            res['problems'].append(f"{row['label'][:80]}: want {str(w)[:40]!r}, page {str(got)[:40]!r}" + (f" ({row['error']})" if row.get('error') else ''))
    said = ' '.join(res['problems'] + res['unknown'])
    for lab in W.required_empty(rows):
        if lab[:60] not in said:
            res['problems'].append(f'required field empty on the page: {lab[:100]}')
    res['fields'] = rows
    try: page.screenshot(path=os.path.join(out, 'page.png'), full_page=True)
    except Exception: pass
    seen = {r['key'] for r in rows}
    for x in page.evaluate(UNSEEN_REQUIRED):                      # any required control left empty that the runner never read (SPX radios once read back as 27/27)
        if x['id'] not in seen and x.get('key') not in seen:
            res['problems'].append(f"required field the runner did not read, empty on the page: {x['label'][:90] or x['id']}")
    if captcha_on(page):                                          # a reCAPTCHA above Apply (SPX): Joey ticks it and presses Apply in this tab
        res['problems'].append('reCAPTCHA before Apply — Joey (the form is filled; tick it and press Apply in this tab)'); res['status'] = 'captcha'
        return res
    res['status'] = 'dry-run' if not res['problems'] and not res['unknown'] else 'needs-user'
    log(f'all fields filled and read back — {sum(1 for r in rows if r.get("ok"))}/{len(rows)} read back')
    return res


COOKIE_RX = re.compile(r'\bcookies?\b', re.I)
OTHER_TEXT = re.compile(r'^if other( source)?\b.{0,40}(specify|explain|list|enter)|^other\b.{0,30}(free text|specify|please)|^please specify\b', re.I)
IF_FOLLOW = re.compile(r'^if (other|yes|no|employee referral|you (selected|answered))\b', re.I)   # follow-ups that sit between a list and its Other box
DONE = re.compile(r'thank you for (applying|your application)|application (has been |was )?(successfully )?(submitted|received|sent)|you have (successfully )?applied', re.I)   # "Your application has been sent. Thank you!" (an employer 11-04)


def done_text(after, before=''):
    """Pure (tested). True when the page text after Apply has a success phrase (DONE) that was NOT already on the page
    before Apply — an employer's form itself opens with "Thank you for your interest in this position." (11-04: read as a
    confirmation while the page said "Please correct the errors below")."""
    seen = {m.group(0).lower() for m in DONE.finditer(before or '')}
    return any(m.group(0).lower() not in seen for m in DONE.finditer(after or ''))


REFUSED = re.compile(r'please (complete all required fields|correct the errors)|fields require a valid input', re.I)
BACK_ONLY = lambda t: 'Back to Job Listings' in t and not re.search(r'Upload a Resume|Expand all sections|Email Address', t)   # an employer's success page


def sf_done(before, after):
    """Pure (tested). (confirmed, why) after Apply (JSA-299): confirm_page.judge with the SF sentences — the page must
    have changed (the Apply button gone or the URL changed) and show a success URL or a success sentence that is new
    ("thank you for your interest" never counts) — or an employer's bare "Back to Job Listings" page. A refusal first.
    `before` / `after` = {'url', 'text', 'form'}."""
    import confirm_page as CP
    if REFUSED.search(after.get('text') or ''):
        return False, 'refused by the page'
    return CP.judge(before, after, done_re=DONE, extra=lambda s: s.get('form') is False and BACK_ONLY(s.get('text') or ''))


def sf_snap(page, text=None):
    try:
        form = apply_button(page).count() > 0
    except Exception:
        form = None
    return {'url': page.url, 'text': page_text(page) if text is None else text, 'form': form}

INVALID_FIELDS = r"""() => [...document.querySelectorAll('input, textarea')].filter(e => e.offsetParent !== null && !['hidden','button','submit','file','radio','checkbox'].includes(e.type)).map(e => {
  let a = e, msg = '';
  for (let i = 0; i < 4 && a && !msg; i++) { a = a.parentElement; if (!a) break;
    const m = [...a.querySelectorAll('*')].find(x => x.children.length === 0 && x.offsetParent !== null && /^(invalid (number|value|entry|format)|please enter a (valid )?number|only (numbers|digits))/i.test((x.textContent || '').trim()));
    if (m) msg = m.textContent.trim(); }
  const lab = ((e.labels && e.labels[0] && e.labels[0].innerText) || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
  return msg ? {id: e.id, label: lab, value: e.value, msg} : null;
}).filter(Boolean)"""


def fix_numeric(page, log):
    """After a refused Apply: a salary box flagged "Invalid number" gets the number from Joey's rule (2026-11-01: 52000 a
    year / 25 an hour / current 0 — run_wd.salary_number). Returns the fixed rows; [] when nothing could be fixed."""
    from run_wd import salary_number
    out = []
    for f in page.evaluate(INVALID_FIELDS):
        num = salary_number(f['label'])
        if not num or not re.search(r'number|digit', f['msg'], re.I):
            continue
        loc = page.locator(css(f['id'])).first
        loc.fill(num); loc.press('Tab'); time.sleep(0.6)
        log(f"{f['label'][:50]}: {f['msg']} for {f['value'][:30]!r} → {num} (Joey 2026-11-01 digits-only salary)")
        out.append({'label': f['label'], 'want': num, 'page': loc.input_value()})
    return out


APPLY_SEL = '[id$="_submitBtn"][role=button]:visible, #fbqa_apply:visible'   # a <span role=button> "Apply" (an employer) / button#fbqa_apply (register-and-apply pages, SPX, Danfoss)


def apply_button(page):
    b = page.locator(APPLY_SEL)
    if not b.count():
        b = page.locator('button:visible, input[type=submit]:visible, [role=button]:visible').filter(has_text=re.compile(r'^\s*Apply\s*$'))
    return b


def submit(page, company, log, retry=True):
    """Press Apply and confirm. Returns (status, confirmed_by, queue note or None) — press_result decides the wording, so a
    click that never landed is never reported as "pressed the final button" (Danfoss 11-05, type AF)."""
    from datetime import timedelta
    import gmail_code
    import confirm_page as CP
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    before = page_text(page)
    snap0 = sf_snap(page, before)
    b = apply_button(page)
    if not b.count():
        if DONE.search(before) and not on_application(page):
            return 'submitted', 'page', None
        log('no Apply button'); return 'blocked', None, 'no Apply button on the page — nothing was submitted'
    clicked, why = press_apply(page, b.first, log)
    if not clicked:                                               # the button may have gone away (Joey pressed Apply himself): look for the success page
        log(f'{why or "Apply not clicked"} — checking whether the page already moved on')
        for _ in range(5):
            time.sleep(2)
            ok, why = sf_done(snap0, sf_snap(page))
            if ok:
                log(f'confirmation page: {why}'); CP.settle(page); return 'submitted', 'page', None
        if apply_button(page).count():                            # the form is still there, unpressed: nothing was sent — no e-mail wait
            st, note = press_result(False, None, False)
            log(note); return st, None, note
    for _ in range(15):
        time.sleep(2)
        t = page_text(page)
        if REFUSED.search(t) or (re.search(r'required field|is required', t, re.I) and 'Expand all sections' in t):   # a refusal first: the form's own intro may thank the candidate (an employer)
            fixed = fix_numeric(page, log) if retry else []
            if fixed and all(N(x['page']) == x['want'] for x in fixed):
                log('Apply again after the number fix'); return submit(page, company, log, retry=False)
            log('Apply refused by the page: ' + t[:200]); return 'refused', None, None
        ok, why = sf_done(snap0, sf_snap(page, t))                # JSA-299: a changed page that says so (an employer: "Back to Job Listings")
        if ok:
            log(f'confirmation page: {why}'); CP.settle(page); return 'submitted', 'page', None
    log('no thank-you page — receipt pending: receipt_confirm checks Gmail later (JSA-391; no waiting in place)')
    st, note = press_result(clicked, None, True)
    return st, None, note


def write_form_check(r, out, url, a):
    """form_check.json (the results line is written by runner_common.Run.finish, JSA-187)."""
    n, ok = len(r['fields']), sum(1 for f in r['fields'] if f.get('ok'))
    json.dump({'at': now(), 'posting': url, 'job': a.job, **r, 'readback': f'{ok}/{n}'}, open(os.path.join(out, 'form_check.json'), 'w'), indent=1, ensure_ascii=False)
    return n, ok


def store_row(job_id, path=None):
    """The jobs store row with this id (read only), or None."""
    path = path or jpaths.data('store', 'jobs.jsonl')
    if not job_id or not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if f'"{job_id}"' in line:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get('id') == job_id:
                    return r
    return None


def captcha_wait(submit, given):
    """Minutes to wait for Joey's reCAPTCHA tick: the number given on the command line (a dry run too: Erie's sign-in CAPTCHA,
    Joey 2026-11-05 「勾好了」 came after the dry run had already stopped); else 15 with --submit and 0 in a dry run (an
    unattended dry run never waits). Negative → 0."""
    m = given if given is not None else (15 if submit else 0)
    return max(0.0, float(m))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url'); ap.add_argument('--job'); ap.add_argument('--resume'); ap.add_argument('--out')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222'); ap.add_argument('--folder'); ap.add_argument('--submit', action='store_true')
    ap.add_argument('--new-account', action='store_true', help='no account at this company yet (Joey): open Create Account directly')
    ap.add_argument('--wait-captcha', type=float, default=None, help='minutes to wait for Joey to tick a reCAPTCHA (sign-in / register / above Apply); default 15 with --submit, 0 in a dry run')
    a = ap.parse_args()
    a.wait_captcha = captcha_wait(a.submit, a.wait_captcha)
    import run_form as RF
    folder = jpaths.folder(a.folder) if a.folder else None   # as typed, else under the data home (ADR-0008)
    jd, cover_pdf = '', None
    if folder:
        fj = json.load(open(os.path.join(folder, 'job.json')))
        a.job = a.job or fj.get('id'); a.url = a.url or fj.get('url')
        pdfs = sorted(x for x in os.listdir(folder) if x.lower().endswith('.pdf'))
        a.resume = a.resume or next((os.path.join(folder, x) for x in pdfs if 'resume' in x.lower()), None)
        cover_pdf = next((os.path.join(folder, x) for x in pdfs if 'cover' in x.lower()), None)
        a.out = folder
        if os.path.exists(os.path.join(folder, 'jd.md')): jd = open(os.path.join(folder, 'jd.md'), encoding='utf-8').read()
        if RF.already_submitted(folder):
            print('STATUS already-submitted'); return
    if a.submit and not folder:
        sys.exit('--submit needs --folder')
    global JOB
    JOB = store_row(a.job) or {}
    url = re.sub(r'\?.*$', '', a.url or '')
    if not parse_job(url):
        sys.exit(f'not a SuccessFactors career-site job URL: {a.url}')
    resume = a.resume or jpaths.resume('2026-10', jsa_profile.resume_file('Data_Analyst_A-Classic.pdf'))
    p = parse_job(url)
    out = os.path.abspath(a.out or os.path.join(DATA, 'dryrun', 'successfactors', f"{p['host'].split('.')[1] if p['host'].count('.') > 1 else p['host']}_{p['id']}"))
    os.makedirs(out, exist_ok=True)
    logf = open(os.path.join(out, 'run_log.md'), 'a')
    def log(m): logf.write(f'- {now()} {m}\n'); logf.flush(); print(m)
    from playwright.sync_api import sync_playwright
    t0 = time.time()
    log(f'start successfactors {"submit" if a.submit else "dry-run"} {url} (resume {os.path.basename(resume)})')
    import runner_common as RC                                   # JSA-187: opening checks · submit gate · closing books
    R = RC.Run('successfactors', url, folder, out, submit=a.submit, log=log, label='SuccessFactors', data_dir=DATA)
    if not R.opening(resume):                                    # submit + materials problem: stopped before filling
        return
    with sync_playwright() as pw:
        ctx = cdp_connect.connect(pw, a.cdp).contexts[0]
        stale = [q for q in ctx.pages if parse_job(re.sub(r'\?.*$', '', q.url or '')) == p]
        for q in stale:                                           # one tab per posting: only older tabs of THIS job page — never another company's tab (a tab waiting for Joey's CAPTCHA was closed once, SPX 11-04)
            try: q.close()
            except Exception: pass
        page = ctx.new_page(); page.set_viewport_size({'width': 1300, 'height': 900})
        page.set_default_timeout(10000)                          # a blocked click fails in 10 s, never hangs the run
        R.mark('page')
        try:
            fjc = json.load(open(os.path.join(folder, 'job.json'))) if folder else {}
            r = run(page, url, resume, cover_pdf, log, out, folder, jd, fjc.get('company') or p['host'], a.job or '', a.wait_captcha, a.new_account)
        except Exception as e:
            r = {'status': 'blocked', 'problems': [f'runner error {type(e).__name__}: {str(e)[:200]}'], 'fields': [], 'unknown': []}
        checked = R.check(r)                                     # before Joey is asked to tick: a mismatch never reaches him
        only_captcha = (r.get('status') == 'captcha' and not r['unknown'] and not checked and not R.pre
                        and all(x.startswith('reCAPTCHA before Apply') for x in r['problems']))
        if a.submit and only_captcha and R.approved():          # everything else passed: Joey ticks, the runner presses Apply within seconds (a tick expires in ~2 min)
            R.mark('wait_joey')
            RF.push('求职 runner：人机验证', f"{os.path.basename(out)[11:60]} — 表单已填好，勾一下「I'm not a robot」就会自动提交")
            log(f'waiting up to {a.wait_captcha:g} min for the reCAPTCHA tick')
            if wait_token(page, a.wait_captcha * 60):
                log('reCAPTCHA ticked by Joey — pressing Apply now'); r['problems'] = []; r['status'] = 'dry-run'
            else:
                log('no reCAPTCHA tick in time')
        was_captcha = r.get('status') == 'captcha'
        decision = R.gate(r, checked)
        if decision != 'press' and was_captcha:
            RF.push('求职 runner：人机验证', f"{os.path.basename(out)[11:60]} — SuccessFactors 登录页有人机验证，交给你")
        if decision == 'press':
            R.mark('submit')
            company = json.load(open(os.path.join(folder, 'job.json'))).get('company') or p['host']
            note = None
            t_sub = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')   # the click time: receipt_confirm looks for mail since then (JSA-391)
            try:
                out_ = submit(page, company, log)
                r['status'], r['confirmed_by'] = out_[:2]; note = out_[2] if len(out_) > 2 else None   # (status, confirmed_by[, queue note])
            except Exception as e:
                log(f'submit step error {type(e).__name__}: {str(e)[:160]}'); r['status'], r['confirmed_by'] = 'unconfirmed', None
            if r['status'] == 'submitted':
                log(f"CONFIRMED by {r['confirmed_by']}")
            elif r['status'] == 'refused':
                r['status'] = 'blocked'; R.stopped_at = RC.PAGE
                R._q('SuccessFactors refused Apply — rerun after the fix')
            elif r['status'] == 'blocked':                       # Apply never pressed (covered / missing): nothing was sent
                R.stopped_at = RC.PAGE; r['problems'].append(note or 'Apply not pressed')
                R._q('not submitted: ' + (note or 'Apply not pressed'))
            elif note and note != PRESSED_NOTE:                  # unconfirmed after a failed click: never "pressed the final button" (type AF)
                R._q(note)
            elif r['status'] == 'unconfirmed' and note == PRESSED_NOTE:   # pressed, the page showed nothing: the receipt e-mail is checked later (JSA-391)
                r['receipt_pending'] = True
        write_form_check(r, out, url, a)
        R.finish(r, ctx=ctx, page=page, extra=({'receipt': 'pending', 'submit_at': t_sub} if r.get('receipt_pending') else None))

if __name__ == '__main__':
    main()
