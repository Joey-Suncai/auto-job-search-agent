#!/usr/bin/env python3
"""Canonical-answer audit: what the form ACTUALLY says vs Joey's confirmed facts.

Why this exists: every wrong answer on 2026-10-28 came from matching option TEXT with a
regex (a Workday employer degree -> "Masters of Technology"; veteran -> "I identify as a Veteran, just not a
protected Veteran"; source -> "104 Job Bank"; a Workday employer "authorized as of today" -> Yes). All of
them PASSED verify.js, because the plan itself was wrong. verify.js compares the page with the
plan; this module compares the page with the facts, independently of any plan, at gate time.
A mismatch is a hard block: the runner never submits.

Data   : config/canonical.json (accept/exact patterns + the evidence line for each fact)
Learned: data/runner/canon_learned.json  {"<tenant>": {"<key>": ["<option text>", ...]}}
         written after Joey confirms a value the patterns do not cover, so each tenant converges.

Pick   : canon.pick(key, options, tenant) — the right option from a field's own list (plan_build and run_wd use it
         before any rule text match or DeepSeek pick, JSA-005)
CLI    : python3 canon.py --check-file records.json [--tenant myworkdayjobs.com]
         records = [{"label": "...", "value": "..."}, ...]
         python3 canon.py --learn <tenant> <key> <option text>   # accept a value Joey confirmed (fact gate keys: fact:<key>, JSA-281)
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
DATA = os.environ.get('CX_DATA') or jpaths.data('runner')
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402
SPEC = json.load(open(jsa_profile.data_file('canonical.json', 'JSA_CANONICAL'), encoding='utf-8'))   # the candidate's high-stakes answers (moved to config/ 2026-11-02, JSA-077)


def norm(s):
    s = str(s if s is not None else '')
    s = re.sub('[\u200b-\u200d\u2060\ufeff\u00ad]', '', s)   # zero-width / soft-hyphen characters in option text (Danfoss 11-05: 'I am not a protected veteran\u200b')
    s = s.replace('\u2019', "'").replace('\u2018', "'").replace('\u2013', '-').replace('\u2014', '-')
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s.rstrip('.').strip()


def classify(label):
    """Which canonical field a form label refers to (None = not high-stakes)."""
    lab = norm(label)
    if not lab:
        return None
    for key in SPEC['order']:
        spec = SPEC['fields'][key]
        if re.search(spec['label_re'], lab, re.I):
            # some labels are the same words but a different question ("Are you Hispanic or Latino … regardless of race?")
            if spec.get('label_not') and re.search(spec['label_not'], lab, re.I):
                continue
            return key
    return None


def learned(tenant):
    p = os.path.join(DATA, 'canon_learned.json')
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p, encoding='utf-8')).get(tenant or '', {})
    except Exception:
        return {}


def learn(tenant, key, value):
    p = os.path.join(DATA, 'canon_learned.json')
    all_ = {}
    if os.path.exists(p):
        try:
            all_ = json.load(open(p, encoding='utf-8'))
        except Exception:
            all_ = {}
    vals = all_.setdefault(tenant or '', {}).setdefault(key, [])
    if norm(value) not in [norm(v) for v in vals]:
        vals.append(str(value))
        json.dump(all_, open(p, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


def check(key, value, tenant=None):
    """(ok, reason). Accepts, in order: a learned value for this tenant, an exact text, an accept regex."""
    spec = SPEC['fields'].get(key)
    if not spec:
        return True, 'not a canonical field'
    v = norm(value)
    if not v:
        return False, 'empty'
    for lv in learned(tenant).get(key, []):
        if norm(lv) == v:
            return True, 'learned for this tenant'
    if v in [norm(x) for x in spec.get('accept_exact', [])]:
        return True, 'exact'
    if key == 'degree_level' and not degree_field_ok(v):
        return False, 'the degree names a field that is not his (want %s)' % spec.get('want')
    for w in [v] + ([abbr_rest(v)] if key in ABBR_PREFIX and abbr_rest(v) else []):
        if w in [norm(x) for x in spec.get('accept_exact', [])] or any(re.search(p, w, re.I) for p in spec.get('accept', [])):
            bad = [p for p in (spec.get('reject') or []) if re.search(p, v, re.I) or re.search(p, w, re.I)]
            if bad:
                return False, 'matched accept but also reject %r' % bad[0]
            return True, 'pattern' if w == v else 'pattern (after the abbreviation prefix)'
    return False, 'no accept pattern matched (want %s)' % spec.get('want')


DEGREE_FIELD_RX = re.compile(r"^(master|bachelor)\S*(?: (?:of|in) (?:science|arts))?(?: degree)? in (.+)$|^([mb])\.? ?(?:s|a)\.?c?\.? in (.+)$")
HIS_DEGREE_FIELDS = {'master': re.compile(r'^((applied )?data science|(data )?analytics|statistics|computer science)\b'),
                     'bachelor': re.compile(r'^economics\b')}   # his M.S. Applied Data Science / B.A. Economics (Joey 2026-11-10, JSA-282)


def degree_field_ok(value):
    """Pure (tested, JSA-282). A degree option that names a field ("Master of Science in Taxation", "M.S. in Statistics",
    "B.A. - Bachelor of Arts in Economics") passes only when the field is one of his (master: data science / applied data
    science / analytics / statistics / computer science; bachelor: economics). No field named → True."""
    v = norm(value)
    full = abbr_rest(v) or v
    m = DEGREE_FIELD_RX.match(full)
    if not m:
        return True
    level = m.group(1) or {'m': 'master', 'b': 'bachelor'}[m.group(3)]
    return bool(HIS_DEGREE_FIELDS[level].match((m.group(2) or m.group(4)).strip()))


ABBR_PREFIX = {'degree_level'}   # fields whose options may read "<abbreviation> - <full name>" (JSA-282)
ABBR_RX = re.compile(r'^((?:[a-z]{1,4}\.?){1,3})\s*[-:|/]\s*(\S.*)$')


def abbr_rest(v):
    """Pure (tested, JSA-282). A normalised option "b.a. - bachelor of arts" → "bachelor of arts" (the full name after a
    short abbreviation prefix: Vanguard 2026-11-10); no such prefix → None. Reject patterns still see the whole text."""
    m = ABBR_RX.match(v or '')
    return m.group(2).strip() if m and len(m.group(1).replace('.', '')) <= 6 else None


PER_ENTRY = {'school', 'degree_level', 'education_field'}   # differ per education block: checked, never picked


PICK_NEVER = {'source_channel': re.compile(r'\brefer(r(al|ed|er|ing))?\b|\brecruiters?\b|\bemployees?\b|\bfriends?\b|\bcolleagues?\b|\bco-?workers?\b|\bword of mouth\b|\bfamily\b', re.I)}
# never PICKED for him: "Employee referral" as his source; nor an option that claims a person reached him — "Radix Recruiter",
# "Radix Employee" (JSA-219, Radix 11-05): the first option of the menu (Joey 2026-10-30) means the first TRUE one
                                                                                   # (JSA-195 — a referral is decided per company by the referrer pool, never auto-filled)


def pick(key, options, tenant=None):
    """The option a form should get for a canonical field, chosen from its OWN option list (JSA-005): a value learned for
    this tenant first, then an exact accepted text (spec order), then the first option (page order) that passes check().
    None when no option passes — the caller asks Joey instead of guessing. Never calls a model."""
    spec = SPEC['fields'].get(key)
    opts = [o for o in (options or []) if str(o).strip() and not (key in PICK_NEVER and PICK_NEVER[key].search(str(o)))]
    if not spec or not opts or key in PER_ENTRY:
        return None
    by_norm = {norm(o): o for o in opts}
    for lv in learned(tenant).get(key, []):
        if norm(lv) in by_norm:
            return by_norm[norm(lv)]
    for ex in spec.get('accept_exact', []):
        if norm(ex) in by_norm:
            return by_norm[norm(ex)]
    for o in opts:
        if re.search(r'^(select one|please select|--|choose)', norm(o)):
            continue
        if check(key, o, tenant)[0]:
            return o
    return None


SKIP_TYPES = {'textarea', 'file', 'date'}  # open essays, uploads and dates are never canonical answers (JSA-186; Oracle
                                            # 'Newly Separated Veteran Discharge Date' = '//', Ricoh 11-04)
SECTION_RE = re.compile(r'^(.+?)\(([^()]*)\)\s*:\s*(.+)$')   # "Formal Education (University of Chicago): Type"
INVERT_RE = re.compile(r'\bwithout\b.{0,60}\bsponsor|\b(do|does|will|would) not (need|require)\b.{0,40}\bsponsor', re.I)
NOW_ONLY_RE = re.compile(r'\b(for|in|during) (the duration of )?(this|the) (internship|position|role|job)\b|\bduration of (this|the|my) internship|\b(now|currently|at this time|today)\b'
                         r'|\b(e\.g\.|such as|including)[^?]{0,40}\b(opt|cpt)\b|\((e\.g\.,? )?[^)]{0,30}\b(opt|cpt)\b[^)]*\)', re.I)   # = answer_rules SPONS_NOW_ONLY (JSA-279)
FUTURE_RE = re.compile(r'future|after graduat|at any time|any time after|later|eventually|going forward|upon graduation|full[- ]time', re.I)
BOOL = {'true': True, 'false': False}


def question_of(label):
    """The question part of a label: for "Section (entry name): Field" the entry name only names the block (JSA-186)."""
    m = SECTION_RE.match(str(label or '').strip())
    return m.group(3) if m else (label or '')


def yes_no_key(key):
    return norm(SPEC['fields'].get(key, {}).get('want', '')) in ('yes', 'no')


def flip(v):
    n = norm(v)
    return 'No' if re.match(r'^yes\b', n) else 'Yes' if re.match(r'^no\b', n) else v


def inverted_key(key, label):
    """(key, inverted) for a label: a "…without sponsorship…" question asks the opposite of "do you need sponsorship" —
    judged with the answer flipped, against the NOW answer when it covers only now / this internship, else the future one."""
    q = norm(question_of(label))
    if key in ('sponsorship_future', 'sponsorship_now') and INVERT_RE.search(q):
        return ('sponsorship_now' if NOW_ONLY_RE.search(q) and not FUTURE_RE.search(q) else key), True
    return key, False


SECOND_MAJOR_RE = re.compile(r"\b(second(ary)?|double|additional|2nd|other) (major|discipline|field( of study)?|concentration)\b|\bminor\b|\bmajor\s*(#?\s*2|two)\b", re.I)   # = answer_rules SECOND_MAJOR
MAJOR_AND_MINOR_RE = re.compile(r"\bmajor(s|\(s\))?(?!\w)[^?]{0,30}(\band\b|&|/)\s*(any )?minor|\bin addition to\b", re.I)   # "major and minor?" asks the major (Protective 11-02)
NONE_RE = re.compile(r"^(none|n/?a|not applicable|no( second(ary)? major| minor)?|-+)$", re.I)


def second_major_q(label):
    """Pure (tested, JSA-293). True when an education-field question asks a SECOND major / minor ("Secondary Major", "Double
    major", "Minor", "Major 2") — the same test as answer_rules majorWhich 'second'; "major and minor" asks the major."""
    q = str(question_of(label) or '')
    return bool(SECOND_MAJOR_RE.search(q)) and not MAJOR_AND_MINOR_RE.search(q)


def second_major_left_empty(value, secondary=None):
    """Pure (tested, JSA-293). True when a second-major / minor answer is right because none is on file (Joey 2026-11-10,
    JSA-281: left empty): no secondary major in the facts and the value empty or a none-like option ("None", "N/A", "Not
    applicable"). A real field there is fact_gate's mismatch (a Greenhouse employer 10-28 got "Data Science"); one on file → False."""
    v = norm(value)
    return not norm(secondary) and (not v or bool(NONE_RE.match(v)))


def judge(key, label, value, tenant=None):
    """check() with the label's inversion applied (the one rule audit() uses) → (ok, why)."""
    k, inv = inverted_key(key, label)
    if not inv:
        return check(key, value, tenant)
    ok, why = check(k, flip(value), tenant)
    want = SPEC['fields'].get(k, {}).get('want', '')
    return ok, (why if ok else 'inverted question ("without sponsorship"): needs %s = %s, so this question wants %s, got %r'
                % (k, want, flip(want), str(value)[:60]))


def pick_for(key, label, options, tenant=None):
    """pick() for a label: on a "…without sponsorship…" question the option whose FLIPPED answer passes (JSA-267: an Ashby employer
    11-10 "authorized … without the need for sponsorship now or in the future?" — pick() alone took 'Yes', the plain
    sponsorship answer, over the rules' right 'No - I would need sponsorship'). None when no option passes."""
    k, inv = inverted_key(key, label)
    if not inv:
        return pick(key, options, tenant)
    for o in options or []:
        if str(o).strip() and not re.search(r'^(select one|please select|--|choose)', norm(o)) and check(k, flip(o), tenant)[0]:
            return o
    return None


DEGREE_STATE_Q = re.compile(r'^\W*degree (achieved|earned|obtained|received|awarded|completed)\W*$', re.I)


def entry_of(label):
    """Pure. The "Section (entry)" part of a background-row label ("Education (University of Chicago): Area of Study" →
    "education (university of chicago)"); '' for a label without one."""
    m = re.match(r'^(.{1,120}?\([^)]{1,80}\))\s*:', str(label or ''))
    return norm(m.group(1)) if m else ''


def other_school_entries(records, tenant=None):
    """Pure (tested, JSA-295). The entries whose "If other, enter School / Institution Name" box holds a school name that
    passes the canon — there a School list set to "Other" is his answer, not a wrong school (an employer 11-10). A form without
    "Section (entry):" labels gives the entry '' (JSA-321: "If your school is not listed above, please enter the school
    name here")."""
    out = set()
    for rec in records or []:
        label = rec.get('label') or ''
        q = question_of(label)
        if re.search(r'\bother\b|not listed|specify', q, re.I) and classify(q) == 'school' \
                and norm(rec.get('value')) and check('school', rec.get('value'), tenant)[0]:
            out.add(entry_of(label))
    return out


CURRENT_Q = re.compile(r'\bcurrent(ly)?\b|\b(attend|attending|enrolled)\b', re.I)


def current_school_tokens():
    """His current school as option tokens: 'University of Chicago' → {'chicago', 'uchicago'} (profile education[].current)."""
    out = set()
    for e in (jsa_profile.load().get('education') or []):
        if e.get('current') and e.get('school'):
            t = re.sub(r'\b(the|university|college|institute|school|of|at)\b', ' ', norm(e['school'])).split()
            if t:
                out |= {' '.join(t), 'u' + ''.join(t)}
    return out


def other_is_only_pick(options, tenant=None, label=''):
    """Pure-ish (tested, JSA-321). True when a School list is known (options given) and none of its options is his
    school: there "Other" is the only true pick. A question about the school he attends NOW counts only his current
    school (a Greenhouse employer 10-31 offered UIUC, not UChicago: "Other" is right; a Greenhouse employer 10-31 offered "UChicago": "Other" is wrong).
    Unknown options = False (the check stops and asks)."""
    opts = [o for o in (options or []) if norm(o) and not re.search(r'^(select|please select|--|choose)', norm(o))]
    if not opts:
        return False
    if CURRENT_Q.search(str(label or '')):
        cur = current_school_tokens()
        return not any(re.search(r'\b' + re.escape(t) + r'\b', norm(o)) for o in opts for t in cur)
    return not any(check('school', o, tenant)[0] for o in opts)


def audit(records, tenant=None, warn=None):
    """records: [{"label","value"[,"type","required"]}] read from the live page/QA record. Returns hard mismatches.
    JSA-186 (newer runners read the page, not a plan): `type` textarea / file / date is skipped; a "Section (entry): Field" label is
    classified by the field; a checkbox value "True"/"False" — not ticked claims nothing, ticked claims the label's own
    category (or Yes for a yes/no question); a "…without sponsorship…" question is judged with the answer flipped; an empty
    value on a field marked required=False goes to `warn` (a list) instead of the hard list."""
    out = []
    named = other_school_entries(records, tenant)
    for rec in records or []:
        label, value = rec.get('label') or '', rec.get('value')
        value = '' if value is None else value
        if isinstance(value, bool):
            value = 'True' if value else 'False'
        if isinstance(value, list):
            value = ' | '.join(str(x) for x in value)
        value = str(value)
        if str(rec.get('type') or '').lower() in SKIP_TYPES:
            continue
        key = classify(question_of(label))
        if not key:
            continue
        if key == 'degree_level' and DEGREE_STATE_Q.search(question_of(label)) and norm(value) in ('yes', 'no', 'in progress', 'in-progress'):
            continue                              # "Degree Achieved: In Progress / Yes" is whether it is finished, not a level (an employer 11-10, JSA-295)
        b = BOOL.get(norm(value))
        if b is not None:
            if yes_no_key(key):
                value = 'Yes' if b else 'No'
            elif not b:
                continue                          # an unticked category box claims nothing
            else:
                value = question_of(label)        # a ticked category box claims its own label
        if key == 'education_field' and second_major_q(label) and second_major_left_empty(
                value, ((jsa_profile.load().get('answers') or {}).get('secondary_major') or {}).get('text')):
            continue                              # no second major / minor on file: empty is his answer, not a missing major (JSA-293)
        if key == 'school' and re.match(r'^other\b', norm(value)) and (entry_of(label) in named or other_is_only_pick(rec.get('options'), tenant, question_of(label))):
            continue                              # School = "Other" with his school's name typed in the row's "If other" box (JSA-295),
                                                  # or a list that offers neither of his schools (a Greenhouse employer 10-31, JSA-321)
        if not norm(value) and rec.get('required') is False:
            if warn is not None:
                warn.append({'key': key, 'label': str(label)[:120], 'value': '', 'reason': 'empty (optional field)'})
            continue
        # "…without sponsorship…" = the sponsorship answer flipped (decisions-log 2026-11-05; Xaira, Marshall Wace 10-31)
        ok, why = judge(key, label, value, tenant)
        key = inverted_key(key, label)[0]
        if not ok:
            out.append({'key': key, 'label': str(label)[:120], 'value': str(value)[:120],
                        'want': SPEC['fields'][key].get('want'), 'reason': why,
                        'evidence': SPEC['fields'][key].get('evidence', '')})
    # JSA-281: the critical questions checked against the facts in config/profile.json (conviction, any-employer
    # authorization, degree level, major, start date, the user's own saved answer) — whatever wrote the value
    import fact_gate
    out += fact_gate.audit(records, jsa_profile.load(), learned(tenant))
    seen, uniq = set(), []                                     # the page probe and the plan may give the same field twice
    for m in out:
        k = (m['key'], m['label'][:60], norm(m['value']))
        if k not in seen:
            seen.add(k); uniq.append(m)
    return uniq


def tenant_of(url):
    m = re.match(r'https?://([^/]+)', url or '')
    return m.group(1).lower() if m else ''


def probe_src():
    return open(os.path.join(HERE, 'canon_probe.js'), encoding='utf-8').read()


def block(reasons):
    """Gate lines for run.py / run_wd.py problems."""
    return ['canonical mismatch: %s = %r (want %s; %s)' % (m['key'], m['value'], m['want'], m['reason']) for m in reasons]


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--learn' in args:
        i = args.index('--learn')
        tenant, key, value = args[i + 1], args[i + 2], args[i + 3]
        learn(tenant, key, value)
        print('learned for %s: %s = %r' % (tenant, key, value))
    elif '--check-file' in args:
        recs = json.load(open(args[args.index('--check-file') + 1], encoding='utf-8'))
        tenant = args[args.index('--tenant') + 1] if '--tenant' in args else None
        print(json.dumps(audit(recs, tenant), indent=1, ensure_ascii=False))
    else:
        print(__doc__)