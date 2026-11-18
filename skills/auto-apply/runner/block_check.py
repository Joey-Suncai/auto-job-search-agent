#!/usr/bin/env python3
"""Profile-block check (JSA-294, Joey 2026-11-11): every education / work block on a form, judged by CODE against the one
fact entry it belongs to.

The block writers (Workday wd_profile blocks, SuccessFactors sf_background / sf_combo_edu, the rules' education section
on Greenhouse / Ashby / Lever, the Oracle / SmartRecruiters / TikTok cards) fill boxes whose labels say only "Degree",
"From", "Overall Result (GPA)", "Job Title". A reader of one box cannot tell which school or employer it belongs to
(bare labels: the whole read stopped 36 % of them, all false alarms), and a box whose fill did not take keeps what the
résumé parse put there: on Workday the parse writes the major GPA 3.85 into UIUC's "Overall Result" box and "Job
Searching Agent" (the side project) into Hyde Park's Job Title (a Workday employer / Jain / an employer / Adobe … 11-01 – 11-10 — there
the fill overwrote them; Review screenshots show 3.60 and Business Analyst Intern).

Here each block is grouped (Workday section "Education 2" / the run's `entry` / a "Education (UIUC): " label prefix / the
order of the rows), its entry is found by the school or employer it names (else the entry the runner aimed at), and every
box is compared with that entry's facts: school, degree level, field of study, start / end, GPA (overall 3.60 · institution
3.81 · major 3.85 · the M.S. has none), still attending; job title, company, location, start / end, "currently work here",
role description. A box the code cannot judge (minor, division, type of business …) is 'unknown': the whole-question read
gets it WITH its entry ("Overall Result (GPA) — education entry: University of Illinois Urbana-Champaign, B.A. Economics").

    import block_check as BC
    BC.problems(rows)            → ["Overall Result (GPA) — education entry University of Illinois …: '3.85' (want 3.60)", …]
    BC.judge(rows)               → {i: {'verdict': 'ok' | 'bad' | 'unknown', 'why', 'context', 'kind', 'entry'}} (block rows only)
rows = runner fields / field-rows / whole-read items in page order: label|question, page, answer|planned|want|value,
source|rule, section, entry, kind. Only the page value is judged when `page_only` (the submit gate: what the form holds).
Used by runner_common.Run.check (Oracle / iCIMS / SmartRecruiters / Workable / SuccessFactors), run_wd before leaving a
page, run_tiktok's read-back, whole_read (code decides block boxes; unknown ones get the entry context) and
scripts/block_check_replay.py.
"""
import datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))


def N(s):
    return ' '.join(str(s if s is not None else '').split())


def low(s):
    return re.sub(r'[^a-z0-9]+', ' ', N(s).lower().replace('&', ' and ')).strip()


# ----------------------------------------------------------------------------- facts
def entries(prof=None, wd=None):
    """{'education': [...], 'work': [...]} from config/profile.json education + config/wd_profile.json (both in the data
    home). Pure when prof / wd are given (tested)."""
    if prof is None or wd is None:
        import jsa_profile
        prof = jsa_profile.load() if prof is None else prof
        if wd is None:
            try:
                wd = json.load(open(jsa_profile.data_file('wd_profile.json', 'JSA_WD_PROFILE'), encoding='utf-8'))
            except (OSError, ValueError):
                wd = {}
    gpa = ((prof.get('answers') or {}).get('gpa_threshold') or {}).get('by') or {}
    edu = []
    for e in prof.get('education') or []:
        w = next((x for x in wd.get('education') or [] if re.search(x.get('match') or '^$', e.get('school') or '', re.I)), {})
        level = str(e.get('level') or w.get('Degree') or '').lower()
        g = str(w.get('GPA') or '')
        gp = {}
        if g:                                                  # the school with a GPA: overall (cumulative) 3.60, major 3.85, institution 3.81
            gp = {'overall': g, 'major': str(gpa.get('major') or ''), 'institution': ''}
            m = re.search(r'institution (\d\.\d+)', json.dumps((prof.get('answers') or {}).get('gpa') or {}))
            if m:
                gp['institution'] = m.group(1)
        fields = [e.get('major'), w.get('Field')] + list(w.get('Field_alts') or []) + list(w.get('Field_prefs') or [])
        edu.append({'kind': 'education', 'name': e.get('school') or w.get('School'), 'short': e.get('short') or '',
                    'match': '|'.join(x for x in (e.get('match_re'), w.get('match')) if x) or re.escape(e.get('school') or ''),
                    'alts': list(w.get('School_alts') or []), 'level': level, 'degree': e.get('degree') or '',
                    'fields': [f for f in dict.fromkeys(fields) if f], 'field_search': list(w.get('Field_search') or []),
                    'gpa': gp, 'start': e.get('start') or w.get('From_month') or w.get('From') or '',
                    'end': e.get('end') or w.get('To_month') or w.get('To') or '', 'current': bool(e.get('current')),
                    'city': e.get('city') or '', 'state': e.get('state') or ''})
    work = []
    for w in wd.get('work') or []:
        work.append({'kind': 'work', 'name': w.get('Company') or '', 'match': w.get('match') or re.escape(w.get('Company') or ''),
                     'title': w.get('Job Title') or '', 'location': w.get('Location') or '', 'start': w.get('From') or '',
                     'end': w.get('To') or '', 'current': bool(w.get('current')), 'desc': w.get('Description') or ''})
    return {'education': edu, 'work': work}


