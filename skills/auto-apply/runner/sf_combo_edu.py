#!/usr/bin/env python3
"""SuccessFactors education rows made of combo lists — School / Degree / Major / Status (JSA-092, Erie 2026-11-04).

Erie's "Education Details" section holds rows the resume parser created; School, Degree, Major and Status are combo
lists (School is a long, server-searched list without "University of Chicago"). The general rules answered every row
with the same school, the refill pass then typed into the first School box three times ("University oUniv…"). Here each
row is matched to an education entry of config/profile.json, set from that entry, extra rows are removed, missing
entries get a row; a school missing from the list → "Other" + the school's name in the row's companion text box.

Pure parts (tested by scripts/test_sf_combo_edu.py, DeepSeek-written cases):
    group_rows(fields)              → education rows from the page's fields in document order
    row_plan(rows, edus)            → which entry each row holds, rows to delete, entries to add, unmatched rows
    pick_school / pick_degree / pick_major / pick_status / companion
Page part: fill_combo_education(page, log, combo_options, N, skip) used by run_successfactors.run().
"""
import re, time
from datetime import datetime

SCHOOL_RX = re.compile(r'^(name of )?(school|college|university|institution)( name)?$|^(school|college|university)\s*/\s*(school|college|university|institution)$', re.I)
DEGREE_RX = re.compile(r'^(degree|degree (type|level|earned|obtained)|type of degree|level of (degree|education))$', re.I)
MAJOR_RX = re.compile(r'^(major|field of study|area of study|discipline|course of study|subject|major/field of study|major \(field of study\))$', re.I)
STATUS_RX = re.compile(r'^(status|degree status|education status|completion status|enrollment status)$', re.I)
GPA_RX = re.compile(r'\bgpa\b|grade point', re.I)
OTHER_RX = re.compile(r'\bother\b|not listed|specify|school name|institution name|name of (school|institution)', re.I)
COMMENTS_RX = re.compile(r'^(comments?|notes?|additional (comments?|information|info))$', re.I)
ROW_RX = re.compile(r'\b(degree|major|minor|field of study|area of study|discipline|subject|status|comments?|notes?|gpa|grade point|other|specify|'
                    r'not listed|school name|institution name|graduat\w*|start|end|from|year|month|city|state|country|location|honou?rs?|concentration)\b', re.I)
PLACEHOLDER = re.compile(r'^(no selection|select( one)?|please select|-+|there were no results|no results( found)?|no matches( found)?|loading\.*|searching\.*)$', re.I)


def _lab(t):
    return re.sub(r'\s+', ' ', str(t or '')).strip().lstrip('*').strip().rstrip(':').strip()


def _real(opts):
    return [o for o in opts or [] if str(o or '').strip() and not PLACEHOLDER.match(str(o).strip())]


def norm_school(t):
    """'The University of Illinois at Urbana-Champaign (IL)' → 'universityofillinoisurbanachampaign': lower case, a
    trailing (…) dropped, '&' = 'and', the words 'the' and 'at' dropped, every non-letter removed."""
    t = re.sub(r'\s*\([^)]*\)\s*$', '', str(t or '')).lower().replace('&', ' and ')
    t = re.sub(r'\b(the|at)\b', ' ', t)
    return re.sub(r'[^a-z]', '', t)


def kind(label):
    """Pure. The education-row box a label names: school / degree / major / status / gpa / other_school / comments / None."""
    lab = _lab(label)
    if SCHOOL_RX.match(lab):
        return 'school'
    if DEGREE_RX.match(lab):
        return 'degree'
    if MAJOR_RX.match(lab):
        return 'major'
    if STATUS_RX.match(lab):
        return 'status'
    if GPA_RX.search(lab):
        return 'gpa'
    if COMMENTS_RX.match(lab):
        return 'comments'
    if OTHER_RX.search(lab):
        return 'other_school'
    return None


