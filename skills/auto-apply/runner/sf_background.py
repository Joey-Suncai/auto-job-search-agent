#!/usr/bin/env python3
"""SuccessFactors background sections — "Previous Employment" and "Formal Education" rows (JSA-092, an employer 2026-11-04).

The resume parser fills these rows on its own (company "HYDE PARK", location "Chicago" for every job, one education row
"M.S. in Applied Data Science; B.A. in Economics" with a wrong From Date). Every row is matched to a fact on file and
set from it; a missing school / employer gets a new row ("Add new row"); a row that matches nothing is a problem.

Facts: work = config/wd_profile.json → work (the same entries Workday uses); education = config/profile.json → education
(school, level, major, start, end, current), with the start month from wd_profile.json when profile.json has none.
A Division / department box has no fact on file unless the work entry has "Division" — then it stays unknown (blocks).

    plan = bg_plan(section, work, edus, today)            # pure, tested (scripts/test_sf_background.py)
    rows, keys, secs = fill_background(page, log)          # page side, used by run_successfactors.run()
"""
import calendar, json, os, re, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))

WORK_RX = re.compile(r'^(previous|prior|past|work|employment)\b.*(employment|experience|history)$|^(work|employment) (experience|history)$', re.I)
EDU_RX = re.compile(r'^(formal )?education( history)?$', re.I)


def _compact(t):
    return re.sub(r'[^a-z]', '', str(t or '').lower())


def _lab(t):
    return re.sub(r'\s+', ' ', str(t or '')).replace(' ', ' ').lstrip('* ').strip()


WORK_ALIASES = [(r'^(company|company name|employer|employer name|name of (company|employer)|organi[sz]ation( name)?)$', 'Company'),
                (r'^(job title|title|position|position title|job title/position|job position)$', 'Job Title'),
                (r'^(present|current) employer\??$|^(currently employed|current job|is this your current (job|employer))( here)?\??$', 'Current'),
                (r'^(start date|from date|from|date started)$', 'Start Date'), (r'^(end date|to date|to|date ended)$', 'End Date'),
                (r'^(location|city|city/location)$', 'Location')]
EDU_ALIASES = [(r'^(school|school name|name of school|college|college/university|university|university/college|institution|institution name)$', 'School Name'),
               (r'^(type|degree|degree type|degree/certificate|degree / certificate|degree or certificate|certificate/degree)$', 'Type'),
               (r'^(subject|major|field of study|area of study|major/field of study)$', 'Subject'),
               (r'^(still attending|currently attending|attending|are you still attending)\??$', 'Attending'),
               (r'^(degree/certificate completion date|completion date|degree completion date|graduation date|date of graduation)$', 'Completion Date'),
               (r'^(from date|start date|from)$', 'From Date'), (r'^(end date|to date|to)$', 'End Date'), (r'^result$', 'Result')]


def canon_label(label, kind):
    """Pure (tested). A row box's page label → the key bg_plan's values use: work "Company Name" → Company, "Title" →
    Job Title, "Present Employer" → Current; education "College/University" → School Name, "Degree/Certificate" → Type,
    "Major" → Subject, "Still Attending?" → Attending, "Degree/Certificate Completion Date" → Completion Date, "Start
    Date" → From Date (an employer 11-05). Anything else is returned as it is (star / colon dropped)."""
    lab = _lab(label).rstrip(':').strip()
    for rx, key in (WORK_ALIASES if kind == 'work' else EDU_ALIASES if kind == 'edu' else []):
        if re.match(rx, lab, re.I):
            return key
    return lab


def month_first(ym):
    """'2025-08' / '08/2025' → '08/01/2025'; '' when it cannot be read."""
    m = re.fullmatch(r'(\d{4})-(\d{1,2})', str(ym or '').strip()) or None
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(r'(\d{1,2})/(\d{4})', str(ym or '').strip())
        if not m:
            return ''
        mo, y = int(m.group(1)), int(m.group(2))
    return f'{mo:02d}/01/{y}' if 1 <= mo <= 12 else ''