def describe(e):
    """The entry as the reader sees it: "University of Illinois Urbana-Champaign, B.A. Economics (2024-08 – 2026-05, completed)"."""
    if not e:
        return ''
    if e['kind'] == 'education':
        return '%s, %s (%s – %s, %s)' % (e['name'], e['degree'] or e['level'], e['start'] or '?', e['end'] or '?',
                                         'in progress' if e['current'] else 'completed')
    return '%s, %s (%s – %s, ended)' % (e['title'], e['name'], e['start'] or '?', e['end'] or '?')


# ----------------------------------------------------------------------------- labels → box
PREFIX = re.compile(r'^\s*((?:formal |your )?education|previous employment|work experience|employment|experience)\s*\(([^)]{2,120})\)\s*:\s*(.+)$', re.I | re.S)
EDU_BOX = [   # (box, label regex) — first hit wins; checked on the label without a "Education (X): " prefix
    ('gpa', r'\bgpa\b|overall result|grade point|cumulative (average|result)'),
    ('school', r'^(?!.*\b(major|minor|degree|gpa|year|month|date|city|state|location|country|type|level)\b)(name of )?(school|university|institution|college)( or university| name|/institution( name)?|/university)?\b|^college/univers'),
    ('degree_done', r'degree achieved|did you graduate|^graduated\b|degree (completed|status)|^result$'),
    ('end', r'completion date|^date (ended|of graduation)'),
    ('field', r'^if other, enter area of study|^subject$'),
    ('degree', r'^type$'),
    ('current', r'still attending|currently (attend|enrolled)|i currently attend'),
    ('degree', r'^(degree|education type|degree type|degree/certific\w*|level of education|degree level|education level)\b'),
    ('field', r'^(field of study|major|area of study|area of focus|major/area of focus|discipline|concentration|major \(legacy\)|program)\b'),
    ('minor', r'^minor\b'),
    ('start', r'^(from|start)( date| month| year)?\b|^date started|^start date (month|year)'),
    ('end', r'^(to|end)( date| month| year)?\b|^(to|end) \(actual or expected\)|graduation (date|year|month)|expected graduation|^date (ended|of graduation)'),
]
WORK_BOX = [
    ('title', r'^(job title|title|position( title)?)\b'),
    ('company', r'^(company|employer|company name|employer name|organi[sz]ation)\b'),
    ('location', r'^(location|city|office location)\b'),
    ('current', r'currently work|present employer|current (job|employer)'),
    ('start', r'^(from|start)( date| month| year)?\b'),
    ('end', r'^(to|end)( date| month| year)?\b'),
    ('desc', r'^(role description|description|responsibilities|job description|duties|summary of work performed)\b'),
]
EDU_RULES = {'school', 'degree', 'discipline', 'major', 'gpa', 'gpa_current', 'start_year', 'start_month', 'end_year', 'end_month',
             'grad_date', 'grad_year', 'grad_month'}