def group_rows(fields):
    """Pure (tested). Fields in document order [{key, label, type, value}] → education rows [{school: <field>, fields:
    [<field> …]}]. A row starts at a box labelled School (or College / University / Institution, "Name of School") and
    takes the following boxes while their labels are short (≤ 40 characters) education-row words (Degree, Major, Status,
    Comments, GPA, "If other, please specify", dates …); it ends at the next School box or at the first other label. A row counts only when it has
    a Degree or Major box (a lone "School" question is not a row)."""
    rows, cur = [], None
    for f in fields or []:
        lab = _lab(f.get('label'))
        if kind(lab) == 'school':
            if cur:
                rows.append(cur)
            cur = {'school': f, 'fields': [f]}
            continue
        if cur is not None and (kind(lab) or ROW_RX.search(lab)) and len(lab) <= 40:   # row boxes have short labels; a long question after the rows ends them
            cur['fields'].append(f)
            continue
        if cur:
            rows.append(cur)
        cur = None
    if cur:
        rows.append(cur)
    return [r for r in rows if any(kind(f.get('label')) in ('degree', 'major') for f in r['fields'])]


def _names(e):
    return [n for n in (e.get('school'), e.get('short'), *(e.get('aliases') or [])) if n]


def match_entry(text, edus):
    """The education entry a school text belongs to: the same name (norm_school) as its school / short name, else its
    match_re found in the text with every non-letter removed; None."""
    n = norm_school(text)
    if not n:
        return None
    for e in edus or []:
        if n in {norm_school(x) for x in _names(e)}:
            return e
    compact = re.sub(r'[^a-z]', '', str(text or '').lower())
    for e in edus or []:
        if e.get('match_re') and re.search(e['match_re'], compact):
            return e
    return None


def row_plan(rows, edus):
    """Pure (tested). rows [{school: <School box value>, other: <companion text value>}] in page order, edus = the
    education entries in profile order → {'rows': {idx: school name}, 'delete': [idx …], 'add': [school …],
    'unmatched': [idx …]}. A row's school is its School value, or its companion text when the School value is "Other";
    placeholders ("No Selection") count as empty, and so does "Other" with an empty companion. The first row of an entry holds it; a later row of the same
    entry is deleted; a row with a school that matches no entry is unmatched (a person decides); an empty row takes the
    next entry (profile order) that has no row yet, and an empty row left over is deleted; entries with no row are added."""
    out = {'rows': {}, 'delete': [], 'add': [], 'unmatched': []}
    used, empties = [], []
    for i, r in enumerate(rows or []):
        s = str(r.get('school') or '').strip()
        if PLACEHOLDER.match(s):
            s = ''
        o = str(r.get('other') or '').strip()
        text = (o if o else '') if re.match(r'^other\b', s, re.I) else s
        if not text:
            empties.append(i); continue
        e = match_entry(text, edus)
        if e is None:
            out['unmatched'].append(i); continue
        if e['school'] in used:
            out['delete'].append(i); continue
        used.append(e['school']); out['rows'][i] = e['school']
    left = [e for e in edus or [] if e['school'] not in used]
    for i in empties:
        if left:
            e = left.pop(0); used.append(e['school']); out['rows'][i] = e['school']
        else:
            out['delete'].append(i)
    out['delete'].sort()
    out['add'] = [e['school'] for e in left]
    return out


SCHOOL_STOP = {'university', 'univ', 'u', 'of', 'the', 'at', 'in', 'and', 'campus', 'main'}
CAMPUS = {'churb': ('urbana', 'champaign'), 'urb': ('urbana', 'champaign'), 'urbana': ('urbana', 'champaign'), 'champaign': ('urbana', 'champaign'),
          'chgo': ('chicago',), 'spfld': ('springfield',)}       # campus hints of short school lists ("Illinois, U of/ChUrb", "… /Chgo" — an employer 11-05)


def school_words(t):
    """Pure (tested). A school name → its distinctive words in order, lower case: a trailing (…) dropped, '&' = 'and',
    split on every non-letter ("Illinois, U of/ChUrb" → illinois u of churb), the words University / Univ / U / of / the /
    at / in / and / campus / main dropped, campus hints spelled out (ChUrb / Urb / Urbana / Champaign = urbana champaign,
    Chgo = chicago, Spfld = springfield), repeats dropped. "Chicago, U of" → [chicago]; "University of Illinois
    Urbana-Champaign" → [illinois, urbana, champaign]."""
    t = re.sub(r'\s*\([^)]*\)\s*$', '', str(t or '')).lower().replace('&', ' and ')
    out = []
    for w in re.split(r'[^a-z]+', t):
        if not w or w in SCHOOL_STOP:
            continue
        for x in CAMPUS.get(w, (w,)):
            if x not in out:
                out.append(x)
    return out


