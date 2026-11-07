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
         python3 canon.py --learn <tenant> <key> <option text>   # accept a value Joey confirmed
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
    if any(re.search(p, v, re.I) for p in spec.get('accept', [])):
        bad = [p for p in spec.get('reject', []) if re.search(p, v, re.I)]
        if bad:
            return False, 'matched accept but also reject %r' % bad[0]
        return True, 'pattern'
    return False, 'no accept pattern matched (want %s)' % spec.get('want')


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
NOW_ONLY_RE = re.compile(r'\bfor (the duration of )?(this|the) (internship|position|role|job)\b|\bduration of (this|the|my) internship|\b(now|currently|at this time|today)\b', re.I)
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


def audit(records, tenant=None, warn=None):
    """records: [{"label","value"[,"type","required"]}] read from the live page/QA record. Returns hard mismatches.
    JSA-186 (newer runners read the page, not a plan): `type` textarea / file / date is skipped; a "Section (entry): Field" label is
    classified by the field; a checkbox value "True"/"False" — not ticked claims nothing, ticked claims the label's own
    category (or Yes for a yes/no question); a "…without sponsorship…" question is judged with the answer flipped; an empty
    value on a field marked required=False goes to `warn` (a list) instead of the hard list."""
    out = []
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
        b = BOOL.get(norm(value))
        if b is not None:
            if yes_no_key(key):
                value = 'Yes' if b else 'No'
            elif not b:
                continue                          # an unticked category box claims nothing
            else:
                value = question_of(label)        # a ticked category box claims its own label
        if not norm(value) and rec.get('required') is False:
            if warn is not None:
                warn.append({'key': key, 'label': str(label)[:120], 'value': '', 'reason': 'empty (optional field)'})
            continue
        q = norm(question_of(label))
        if key in ('sponsorship_future', 'sponsorship_now') and INVERT_RE.search(q):
            # "…without sponsorship…" = the sponsorship answer flipped: the NOW answer when the question covers only now /
            # this internship / this position, else the future one (decisions-log 2026-11-05; Xaira, Marshall Wace 10-31)
            if NOW_ONLY_RE.search(q) and not FUTURE_RE.search(q):
                key = 'sponsorship_now'
            ok, why = check(key, flip(value), tenant)
            why = why if ok else 'inverted question ("without sponsorship"): ' + why
        else:
            ok, why = check(key, value, tenant)
        if not ok:
            out.append({'key': key, 'label': str(label)[:120], 'value': str(value)[:120],
                        'want': SPEC['fields'][key].get('want'), 'reason': why,
                        'evidence': SPEC['fields'][key].get('evidence', '')})
    return out


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