def month_last(ym):
    """'2025-10' / '10/2025' → '10/31/2025' (the month's last day); '' when it cannot be read."""
    f = month_first(ym)
    if not f:
        return ''
    mo, y = int(f[:2]), int(f[-4:])
    return f'{mo:02d}/{calendar.monthrange(y, mo)[1]:02d}/{y}'


def section_kind(head):
    """Pure. 'work' / 'edu' / None from a section heading ("Previous Employment", "Formal Education")."""
    h = _lab(head)
    if EDU_RX.match(h):
        return 'edu'
    if WORK_RX.match(h):
        return 'work'
    return None


def _work_values(e, row):
    v = {'Job Title': e.get('Job Title') or '', 'Company': e.get('Company') or '', 'Location': e.get('Location') or '',
         'Start Date': month_first(e.get('From')), 'End Date': '' if e.get('current') else month_last(e.get('To')),
         'Current': '/^yes\\b/i' if e.get('current') else '/^no\\b/i'}
    if e.get('Division'):
        v['Division'] = e['Division']
    have = {canon_label(f['label'], 'work'): f.get('value') or '' for f in row.get('fields') or []}
    if not have.get('Summary of Work Performed', '').strip() and e.get('Description'):
        v['Summary of Work Performed'] = e['Description']
    return v


def _edu_values(e, today):
    current = bool(e.get('current'))
    ended = bool(e.get('end')) and str(e['end']) <= today and not current
    v = {'Type': '/^' + ('master' if e.get('level') == 'master' else 'bachelor' if e.get('level') == 'bachelor' else re.escape(str(e.get('level') or ''))) + '/i',
         'Subject': e.get('major') or '', 'School Name': e.get('school') or '',
         'Result': '/in progress|pursuing|enrolled|current/i' if current else ('/^graduated|completed|degree (awarded|received)/i' if ended else '/in progress/i'),
         'From Date': month_first(e.get('start')), 'End Date': month_last(e.get('end')),
         'Attending': '/^yes\\b/i' if current else '/^no\\b/i'}
    if ended:
        v['Completion Date'] = month_last(e.get('end'))          # a degree still in progress has no completion date: the box keeps what it has
    return v


def _match(kind, row, entries):
    """The entry a parsed row belongs to: work by Company (then Job Title), education by School Name; None."""
    have = {canon_label(f['label'], kind).lower(): f.get('value') or '' for f in row.get('fields') or []}   # "Company Name" / "College/University" (an employer 11-05)
    if kind == 'work':
        comp, title = _compact(have.get('company')), _compact(have.get('job title'))
        for e in entries:
            rx = e.get('match') or '$^'
            if comp and (re.search(rx.replace(' ', ''), comp) or _compact(e.get('Company')).startswith(comp) or comp.startswith(_compact(e.get('Company')))):
                return e
        for e in entries:
            if title and title == _compact(e.get('Job Title')) and not comp:
                return e
        return None
    school = _compact(have.get('school name'))
    for e in entries:
        if school and re.search(e.get('match_re') or '$^', school):
            return e
    return None


def _empty(row):
    return not any(str(f.get('value') or '').strip() for f in row.get('fields') or []) and not any(str(d.get('value') or '').strip() for d in row.get('dates') or [])


def bg_plan(section, work, edus, today=None):
    """Pure (tested). One section {head, rows: [{fields: [{label, value, type}], dates: [{name, value}]}]} →
    {'kind', 'rows': [{'idx', 'who', 'set': {label: value}}], 'add': [who …], 'unmatched': [idx …], 'delete': [idx …]}.
    Each row matched to an entry gets that entry's values (combo values are '/regex/i' picks); the second row matching the
    same entry is deleted; an empty row takes the next entry with no row; a non-empty row matching nothing is unmatched;
    entries left with no row are added. Not a work / education section → None."""
    kind = section_kind(section.get('head'))
    if not kind:
        return None
    today = today or datetime.now().strftime('%Y-%m')
    entries = list(work if kind == 'work' else edus)
    name = (lambda e: e.get('Company') or '') if kind == 'work' else (lambda e: e.get('school') or '')
    out = {'kind': kind, 'rows': [], 'add': [], 'unmatched': [], 'delete': []}
    used, empties = [], []
    for i, row in enumerate(section.get('rows') or []):
        if _empty(row):
            empties.append(i); continue
        e = _match(kind, row, entries)
        if e is None:
            out['unmatched'].append(i); continue
        if name(e) in used:
            out['delete'].append(i); continue
        used.append(name(e))
        out['rows'].append({'idx': i, 'who': name(e), 'set': _work_values(e, row) if kind == 'work' else _edu_values(e, today)})
    left = [e for e in entries if name(e) not in used]
    for i in empties:
        if not left:
            break
        e = left.pop(0); used.append(name(e))
        out['rows'].append({'idx': i, 'who': name(e), 'set': _work_values(e, {}) if kind == 'work' else _edu_values(e, today)})
    out['add'] = [name(e) for e in left]
    out['rows'].sort(key=lambda r: r['idx'])
    return out