def split_label(label):
    """Pure (tested). "Education (UIUC): Degree" → ('education', 'UIUC', 'Degree'); a plain label → (None, '', label)."""
    m = PREFIX.match(N(label))
    if not m:
        return None, '', N(label)
    kind = 'education' if 'educ' in m.group(1).lower() else 'work'
    return kind, m.group(2).strip(), m.group(3).strip()


TT_KEY = re.compile(r'^(education|internship|work)\[(\d+)\]\.(\w+)$')            # TikTok formily keys: "education[0].degree"
TT_BOX = {'school': 'school', 'degree': 'degree', 'fieldOfStudy': 'field', 'period': 'period', 'title': 'title', 'company': 'company'}


def box_of(kind, label):
    """Pure (tested). Which box of an education / work block a (prefix-free) label is; None = not a block box."""
    lab = N(label)
    m = TT_KEY.match(lab)
    if m:
        return TT_BOX.get(m.group(3))
    if len(lab) > 70 or re.search(r'high school|secondary', lab, re.I):
        return None
    for box, rx in (EDU_BOX if kind == 'education' else WORK_BOX):
        if re.search(rx, lab, re.I):
            if box in ('start', 'end'):                        # "Start date month" + "Start date year" are two boxes of one block
                part = 'month' if re.search(r'\bmonth\b', lab, re.I) else 'year' if re.search(r'\byear\b', lab, re.I) else ''
                return box + ('_' + part if part else '')
            return box
    return None


def row_label(r):
    return N(r.get('label') or r.get('question') or r.get('key') or '')


def row_value(r, page_only=False):
    """The value judged: what the page holds; else (not page_only) what the runner meant to write."""
    v = r.get('page')
    if isinstance(v, list):
        v = ' | '.join(map(str, v))
    if v not in (None, '') or page_only:
        return N(v)
    for k in ('answer', 'value', 'planned', 'want'):          # a whole-read item's value = the answer about to be written
        if r.get(k) not in (None, '', []):
            x = r[k]
            return N(' | '.join(map(str, x)) if isinstance(x, list) else x)
    return ''


def row_hint(r):
    """Pure (tested). (kind, name hint, section) the runner recorded for a row: the plan's entry dict, a "Education 2"
    section / source, a wd_profile:<kind> / background / education_combo source, or a label prefix."""
    src = str(r.get('source') or r.get('rule') or '')
    sec = N(r.get('section') or '')
    m = re.match(r'^wd_answered:(.+)$', src)
    if m and not sec:
        sec = m.group(1)
    kind, name = None, ''
    e = r.get('entry')
    if isinstance(e, dict):
        name = e.get('School') or e.get('Company') or e.get('school') or e.get('name') or ''
        kind = 'education' if (e.get('School') or e.get('school')) else 'work' if (e.get('Company') or e.get('Job Title')) else None
    k2 = r.get('kind')
    if k2 in ('education', 'work'):
        kind = k2
    if not kind:
        m = re.match(r'^wd_profile:(education|work)$', src)
        if m:
            kind = m.group(1)
        elif re.search(r'educat|school', sec, re.I):
            kind = 'education'
        elif re.search(r'experience|employment|work', sec, re.I):
            kind = 'work'
    m = TT_KEY.match(row_label(r))
    if m:
        kind, sec = kind or ('education' if m.group(1) == 'education' else 'work'), sec or '%s[%s]' % (m.group(1), m.group(2))
    pk, pname, _ = split_label(row_label(r))
    if pk:
        kind, name = kind or pk, name or pname
    if not kind and src.startswith('education_combo'):
        kind = 'education'
    return kind, name, sec


def is_block_row(r):
    """Pure (tested). A row the block writers wrote (or a rule's education-section box): it has a block hint, or a rule
    from the education section on a short box label."""
    kind, _, sec = row_hint(r)
    if kind in ('education', 'work') and (sec or r.get('entry') or kind):
        _, _, base = split_label(row_label(r))
        return box_of(kind, base) is not None or bool(re.match(r'^(wd_profile|wd_answered|background|education_combo)', str(r.get('source') or '')))
    rule = re.sub(r'^rules?:', '', str(r.get('rule') or r.get('source') or ''))
    return rule in EDU_RULES and box_of('education', row_label(r)) is not None