def school_fits(option, edu):
    """Pure (tested). Does a list option name the entry's school, compared by distinctive words (school_words, as a set)
    with the school / short name / aliases? "Chicago, U of" = University of Chicago; "Illinois, U of/ChUrb" = University of
    Illinois Urbana-Champaign; "Illinois, U of/Chgo" (= Illinois Chicago) is neither; "Loyola U Chicago", "Chicago State U"
    are not University of Chicago (extra words)."""
    w = set(school_words(option))
    return bool(w) and any(w == set(school_words(n)) for n in _names(edu) if school_words(n))


def school_near(option, edu):
    """Pure (tested). An option that may be the school without its campus: its distinctive words are a PROPER subset of
    the school's name's words and include the name's first distinctive word ("Illinois, U of" for University of Illinois
    Urbana-Champaign). Not a pick — it only stops "Other" (a person decides)."""
    w = set(school_words(option))
    for n in _names(edu):
        s = school_words(n)
        if w and s and w < set(s) and s[0] in w:
            return True
    return False


def school_query(edu):
    """Pure (tested). The distinctive word to search a short, inverted school list by: the first word of the school's
    name that school_words keeps, in the name's own spelling ("University of Chicago" → "Chicago", "University of Illinois
    Urbana-Champaign" → "Illinois", "Northwestern University" → "Northwestern"); '' when none."""
    name = str((edu or {}).get('school') or '')
    for w in re.split(r'[^A-Za-z]+', re.sub(r'\s*\([^)]*\)\s*$', '', name)):
        if w and w.lower() not in SCHOOL_STOP:
            return w
    return ''


def pick_school(options, edu):
    """Pure (tested). (option, 'match') when an option is the entry's school (same norm_school as its school / short
    name — "University of Chicago (IL)", "The University of Chicago"); else (option, 'match') when exactly ONE option fits
    by distinctive words (school_fits — "Chicago, U of", "Illinois, U of/ChUrb"); (None, 'ambiguous') when several
    different options fit (a person decides; never "Other" then); else (option, 'other') for an "Other" option (exactly
    "Other" first, then one starting with "Other", then "not listed"); else (None, None). Placeholders such as "There
    were no results" are ignored; a different school that only contains the name ("Loyola University Chicago") is never a
    match."""
    opts = _real(options)
    names = {norm_school(n) for n in _names(edu)}
    hit = next((o for o in opts if norm_school(o) in names), None)
    if hit:
        return hit, 'match'
    fits = list(dict.fromkeys(o for o in opts if school_fits(o, edu)))
    if len(fits) == 1:
        return fits[0], 'match'
    if fits or any(school_near(o, edu) for o in opts):
        return None, 'ambiguous'
    oth = (next((o for o in opts if re.fullmatch(r'\s*other\s*', o, re.I)), None) or next((o for o in opts if re.match(r'\s*other\b', o, re.I)), None)
           or next((o for o in opts if re.search(r'not listed|not found|not in (the )?list', o, re.I)), None))
    return (oth, 'other') if oth else (None, None)


def pick_degree(options, edu):
    """Pure (tested). The option for the entry's degree: one equal to its full degree name ("Master of Science",
    "Bachelor of Arts") first; else level master → an option starting with "Master" (Masters, Master's Degree), then one
    containing "Master", then "Graduate"; level bachelor → starting with "Bachelor", then containing "Bachelor"; else None."""
    opts = _real(options)
    full = str(edu.get('degree_full') or '').strip().lower()
    hit = next((o for o in opts if full and o.strip().lower() == full), None)
    if hit:
        return hit
    lvl = str(edu.get('level') or '').lower()
    rxs = {'master': [r'^master', r'\bmaster', r'^graduate\b'], 'bachelor': [r'^bachelor', r'\bbachelor']}.get(lvl, [])
    for rx in rxs:
        hit = next((o for o in opts if re.search(rx, o.strip(), re.I)), None)
        if hit:
            return hit
    return None


FALLBACK_MAJORS = [r'^computer science$', r'^(computer |management )?information systems?$', r'^other$']   # Joey 2026-10-28: no matching major → CS, then IS