def load_facts():
    """(work entries, education entries) from config/wd_profile.json and config/profile.json."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import jsa_profile                                       # the data home's config/ (ADR-0008); env overrides as everywhere
    wd = json.load(open(jsa_profile.data_file('wd_profile.json', 'JSA_WD_PROFILE'), encoding='utf-8'))
    prof = jsa_profile.load()
    edus = []
    for e in prof.get('education') or []:
        e = dict(e)
        if not e.get('start'):
            w = next((x for x in wd.get('education') or [] if re.search(x.get('match') or '$^', _compact(e.get('school')))), None)
            if w and w.get('From_month'):
                e['start'] = w['From_month']
        edus.append(e)
    return wd.get('work') or [], edus


BG_READ = r"""() => [...document.querySelectorAll('.rcmFormSection')].filter(s => s.offsetParent !== null && s.querySelector('[id$=_bgElementContainer]')).map(s => {
  const top = s.querySelector('[id$=":topBar"], [id$=_topBar], h1, h2, h3, [role=heading]');
  const add = s.querySelector('[id$=_addRowBtn]');
  const cont = s.querySelector('[id$=_bgElementContainer]');
  const lab = e => ((e.labels && e.labels[0]) ? e.labels[0].innerText : (e.getAttribute('aria-label') || '')).replace(/\s+/g, ' ').replace(/^\*\s*/, '').trim();
  const rows = [...cont.children].filter(r => r.querySelector('input, textarea, ui5-date-picker-xweb-calendar-widget')).map(r => {
    const del = [...r.querySelectorAll('[title="Delete Row"]')].find(e => e.offsetParent !== null);
    return {fields: [...r.querySelectorAll('input, textarea')].filter(e => e.offsetParent !== null && !['hidden', 'button', 'submit', 'file'].includes(e.type)).map(e => ({key: e.id, label: lab(e),
              type: (e.getAttribute('role') === 'combobox' || /_listSelect$/.test(e.getAttribute('aria-owns') || '')) ? 'combo' : (e.tagName === 'TEXTAREA' ? 'textarea' : 'text'),
              list: e.getAttribute('aria-owns') || '', value: e.value || '', required: e.required || e.getAttribute('aria-required') === 'true' || /^\s*\*/.test((e.labels && e.labels[0] && e.labels[0].innerText) || '')})),
            dates: [...r.querySelectorAll('ui5-date-picker-xweb-calendar-widget')].map(d => ({name: d.getAttribute('accessible-name') || '', value: d.getAttribute('value') || d.value || '',
              required: d.hasAttribute('required')})),
            del: !!del};
  });
  return {id: s.id, head: (top ? top.innerText : '').replace(/\s+/g, ' ').trim(), add: add ? add.id : '', rows};
})"""


def _row(page, sid, idx):
    return page.locator(f'[id="{sid}"] [id$=_bgElementContainer] > *:has(input, textarea, ui5-date-picker-xweb-calendar-widget)').nth(idx)


def _date_box(page, sid, idx, name):
    return _row(page, sid, idx).locator(f'ui5-date-picker-xweb-calendar-widget[accessible-name="{name}"] input').first


def pick_option(opts, want):
    """Pure (tested). The option for a value: '/regex/i' → the first option it finds, else the option equal to it."""
    m = re.fullmatch(r'/(.*)/i?', want or '')
    if m:
        rx = re.compile(m.group(1), re.I)
        return next((o for o in opts if rx.search(o)), None)
    return next((o for o in opts if o.strip().lower() == want.strip().lower()), None)


def _css(i):
    return '[id="' + str(i).replace('"', '\\"') + '"]'


def edu_pick(key, opts, ent):
    """Pure (tested). An education list's option from the entry, with the same pickers as the combo education rows
    (sf_combo_edu): Type → pick_degree (the full degree name first), Subject → pick_major (Joey 2026-10-28: else CS, then
    IS). None for other keys or no entry (the caller falls back to pick_option)."""
    if not ent:
        return None
    import sf_combo_edu as CE
    if key == 'Type':
        return CE.pick_degree(opts, ent)
    if key == 'Subject':
        return CE.pick_major(opts, ent.get('major'))
    return None


def edu_school(page, f, ent, combo_options, N):
    """(option, query, how) for a School combo in a background row: the school's own entry in the list
    (sf_combo_edu.pick_school on the loaded options, else a search by name / short name / distinctive word — "Chicago, U
    of", an employer 11-05), never "Other" here (no companion box); (None, None, 'ambiguous' | None) when no single option fits
    — the box is left empty for Joey."""
    import sf_combo_edu as CE
    try:
        pick, how = CE.pick_school(combo_options(page, f), ent)
    except Exception:
        pick, how = None, None
    if how == 'match':
        return pick, pick, how
    pick, query, how2 = CE.school_choice(page, f, ent, N, _css, combo_options)
    if how2 == 'match':
        return pick, query, how2
    CE._clear(page.locator(_css(f['key'])).first, N)              # never leave a typed search ("University o") in the box
    return None, None, ('ambiguous' if 'ambiguous' in (how, how2) else None)


def fill_background(page, log, combo_options, combo_set, N):
    """Fill every Previous Employment / Formal Education row from the facts (bg_plan). Returns (read-back rows, the input
    keys handled, the section ids handled — their date pickers are skipped by the general reader)."""
    work, edus = load_facts()
    rows, keys, secs = [], set(), set()
    for _ in range(4):                                            # add / delete one row at a time, then re-read (the page re-renders)
        changed = False
        for s in page.evaluate(BG_READ):
            p = bg_plan(s, work, edus)
            if not p:
                continue
            if p['delete']:
                i = p['delete'][0]
                log(f"{s['head']}: deleting duplicate row {i + 1}")
                _row(page, s['id'], i).locator('[title="Delete Row"]').first.click(); time.sleep(1.5)
                ok = page.locator('#sfOverlayMgr button:has-text("OK"), #sfOverlayMgr button:has-text("Yes")')
                if ok.count() and ok.first.is_visible(): ok.first.click(); time.sleep(1.5)
                changed = True; break
            if p['add'] and s['add']:
                log(f"{s['head']}: adding a row for {p['add'][0]}")
                page.locator(f'[id="{s["add"]}"]').first.click(); time.sleep(2)
                changed = True; break
        if not changed:
            break
    for s in page.evaluate(BG_READ):
        p = bg_plan(s, work, edus)
        if not p:
            continue
        secs.add(s['id'])
        for i in p['unmatched']:
            rows.append({'key': f"bg:{s['id']}:{i}", 'label': f"{s['head']} row {i + 1}: matches no fact on file", 'type': 'text', 'required': True,
                         'want': None, 'page': '', 'ok': False, 'bg': True})
        for who in p['add']:
            rows.append({'key': f"bg:{s['id']}:add:{who}", 'label': f"{s['head']}: no row for {who}", 'type': 'text', 'required': True,
                         'want': who, 'page': '', 'ok': False, 'bg': True})
        for r in p['rows']:
            row = s['rows'][r['idx']]
            ent = next((e for e in edus if e.get('school') == r['who']), {}) if p['kind'] == 'edu' else {}
            for f in row['fields']:
                keys.add(f['key'])
                lab = _lab(f['label']); ck = canon_label(lab, p['kind']); want = r['set'].get(ck)   # "Company Name" → Company … (an employer 11-05)
                if want is not None and f['type'] != 'combo' and re.fullmatch(r'/.*/i?', str(want)):
                    want = None                                   # a pick pattern ("Present Employer" Yes / No) only fits a list
                rec = {'key': f['key'], 'label': f"{s['head']} ({r['who']}): {lab}", 'type': f['type'], 'required': bool(f.get('required')),
                       'list': f.get('list') or '', 'options': [], 'rule': 'background', 'bg': (s['id'], r['idx'], lab, 'field')}
                try:
                    if want is None:
                        rec['want'] = f['value'] or None                  # no fact for this box: keep what is there (blocks when required and empty)
                    elif f['type'] == 'combo' and ck == 'School Name' and ent:   # a long, searched school list (Acuity "College/University")
                        pick, query, how = edu_school(page, f, ent, combo_options, N)
                        rec['want'] = pick or want; rec['query'] = query
                        if not pick:
                            rec['error'] = (f'{want}: several school list options could be it — Joey' if how == 'ambiguous'
                                            else f'{want} is not in the school list — Joey')
                            rec['nofill'] = True                  # the refill pass must not type the full name again ("University o", an employer 11-05)
                        elif N(f['value']).lower() != N(pick).lower():
                            import sf_combo_edu as CE
                            CE.combo_pick(page, f, pick, N, _css, query=query)
                    elif f['type'] == 'combo':
                        opts = combo_options(page, f)
                        pick = edu_pick(ck, opts, ent) or pick_option(opts, want)
                        rec['want'] = pick or want
                        if not pick:
                            rec['error'] = f'no option for {want} in {opts[:8]}'
                        elif N(f['value']).lower() != N(pick).lower():
                            combo_set(page, f, pick)
                    else:
                        rec['want'] = want
                        if N(f['value']) != N(want):
                            page.locator(f'[id="{f["key"]}"]').first.fill(want)
                except Exception as ex:
                    rec['error'] = f'{type(ex).__name__}: {str(ex)[:100]}'
                rows.append(rec)
            for d in row['dates']:
                want = r['set'].get(canon_label(d['name'], p['kind']))   # education "Start Date" = From Date (an employer 11-05)
                rec = {'key': f"bgdate:{s['id']}:{r['idx']}:{d['name']}", 'label': f"{s['head']} ({r['who']}): {d['name']}", 'type': 'date',
                       'required': bool(d.get('required')) or bool(want), 'rule': 'background', 'bg': (s['id'], r['idx'], d['name'], 'date'),
                       'want': want if want is not None else (d['value'] or None)}
                try:
                    if want and d['value'] != want:
                        box = _date_box(page, s['id'], r['idx'], d['name'])
                        box.scroll_into_view_if_needed(); box.click(); box.fill(want); box.press('Tab'); time.sleep(0.5)   # never Enter (it submits the form)
                except Exception as ex:
                    rec['error'] = f'{type(ex).__name__}: {str(ex)[:100]}'
                rows.append(rec)
        log(f"{s['head']}: {len(p['rows'])} row(s) set from the facts" + (f", unmatched {p['unmatched']}" if p['unmatched'] else '') + (f", missing {p['add']}" if p['add'] else ''))
    return rows, keys, secs


def bg_readback(page, rows, N):
    """Read the background rows again (by section / row / label) and set page / ok on each."""
    secs = {s['id']: s for s in page.evaluate(BG_READ)}
    for r in rows:
        if not isinstance(r.get('bg'), tuple):
            continue
        sid, idx, lab, what = r['bg']
        s = secs.get(sid); got = ''
        if s and idx < len(s['rows']):
            row = s['rows'][idx]
            if what == 'date':
                got = next((d['value'] for d in row['dates'] if d['name'] == lab), '')
            else:
                got = next((f['value'] for f in row['fields'] if _lab(f['label']) == lab), '')
        r['page'] = got
        w = r.get('want')
        r['ok'] = (w is None and not r['required']) or (w is not None and bool(N(got)) and N(got).lower() == N(w).lower())
    return rows