# ----------------------------------------------------------------------------- grouping
ANCHOR = {'education': ('school',), 'work': ('title', 'company')}


def blocks(rows):
    """Pure (tested). Block rows (in page order) → [{'kind', 'section', 'name_hint', 'idx': [row index]}]. A new block
    starts at a new section / entry hint, at a box the current block already has (a second "School or University"), or
    after a non-block row."""
    out, cur, last = [], None, -9
    for i, r in enumerate(rows):
        lab = split_label(row_label(r))[2]
        if not is_block_row(r):
            # a box of the open block written by another writer (Workday "Field of Study" from prefs-match / answers.json)
            if cur is None or i != last + 1 or box_of(cur['kind'], lab) is None or str(r.get('source') or '').startswith('rules'):
                continue
        kind, name, sec = row_hint(r)
        kind = kind or (cur['kind'] if cur is not None and i == last + 1 else 'education')
        box = box_of(kind, lab)
        ent = r.get('entry') if isinstance(r.get('entry'), dict) else None
        key = sec or (('entry', id(ent)) if ent is not None else None) or (('name', low(name)) if name else None)
        unkeyed = key is None or cur is None or cur['key'] is None
        new = (cur is None or cur['kind'] != kind or i > last + 4                          # another kind, or far from the block
               or (key is not None and cur['key'] is not None and key != cur['key'])      # another section / entry / prefix
               or (unkeyed and i != last + 1)                                             # a question in between
               or (unkeyed and low(lab) in cur['labels'] and box != 'desc')               # a box the block already has
               or (unkeyed and box in ANCHOR[kind] and not cur['boxes'] & set(ANCHOR[kind])))   # its school / company starts a block
        if new:
            cur = {'kind': kind, 'key': key, 'section': sec, 'name_hint': name, 'idx': [], 'boxes': set(), 'labels': set()}
            out.append(cur)
        elif key is not None and cur['key'] is None:
            cur['key'] = key
        cur['idx'].append(i)
        cur['labels'].add(low(lab))
        if box:
            cur['boxes'].add(box)
        if name and not cur['name_hint']:
            cur['name_hint'] = name
        last = i
    keep = []
    for b in out:                                              # a lone rule question ("What is your GPA?") is not a block: the whole read keeps it
        hinted = b['key'] is not None or any(row_hint(rows[i])[0] for i in b['idx'])
        if hinted or b['boxes'] & set(ANCHOR[b['kind']]):
            keep.append(b)
        b.pop('boxes', None); b.pop('key', None); b.pop('labels', None)
    return keep


def find_entry(kind, text, ents):
    t = N(text)
    if not t:
        return None
    for e in ents.get(kind) or []:
        if re.search(e['match'], t, re.I) or (e.get('short') and re.search(r'\b%s\b' % re.escape(e['short']), t, re.I)) \
                or any(low(a) == low(t) for a in e.get('alts') or []):
            return e
    return None