def pick_major(options, major):
    """Pure (tested). The option for the entry's major: equal to it (case-insensitive); else an option of 2+ words whose
    words all appear in the major ("Data Science" for "Applied Data Science"), or one that contains the whole major;
    else Computer Science, then Information Systems (also Computer / Management Information Systems), then Other
    (Joey 2026-10-28: no matching major → CS or IS); else None."""
    opts = _real(options)
    m = re.sub(r'\s+', ' ', str(major or '')).strip().lower()
    if not m:
        return None
    hit = next((o for o in opts if o.strip().lower() == m), None)
    if hit:
        return hit
    mw = set(re.findall(r'[a-z]+', m))
    for o in opts:
        ow = re.findall(r'[a-z]+', o.lower())
        if (len(ow) >= 2 and set(ow) <= mw) or re.search(r'\b' + re.escape(m) + r'\b', o.lower()):
            return o
    for rx in FALLBACK_MAJORS:
        hit = next((o for o in opts if re.search(rx, o.strip(), re.I)), None)
        if hit:
            return hit
    return None


def pick_status(options, edu, today=None):
    """Pure (tested). The status option: a current entry → one starting with Attending / Currently Attending / Enrolled /
    In Progress / Pursuing / Current (never "No Longer Attending" / "Not …"); an entry that ended by `today` (YYYY-MM)
    → one starting with Graduated / Completed / Degree Awarded / Degree Received; else None."""
    opts = _real(options)
    today = today or datetime.now().strftime('%Y-%m')
    if edu.get('current'):
        rx = r'^(currently )?(attending|enrolled|in progress|pursuing|current)\b'
    elif edu.get('end') and str(edu['end']) <= today:
        rx = r'^(graduated|completed|degree (awarded|received|completed))\b'
    else:
        return None
    return next((o for o in opts if re.search(rx, o.strip(), re.I) and not re.search(r'\b(no longer|not)\b', o, re.I)), None)


def companion(row_fields):
    """Pure (tested). The text box that takes the school's name when School = "Other": a box in the row whose label says
    other / not listed / specify / school name (not a combo, not GPA); else the row's Comments box; else None. Returns
    its key."""
    texts = [f for f in row_fields or [] if f.get('type') in ('text', 'textarea')]
    hit = next((f for f in texts if kind(f.get('label')) == 'other_school'), None) or next((f for f in texts if kind(f.get('label')) == 'comments'), None)
    return hit['key'] if hit else None


# ---- page side -----------------------------------------------------------------------------------------------------
START_DATE_RX = re.compile(r'^(from|start|begin)( date)?$', re.I)
END_DATE_RX = re.compile(r'^(to|end)( date)?$', re.I)


def fmt_date(y, m, d, fmt=None):
    """Pure (tested). A date in the box's own pattern: tokens yyyy, MM, dd, M, d; empty / missing = 'MM/dd/yyyy'."""
    out = fmt or 'MM/dd/yyyy'
    return re.sub(r'yyyy|MM|dd|M|d', lambda t: {'yyyy': f'{y:04d}', 'MM': f'{m:02d}', 'dd': f'{d:02d}', 'M': str(m), 'd': str(d)}[t.group(0)], out)