# ----------------------------------------------------------------------------- dates / numbers
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def ym(s):
    """Pure (tested). "8/2025" · "08/2025" · "2026-09" · "09/01/2026" · "Sep 2026" · "2026" → (year, month | None); None."""
    s = N(s).lower().rstrip('.')
    for rx, f in ((r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', lambda m: (int(m[3]), int(m[1]))),
                  (r'(\d{4})-(\d{1,2})(-\d{1,2})?(t.*)?', lambda m: (int(m[1]), int(m[2]))),
                  (r'(\d{1,2})[/.-](\d{4})', lambda m: (int(m[2]), int(m[1]))),
                  (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(\d{1,2},?\s+)?(\d{4})', lambda m: (int(m[3]), MONTHS[m[1]])),
                  (r'(\d{4})', lambda m: (int(m[1]), None))):
        m = re.fullmatch(rx, s)
        if m:
            y, mo = f(m)
            return (y, mo) if mo is None or 1 <= mo <= 12 else None
    m = re.fullmatch(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*', s)
    return (None, MONTHS[m.group(1)]) if m else None


def date_ok(page, fact):
    a, b = ym(page), ym(fact)
    if not a or not b:
        return None
    if a[0] is not None and b[0] is not None and a[0] != b[0]:
        return False
    if a[1] is not None and b[1] is not None and a[1] != b[1]:
        return False
    return True


def yes(v):
    return bool(re.fullmatch(r'(checked|yes|true|on|1|y|currently attending|i currently attend)', low(v)))


def no(v):
    return bool(re.fullmatch(r'(no|false|off|0|n|unchecked|not checked)', low(v)))


NONE_LIKE = re.compile(r'^(n/?a|none|not applicable|no gpa( yet)?|not yet available|-|0|0\.0+)$', re.I)


def gpa_ok(label, v, e):
    """None = cannot judge; True / False."""
    if NONE_LIKE.match(v):
        return True                                            # N/A or none: a required M.S. GPA (decisions-log 10-30); generic 3.60-or-none (Joey 11-10)
    m = re.fullmatch(r'(\d\.\d+)\s*(/\s*4(\.0+)?)?', v)
    band = re.fullmatch(r'(\d\.\d+)\s*(-|–|to)\s*(\d\.\d+)', v)
    g = e.get('gpa') or {}
    if not g:
        return False if (m or band) else None                  # a number in the M.S. block: it has no GPA yet (AMAT 10-30: UIUC's copied in)
    want = g.get('major') if re.search(r'\bmajor\b', label, re.I) else g.get('institution') if re.search(r'institution', label, re.I) else g.get('overall')
    want = want or g.get('overall')
    if m:
        return abs(float(m.group(1)) - float(want)) < 0.005
    if band:
        return float(band.group(1)) <= float(want) <= float(band.group(3))
    return None


def level_of(v):
    t = N(v)
    if re.search(r'under ?-?grad', t, re.I):                 # before the master test: "Undergraduate Degree" holds "graduate degree"
        return 'bachelor'
    if re.search(r'master|\bm\.?\s?s\.?c?\b|\bm\.?\s?a\b|\bmba\b|^ms$|^msc$', t, re.I):
        return 'master'                                       # JSA-327: "Post-Graduate Degree (Master's, PhD, JD, etc.)" lists PhD as an example — it is the master's level (Entrust)
    if re.search(r'\b(ph\.?\s?d|doctor)', t, re.I):
        return 'phd'                                          # "Doctorate - Post Graduate" stays PhD
    if re.search(r'post ?-?grad|^graduate\b|graduate degree', t, re.I):
        return 'master'
    if re.search(r'bachelor|under ?-?grad|\bb\.?\s?a\b|\bb\.?\s?s\b|^ba$|^bs$|baccalaureate', t, re.I):
        return 'bachelor'
    if re.search(r'associate|high school|secondary|diploma|ged\b', t, re.I):
        return 'other'
    return None


def words(s):
    return {w for w in low(s).split() if len(w) > 3}


def period_ok(v, e):
    """A "start end" period box (TikTok): the first month = the entry's start, the last = its end (or Present while current)."""
    got = re.findall(r'(\d{4})\D(\d{1,2})\b|\b(\d{1,2})/(\d{4})\b', v)
    ms = ['%s-%02d' % ((a or d), int(b or c)) for a, b, c, d in got]
    if not ms:
        return 'unknown', ''
    if date_ok(ms[0], e['start']) is False:
        return 'bad', 'period starts %s (want %s)' % (ms[0], e['start'])
    if len(ms) > 1 and date_ok(ms[-1], e['end']) is False:
        return 'bad', 'period ends %s (want %s)' % (ms[-1], e['end'])
    if len(ms) == 1 and not e.get('current') and not re.search(r'present', v, re.I):
        return 'unknown', ''
    return 'ok', ''


# ----------------------------------------------------------------------------- one box
def judge_box(kind, box, label, v, e, ents, today=None, overrides=None):
    """Pure (tested). (verdict, why): 'ok' | 'bad' | 'unknown'. v = the box's value (non-empty)."""
    today = today or datetime.date.today().isoformat()
    other = [x for x in ents.get(kind) or [] if x is not e]
    ov = (overrides or {}).get(box)
    if ov is not None and low(ov) == low(v):
        return 'ok', "Joey's answer for this application (answers.json)"
    if kind == 'education':
        if box == 'school':
            hit = find_entry('education', v, ents)
            if hit is e:
                return 'ok', 'the entry\'s school'
            return 'bad', ('names %s — the block is for %s' % (hit['name'], e['name'])) if hit else ('%r is not one of his schools' % v)
        if box == 'degree':
            lv = level_of(v)
            if lv is None:
                return ('ok', '"Other" allowed') if low(v) == 'other' else ('unknown', 'degree option not recognised')
            return ('ok', 'degree level %s' % lv) if lv == e['level'] else ('bad', 'degree level %s (want %s)' % (lv, e['level']))
        if box in ('degree_done', 'current'):
            done = not e['current'] and str(e['end'])[:7] <= today[:7]
            if box == 'current':
                if not (yes(v) or no(v)):
                    return 'unknown', ''
                return ('ok', '') if yes(v) == (not done) else ('bad', 'still attending = %r (the entry is %s)' % (v, 'completed' if done else 'in progress'))
            if re.fullmatch(r'graduated|completed?', low(v)):
                return ('ok', '') if done else ('bad', '%r (the degree is in progress)' % v)
            if re.search(r'in progress|pursuing|expected|currently', v, re.I):
                return ('ok', '') if not done else ('bad', '%r (the degree is completed)' % v)
            if yes(v) or no(v):
                return ('ok', '') if yes(v) == done else ('bad', '%r (the degree is %s)' % (v, 'completed' if done else 'in progress'))
            return 'unknown', ''
        if box == 'field':
            t = low(v)
            mine = [low(f) for f in e['fields']]
            if any(t == f or (f and (f in t or t in f)) for f in mine) or t == 'other':
                return 'ok', 'field of study of this entry'
            theirs = [low(f) for x in other for f in x['fields'] if low(f) not in mine]
            if any(t == f or (len(f) > 4 and f in t) for f in theirs):
                return 'bad', '%r is the field of the other school' % v
            if any(re.search(re.escape(s), v, re.I) for s in e.get('field_search') or []):
                return 'ok', 'a fallback field (Field_search, Joey 10-28)'
            return 'unknown', 'field option not in the profile list'
        if box == 'gpa':
            r = gpa_ok(label, v, e)
            if r is None:
                return 'unknown', ''
            if r:
                return 'ok', ''
            g = e.get('gpa') or {}
            want = (g.get('major') if re.search(r'\bmajor\b', label, re.I) else g.get('overall')) if g else 'empty / N/A (no GPA yet)'
            return 'bad', 'GPA %r (want %s)' % (v, want)
        if box.split('_')[0] in ('start', 'end'):
            r = date_ok(v, e[box.split('_')[0]])
            return ('unknown', '') if r is None else ('ok', '') if r else ('bad', '%s %r (want %s)' % (box, v, e[box.split('_')[0]]))
        if box == 'period':
            return period_ok(v, e)
        return 'unknown', ''
    if box == 'period':
        return period_ok(v, e)
    # work
    if box == 'company':
        hit = find_entry('work', v, ents)
        if hit is e:
            return 'ok', ''
        return 'bad', ('names %s — the block is for %s' % (hit['name'], e['name'])) if hit else ('%r is not one of his employers' % v)
    if box == 'title':
        if low(v) == low(e['title']):
            return 'ok', ''
        hit = next((x for x in other if low(x['title']) == low(v)), None)
        return 'bad', ('%r is the title at %s' % (v, hit['name'])) if hit else ('%r (want %s)' % (v, e['title']))
    if box == 'location':
        city = low(e['location'].split(',')[0]) if e['location'] else ''
        return ('ok', '') if city and city in low(v) else ('unknown', '')
    if box == 'current':
        return ('ok', '') if no(v) else ('bad', '"currently work here" = %r (the internship ended %s)' % (v, e['end'])) if yes(v) else ('unknown', '')
    if box.split('_')[0] in ('start', 'end'):
        r = date_ok(v, e[box.split('_')[0]])
        return ('unknown', '') if r is None else ('ok', '') if r else ('bad', '%s %r (want %s)' % (box, v, e[box.split('_')[0]]))
    if box == 'desc':
        mine, page = words(e['desc']), words(v)
        if not page or not mine:
            return 'unknown', ''
        share = len(mine & page) / max(1, min(len(mine), len(page)))
        if share >= 0.35:
            return 'ok', ''
        return 'bad', 'the description is not this job\'s (%d %% of its words): %r' % (round(100 * share), v[:70])
    return 'unknown', ''


# ----------------------------------------------------------------------------- the check
def judge(rows, ents=None, page_only=False, today=None, overrides=None):
    """{row index: {'verdict', 'why', 'context', 'kind', 'entry', 'box'}} for every block row. overrides = the folder's
    answers.json ("edu:<School>:GPA" / ":Degree" / ":Field" — Joey per application)."""
    ents = entries() if ents is None else ents
    out = {}
    for b in blocks(rows):
        kind = b['kind']
        names = [row_value(rows[i], page_only) for i in b['idx'] if box_of(kind, split_label(row_label(rows[i]))[2]) in (ANCHOR[kind])]
        aimed = find_entry(kind, b['name_hint'], ents)
        if not aimed:
            for i in b['idx']:
                r = rows[i]
                if box_of(kind, split_label(row_label(r))[2]) in ANCHOR[kind]:
                    aimed = aimed or find_entry(kind, row_value(dict(r, page=None)), ents)
        shown = next((x for x in (find_entry(kind, n, ents) for n in names) if x), None)
        e = aimed or shown
        if e is None and kind == 'work':                       # a parsed block with no company: the title may name the job
            e = next((x for x in ents.get('work') or [] for n in [row_value(rows[i], page_only) for i in b['idx']] if low(n) == low(x['title'])), None)
        ctx = ('%s entry: %s' % (kind, describe(e))) if e else ('%s block %s (no matching entry)' % (kind, b['section'] or b['name_hint'] or '?'))
        ovr = {}
        if e and kind == 'education':
            for k, box in (('GPA', 'gpa'), ('Degree', 'degree'), ('Field', 'field')):
                v = (overrides or {}).get('edu:%s:%s' % (e['name'], k))
                if v:
                    ovr[box] = v
        for i in b['idx']:
            r = rows[i]
            lab = split_label(row_label(r))[2]
            box = box_of(kind, lab)
            v = row_value(r, page_only)
            d = {'kind': kind, 'entry': e['name'] if e else None, 'box': box, 'context': ctx, 'section': b['section']}
            if not v or v in ('[]',):
                out[i] = dict(d, verdict='ok' if box else 'unknown', why='empty (the read-back gate judges empty boxes)')
            elif e is None:
                out[i] = dict(d, verdict='bad' if box in ANCHOR[kind] else 'unknown', why='%s block matches no profile entry (a résumé-parsed block?)' % kind)
            elif box is None:
                out[i] = dict(d, verdict='unknown', why='')
            else:
                vd, why = judge_box(kind, box, lab, v, e, ents, today, ovr)
                out[i] = dict(d, verdict=vd, why=why)
    return out


def problems(rows, ents=None, page_only=True, today=None, overrides=None):
    """The 'bad' boxes as problem lines for a submit gate (page values only by default)."""
    rows = list(rows or [])
    out = []
    for i, d in sorted(judge(rows, ents, page_only, today, overrides).items()):
        if d['verdict'] == 'bad':
            out.append('%s — %s: %s' % (split_label(row_label(rows[i]))[2][:40], d['context'][:90], d['why']))
    return out


def load_overrides(folder):
    try:
        return json.load(open(os.path.join(folder, 'answers.json'), encoding='utf-8')) if folder else {}
    except (OSError, ValueError):
        return {}


if __name__ == '__main__':
    data = json.load(sys.stdin)
    print(json.dumps({str(k): v for k, v in judge(data).items()}, ensure_ascii=False, indent=1))