def edu_date_want(label, edu, required, fmt=None):
    """Pure (tested). The text for one date box of an education row (Newell 11-05: two required "From Date" UI5 boxes per
    row, type AE): a start box ("From Date" / "Start Date" / "From" / "Begin Date") → the first day of the entry's start
    month; an end box ("To Date" / "End Date" / "To") only when required → the last day of the end month; None otherwise
    (no start on file → None: the caller asks Joey, never guesses)."""
    import calendar
    lab = _lab(label)
    e = edu or {}
    if START_DATE_RX.match(lab):
        ym, last = e.get('start'), False
    elif END_DATE_RX.match(lab) and required:
        ym, last = e.get('end'), True
    else:
        return None
    m = re.fullmatch(r'(\d{4})-(\d{1,2})', str(ym or '').strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return fmt_date(y, mo, calendar.monthrange(y, mo)[1] if last else 1, fmt)


ROW_DATES = r"""([rows, known]) => {
  const vis = e => e && e.offsetParent !== null && e.getBoundingClientRect().width > 0;
  const inputs = [...document.querySelectorAll('input, select, textarea')].filter(e => vis(e) && !['hidden', 'button', 'submit'].includes(e.type));
  const mine = rows.map(ids => new Set(ids)), seen = new Set(known);
  const foreign = (el, allowed) => inputs.some(i => seen.has(i.id) && !allowed.has(i.id) && el.contains(i));
  const climb = (start, allowed) => { let a = start; while (a.parentElement && a.parentElement !== document.body && !foreign(a.parentElement, allowed)) a = a.parentElement; return a; };
  const lca = els => { let a = els[0]; while (a && !els.every(e => a.contains(e))) a = a.parentElement; return a; };
  const all = [...document.querySelectorAll('ui5-date-picker-xweb-calendar-widget')];
  const names = all.map((d, j) => d.getAttribute('accessible-name') || String(j));
  const nth = names.map((nm, j) => names.slice(0, j).filter(x => x === nm).length);   // the same index READ_EXTRA keys by ("ui5date:From Date#1")
  return rows.map((ids, i) => {
    const els = ids.map(id => document.getElementById(id)).filter(Boolean);
    if (!els.length) return [];
    const box = climb(lca(els), mine[i]), sec = els[0].closest('.rcmFormSection');
    return all.map((d, j) => [d, j]).filter(([d]) => box.contains(d) && (!sec || sec.contains(d)) && d.getClientRects().length)
      .map(([d, j]) => ({name: names[j], nth: nth[j], key: 'ui5date:' + names[j] + (nth[j] ? '#' + nth[j] : ''), required: d.hasAttribute('required'),
                         fmt: d.getAttribute('format-pattern') || '', value: d.getAttribute('value') || d.value || ''}));
  });
}"""


CONTROLS = r"""([rows, known]) => {
  const strip = t => (t || '').replace(/[\ue000-\uf8ff]/g, ' ').replace(/\s+/g, ' ').trim();
  const vis = e => e && e.offsetParent !== null && e.getBoundingClientRect().width > 0;
  const inputs = [...document.querySelectorAll('input, select, textarea')].filter(e => vis(e) && !['hidden', 'button', 'submit'].includes(e.type));
  const mine = rows.map(ids => new Set(ids));
  const all = new Set(rows.flat()), seen = new Set(known);
  const foreign = (el, allowed) => inputs.some(i => seen.has(i.id) && !allowed.has(i.id) && el.contains(i));
  const climb = (start, allowed) => { let a = start; while (a.parentElement && a.parentElement !== document.body && !foreign(a.parentElement, allowed)) a = a.parentElement; return a; };   // the largest box holding this row's fields and no other labelled field
  const after = (a, b) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
  const lca = els => { let a = els[0]; while (a && !els.every(e => a.contains(e))) a = a.parentElement; return a; };
  const ctl = (root, rx, from) => { const c = [...root.querySelectorAll('a, button, [role=button], span, div')].filter(e => vis(e) && (rx.test(strip(e.textContent)) || rx.test(strip(e.getAttribute('title'))) || rx.test(strip(e.getAttribute('aria-label')))));
    const inner = c.filter(e => !c.some(x => x !== e && e.contains(x)));
    return inner.find(e => !from || after(from, e)) || (from ? null : inner[0]) || null; };   // the innermost match, after `from` in page order
  document.querySelectorAll('[data-jsa-ctl]').forEach(e => e.removeAttribute('data-jsa-ctl'));
  const out = {remove: [], add: false};
  rows.forEach((ids, i) => {
    const els = ids.map(id => document.getElementById(id)).filter(Boolean);
    if (!els.length) { out.remove.push(false); return; }
    const box = climb(lca(els), mine[i]);
    const r = ctl(box, /^(remove|delete( row)?|delete this row)$/i, els[0]) || ctl(box, /^(remove|delete( row)?|delete this row)$/i);
    if (r) r.setAttribute('data-jsa-ctl', 'remove-' + i);
    out.remove.push(!!r);
  });
  const els = rows.flat().map(id => document.getElementById(id)).filter(Boolean);
  if (els.length) {
    const sec = climb(lca(els), all);
    const a = ctl(sec, /^\+?\s*add( new row| another( row)?| more| row)?$/i, els[els.length - 1]);   // the Add after the last row (never another section's)
    if (a) { a.setAttribute('data-jsa-ctl', 'add'); out.add = true; }
  }
  return out;
}"""


EDU_SECTION_RX = re.compile(r'\beducation\b|\bdegrees?\b|\bschool(ing|s)?\b|\bacademic\b', re.I)
SB_EDU_RX = re.compile(r'^(formal )?education( history)?$', re.I)   # sf_background's own sections (it adds their rows itself)


def sections_to_open(sections):
    """Pure (tested). Visible SuccessFactors sections [{id, head, empty, add}] → the ids whose "Add" is clicked once
    before the education rows are read: the section shows "There are no items in this section" (empty), has an Add
    control, its heading is about education (education / degree / school / academic), and it is not one of
    sf_background's headings ("Education", "Formal Education", "Education History"). Erie 2026-11-05: "Highest Level of
    Education Completed" and "Education Details" were both empty, the runner saw no rows and filled nothing."""
    out = []
    for s in sections or []:
        h = re.sub(r'\s+', ' ', str(s.get('head') or '')).strip().lstrip('*').strip()
        if s.get('empty') and s.get('add') and EDU_SECTION_RX.search(h) and not SB_EDU_RX.match(h):
            out.append(s.get('id'))
    return out


EMPTY_SECTIONS = r"""() => [...document.querySelectorAll('.rcmFormSection')].filter(s => s.offsetParent !== null).map(s => {
  const top = s.querySelector('[id$=":topBar"], [id$=_topBar], h1, h2, h3, [role=heading]');
  const none = s.querySelector('.noItemsInSection'), add = s.querySelector('[id$=_addRowBtn]');
  return {id: s.id, head: (top ? top.innerText : '').replace(/\s+/g, ' ').trim(), empty: !!(none && none.offsetParent !== null),
          add: (add && add.offsetParent !== null) ? add.id : ''};
})"""


def open_empty_sections(page, log):
    """Click Add once in every empty education section (sections_to_open); the rows are then filled like parser rows."""
    try:
        secs = page.evaluate(EMPTY_SECTIONS)
    except Exception:
        return []
    ids = sections_to_open(secs)
    for sid in ids:
        s = next(x for x in secs if x['id'] == sid)
        log(f"{s['head']}: empty section — adding a row")
        page.locator(f'[id="{s["add"]}"]').first.click(); time.sleep(2)
    return ids


def _read_rows(page, plan, READ, skip):
    fields = [f for f in plan(page.evaluate(READ)) if f['key'] not in skip]
    return group_rows(fields)


def _confirm(page):
    ok = page.locator('#sfOverlayMgr button:has-text("OK"), #sfOverlayMgr button:has-text("Yes"), #sfOverlayMgr button:has-text("Remove"), #sfOverlayMgr button:has-text("Delete")')
    if ok.count() and ok.first.is_visible():
        ok.first.click(); time.sleep(1.5)


def _clear(inp, N):
    """Empty a combo's text box before typing (typing into a filled box appended: "University oUniv…", Erie 11-04)."""
    try:
        inp.fill('')
    except Exception:
        pass
    try:
        if N(inp.input_value()):
            inp.click(); inp.press('ControlOrMeta+a'); inp.press('Backspace')
    except Exception:
        pass


def combo_search(page, f, query, N, css):
    """Clear the combo, type `query`, wait until the list stops changing; returns the option texts shown."""
    inp = page.locator(css(f['key'])).first
    inp.scroll_into_view_if_needed(); inp.click(); time.sleep(0.3)
    _clear(inp, N)
    inp.press_sequentially(str(query), delay=50)
    lid = f.get('list') or ''
    sel = (css(lid) + ' li[role=option]') if lid else 'li[role=option]'
    texts, last = [], None
    for _ in range(16):
        time.sleep(0.5)
        texts = [N(t) for t in page.locator(sel).all_inner_texts()]
        if texts and texts == last:
            break
        last = texts
    return inp, sel, texts


def combo_pick(page, f, want, N, css, query=None, opener=None):
    """Pick option `want`: with `query` the box is cleared and the query typed first (server-searched lists); else the
    list is opened (`opener`). Up to 3 tries; True when the box then shows `want`."""
    for attempt in range(3):
        if query:
            inp, sel, _ = combo_search(page, f, query, N, css)
        else:
            inp, sel, _ = opener(page, f)
        opt = page.locator(sel)
        for i in range(opt.count()):
            if N(opt.nth(i).inner_text()).lower() == N(want).lower():
                opt.nth(i).scroll_into_view_if_needed(); opt.nth(i).click(); time.sleep(0.8)
                if N(page.locator(css(f['key'])).first.input_value()).lower() == N(want).lower():
                    return True
                break
        page.keyboard.press('Escape'); time.sleep(1.0 + attempt)
        query = query or N(want)
    raise ValueError(f'no option {want!r} (or it did not stick)')


def school_choice(page, f, edu, N, css, combo_options):
    """(option, query, how) for a School combo: search the school's name, then its short name, then its distinctive word
    (school_query: "Chicago", "Illinois" — short inverted lists such as "Chicago, U of", an employer 11-05); then the loaded
    list; then search "Other". how = 'match' / 'other' / 'ambiguous' (several options fit: never "Other", a person
    decides) / None."""
    ambiguous = False
    for q in list(dict.fromkeys(x for x in [edu.get('school'), edu.get('short'), school_query(edu)] if x)):
        _, _, texts = combo_search(page, f, q, N, css); page.keyboard.press('Escape'); time.sleep(0.4)
        pick, how = pick_school(texts, edu)
        if how == 'match':
            return pick, q, how
        ambiguous = ambiguous or how == 'ambiguous'
    try:
        loaded = combo_options(page, f)
    except Exception:
        loaded = []
    pick, how = pick_school(loaded, edu)
    if how == 'match':
        return pick, pick, how
    if ambiguous or how == 'ambiguous':                           # the school is in the list more than once: never "Other"
        _clear(page.locator(css(f['key'])).first, N)
        return None, None, 'ambiguous'
    _, _, texts = combo_search(page, f, 'Other', N, css); page.keyboard.press('Escape'); time.sleep(0.4)
    p2, h2 = pick_school(texts, edu)
    if h2 == 'other':
        return p2, 'Other', h2
    return (pick, pick, how) if how == 'other' else (None, None, None)


def fill_combo_education(page, log, plan, READ, combo_options, opener, css, N, skip=frozenset(), edus=None, gpa_text='', today=None, date_set=None):
    """Find the education rows (group_rows), remove extra / duplicate rows, add missing ones, then set School / Degree /
    Major / Status (and GPA, the companion box) of every row from its entry, and its UI5 date boxes (From / To Date,
    edu_date_want; `date_set(page, field, value)` types without Enter — type AE). Returns (read-back rows, keys handled)."""
    import os, sys
    if edus is None:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
        import jsa_profile
        edus = jsa_profile.get('education') or []
        gpa_text = str(jsa_profile.get('answers.gpa.text') or '')
    today = today or datetime.now().strftime('%Y-%m')
    open_empty_sections(page, log)
    rows = _read_rows(page, plan, READ, skip)
    if not rows:
        return [], set()
    for _ in range(6):                                            # one delete / add at a time, then read again (the page re-renders)
        p = row_plan([{'school': r['school'].get('value'), 'other': next((f.get('value') for f in r['fields'] if f['key'] == companion(r['fields'])), '')} for r in rows], edus)
        ctl = page.evaluate(CONTROLS, [[[f['key'] for f in r['fields']] for r in rows], [f['key'] for f in plan(page.evaluate(READ))]])
        if p['delete'] and ctl['remove'][p['delete'][0]]:
            i = p['delete'][0]
            log(f"education rows: removing row {i + 1} ({rows[i]['school'].get('value') or 'empty'})")
            page.locator(f'[data-jsa-ctl="remove-{i}"]').first.click(); time.sleep(1.5); _confirm(page)
        elif p['add'] and ctl['add']:
            log(f"education rows: adding a row for {p['add'][0]}")
            page.locator('[data-jsa-ctl="add"]').first.click(); time.sleep(2)
        else:
            break
        rows = _read_rows(page, plan, READ, skip)
    p = row_plan([{'school': r['school'].get('value'), 'other': next((f.get('value') for f in r['fields'] if f['key'] == companion(r['fields'])), '')} for r in rows], edus)
    out, keys = [], set()
    try:                                                          # the row's own UI5 date boxes (Newell 11-05: "From Date" sits before School in each row)
        dates = page.evaluate(ROW_DATES, [[[f['key'] for f in r['fields']] for r in rows], [f['key'] for f in plan(page.evaluate(READ))]]) if date_set else []
    except Exception:
        dates = []
    by_name = {e['school']: e for e in edus}
    for i, r in enumerate(rows):
        for f in r['fields']:
            keys.add(f['key'])
        if i in p['delete'] or i in p['unmatched']:
            why = 'a row matching no school on file — Joey' if i in p['unmatched'] else 'an extra row the runner could not remove'
            out.append({'key': r['school']['key'], 'label': f"Education row {i + 1}: {why}", 'type': 'text', 'required': True, 'want': None, 'page': '', 'ok': False, 'bg': True})
            continue
        e = by_name.get(p['rows'].get(i))
        if not e:
            continue
        who = e.get('short') or e['school']
        comp = companion(r['fields'])
        other = False
        for f in r['fields']:
            k = kind(f['label'])
            row = {'key': f['key'], 'label': f"Education ({who}): {_lab(f['label'])}", 'type': f['type'], 'required': bool(f.get('required')), 'list': f.get('list') or '',
                   'options': [], 'rule': 'education_combo', 'step': 'edu'}
            try:
                if k == 'school' and f['type'] == 'combo':
                    pick, query, how = school_choice(page, f, e, N, css, combo_options)
                    row['want'] = pick; row['query'] = query; row['rule'] = 'education_combo:' + str(how)
                    if not pick:
                        row['error'] = (f"{e['school']}: several list options could be it — Joey" if how == 'ambiguous'
                                        else f"no option for {e['school']} and no Other option")
                        row['nofill'] = True                       # the refill pass must not type the name in again
                    elif N(f.get('value')).lower() != N(pick).lower():
                        combo_pick(page, f, pick, N, css, query=query)
                    other = how == 'other'
                    if other: log(f"education ({who}): school not in the list → Other" + (' + name in the companion box' if comp else ' (no companion box)'))
                elif k == 'school':
                    row['want'] = e['school']
                    if N(f.get('value')) != e['school']: page.locator(css(f['key'])).first.fill(e['school'])
                elif k in ('degree', 'major', 'status') and f['type'] == 'combo':
                    opts = combo_options(page, f)
                    pick = pick_degree(opts, e) if k == 'degree' else pick_major(opts, e.get('major')) if k == 'major' else pick_status(opts, e, today)
                    row['want'] = pick
                    if pick is None and (k != 'status' or f.get('required')):
                        row['error'] = f'no option for {k} ({e.get("major") if k == "major" else e.get("level")}) in {opts[:8]}'
                    elif pick and N(f.get('value')).lower() != N(pick).lower():
                        combo_pick(page, f, pick, N, css, opener=opener)
                elif k == 'gpa' and f['type'] in ('text', 'textarea'):
                    w = gpa_text if e.get('level') == 'bachelor' else ('N/A' if f.get('required') else '')   # M.S. GPA not yet: required → N/A (Joey 2026-10-30), optional → empty
                    row['want'] = w or None
                    if N(f.get('value')) != w: page.locator(css(f['key'])).first.fill(w)
                else:
                    row['want'] = f.get('value') or None              # dates, city … : keep what is there (blocks when required and empty)
                    out.append(row); continue
            except Exception as ex:
                row['error'] = f'{type(ex).__name__}: {str(ex)[:100]}'
            row['required'] = bool(row.get('want')) or row['required']
            out.append(row)
        if other and comp:                                        # the school's name in the companion box (dedicated "If other" box, else Comments)
            f = next(x for x in r['fields'] if x['key'] == comp)
            page.locator(css(comp)).first.fill(e['school'])
            for x in out:
                if x['key'] == comp:
                    x['want'] = e['school']; x['required'] = True; x['rule'] = 'education_combo:other_name'
        elif other:
            log(f"education ({who}): Other picked, no box for the school's name")
        for d in (dates[i] if i < len(dates) else []):
            keys.add(d['key'])
            want = edu_date_want(d['name'], e, d.get('required'), d.get('fmt'))
            row = {'key': d['key'], 'name': d['name'], 'nth': d.get('nth') or 0, 'label': f"Education ({who}): {d['name']}", 'type': 'date',
                   'required': bool(d.get('required')), 'list': '', 'options': [], 'rule': 'education_combo:date', 'step': 'edu', 'want': want}
            if want and N(d.get('value')) != want:
                try:
                    date_set(page, row, want)
                except Exception as ex:
                    row['error'] = f'{type(ex).__name__}: {str(ex)[:100]}'
            elif not want and N(d.get('value')):
                row['want'] = d['value']; row['rule'] = 'education_combo:date_kept'       # no fact for this box: keep what the page holds
            elif not want and row['required']:
                row['ask'] = (f"{row['label']} — no {'start' if START_DATE_RX.match(_lab(d['name'])) else 'end'} date on file for "
                              f"{e['school']} (config/profile.json education) — Joey")
            out.append(row)
    for school in p['add']:
        out.append({'key': f'edu-add:{school}', 'label': f'Education rows: no row for {school} (no Add control)', 'type': 'text', 'required': True, 'want': None, 'page': '', 'ok': False, 'bg': True})
    log(f"education rows (combo lists): {len(p['rows'])} set" + (f", unmatched {p['unmatched']}" if p['unmatched'] else '') + (f", missing {p['add']}" if p['add'] else ''))
    return out, keys
