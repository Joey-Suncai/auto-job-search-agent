#!/usr/bin/env python3
"""JSA-359: the product repo never holds the user's own facts (ADR-0011 — facts live in the data home).

Fails when a file that looks like a real personal-fact file is tracked or sits untracked-but-not-ignored in this repo:
  * by NAME   — profile / canonical / wd_profile / facts / connections (.json) or a data-home folder (facts/, resume/,
                applications/, data/, 资料/ …) — unless it is a fictional twin (`*.example.*`) or under config/fixtures/;
  * by SHAPE  — any other .json whose top-level keys look like a profile / canonical / wd_profile (the file may be renamed).
The test never contains real facts: shapes are key names only, the cases below are made up.
    python3 scripts/test_no_personal_facts.py
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACT_NAMES = {'profile', 'canonical', 'wd_profile', 'facts', 'connections'}
DATA_DIRS = {'facts', 'resume', 'applications', 'data', 'logs', '资料'}
SHAPES = [  # (label, keys that must all/at least n appear at the top level)
    ('profile', {'name', 'contact', 'accounts', 'education', 'employers', 'work_auth', 'answers', 'transcript'}, 4),
    ('canonical', {'version', 'order', 'fields'}, 3),
    ('wd_profile', {'work', 'education', 'languages'}, 3),
    ('facts', {'candidate', 'entries', 'facts', 'confirmed_by'}, 3),
]


def fictional_ok(path):
    p = path.replace(os.sep, '/')
    return '/fixtures/' in '/' + p or '.example.' in os.path.basename(p)


def by_name(path):
    """Pure. True when the path is a personal-fact file by its name or folder and is not a fictional twin."""
    p = path.replace(os.sep, '/')
    if fictional_ok(p): return False
    parts = p.split('/')
    if parts[0].lower() in DATA_DIRS and len(parts) > 1: return True
    base = os.path.basename(p).lower()
    stem, ext = os.path.splitext(base)
    return ext == '.json' and stem in FACT_NAMES


def by_shape(obj):
    """Pure. The label of the personal-fact shape a parsed JSON has at the top level, else None."""
    if not isinstance(obj, dict): return None
    keys = set(obj)
    for label, want, n in SHAPES:
        if len(keys & want) >= n: return label
    return None


def offenders(root=ROOT):
    files = subprocess.run(['git', '-C', root, 'ls-files', '-co', '--exclude-standard'], capture_output=True, text=True).stdout.split('\n')
    bad = []
    for f in filter(None, files):
        if by_name(f): bad.append((f, 'name')); continue
        if f.endswith('.json') and not fictional_ok(f):
            try: obj = json.load(open(os.path.join(root, f)))
            except Exception: continue
            lab = by_shape(obj)
            if lab: bad.append((f, 'shape:' + lab))
    return bad


def _addressy(t):
    """Pure. An address-like value: 10+ chars, 2+ words and a street number / ZIP-like digit run (3+ digits) — not a date, a regex, a note with CJK quotes."""
    return (len(t) >= 10 and len(t.split()) >= 2 and re.search(r'\d{3,}|^\d', t) and not re.fullmatch(r'[\d\s:/.\-+]+', t)
            and not t.startswith('/') and not re.search(r'\d{4}-\d{2}-\d{2}|[\u3000-\u9fff\uff00-\uffef]', t))


def identifying_values(profile):
    """Pure (tested with a made-up profile). The values of a profile that identify the person, as (label, value): from `name`, `contact` and `accounts`
    only — e-mail addresses, phone numbers (10+ digits), address-like values (a digit and 2+ words) and the full name. Saved answers and the rest
    of the profile are not scanned (too many ordinary words). Reported by LABEL only — a value is never printed."""
    out = []
    def walk(v, key=''):
        if isinstance(v, dict):
            for k, x in v.items(): walk(x, k)
        elif isinstance(v, list):
            for x in v: walk(x, key)
        elif isinstance(v, str):
            t = v.strip()
            if re.fullmatch(r'[\w.+-]+@[\w-]+\.[\w.-]+', t): out.append(('email', t))
            elif len(re.sub(r'\D', '', t)) >= 10 and len(t) <= 20: out.append(('phone', t))
            elif _addressy(t): out.append(('address', t))
            elif key in ('full', 'signature', 'file_prefix') and (len(t.split()) >= 2 or '_' in t): out.append(('name', t))
            elif key in ('linkedin', 'website') and '/' in t: out.append(('handle', t))
    for k in ('name', 'contact', 'accounts'):
        if isinstance(profile, dict) and k in profile: walk(profile[k])
    if isinstance(profile, dict):      # fragments that name the person / home: an unusual first name (6+ letters), the home town of the high school
        f = str((profile.get('name') or {}).get('first') or '').strip()
        if len(f) >= 6 and f.isalpha(): out.append(('name', f))
        c = str((profile.get('high_school') or {}).get('city') or '').strip()
        if len(c) >= 6 and c.isalpha(): out.append(('place', c))
    for k, v in ((profile or {}).get('answers') or {}).items() if isinstance(profile, dict) and isinstance(profile.get('answers'), dict) else []:
        if re.search(r'address|street|zip|postal|phone|email|pronunc', str(k), re.I): walk(v, k)      # the street address lives in answers.address
    return sorted(set(out))


def value_hits(root, values):
    """Files of the repo (tracked or untracked-not-ignored, text, < 2 MB) that contain any identifying value; → [(file, label)] — never the value."""
    files = subprocess.run(['git', '-C', root, 'ls-files', '-co', '--exclude-standard'], capture_output=True, text=True).stdout.split('\n')
    hits = []
    for f in filter(None, files):
        fp = os.path.join(root, f)
        try:
            if os.path.getsize(fp) > 2_000_000: continue
            txt = open(fp, encoding='utf-8').read().lower()
        except (OSError, UnicodeDecodeError):
            continue
        for label, v in values:
            if v.lower() in txt: hits.append((f, label)); break
    return hits


FAKE_PROFILE = {'name': {'full': 'Zed Quill'}, 'contact': {'email': 'zed.quill@example.org', 'phone': '+1 555 010 0199'},
                'answers': {'address': {'text': '12 Maple Lane'}, 'first_name': {'text': 'Zed'}}, 'gpa': 3.91, 'x': {'when': '2026-11-17', 'note': 'a short note'}}
NOISE = ['/united states.*\\+ ?1\\b/i', 'United States of America (+1)', 'a note (Joey 2026-11-05: 「名字你直接问大模型即可」)', 'DeepSeek 2026-11-05 (kept)']   # ordinary answers are never identifying values (JSA-403)

CASES = [  # made-up paths / shapes only
    ('name', 'config/profile.json', True), ('name', 'config/profile.example.json', False),
    ('name', 'config/fixtures/f1_student/profile.json', False), ('name', 'config/wd_profile.json', True),
    ('name', 'facts/anything.md', True), ('name', 'resume/base.docx', True), ('name', 'applications/x/y.md', True),
    ('name', 'skills/auto-apply/scripts/profile.js', False), ('name', 'scripts/data/readme.md', False),
    ('name', 'config/facts.json', True), ('name', 'config/Profile.JSON', True), ('name', 'Resume/base.docx', True), ('name', 'docs/profile.json', True),
    ('shape', {'name': {}, 'contact': {}, 'education': [], 'employers': []}, 'profile'),
    ('shape', {'version': 1, 'order': [], 'fields': {}}, 'canonical'),
    ('shape', {'work': [], 'education': [], 'languages': []}, 'wd_profile'),
    ('shape', {'name': 'x', 'version': 2}, None), ('shape', [1, 2], None), ('shape', {'dependencies': {}}, None),
]


def main():
    bad = 0
    iv = identifying_values(FAKE_PROFILE)
    if sorted(set(l for l, _ in iv)) != ['address', 'email', 'name', 'phone']: bad += 1; print('FAIL identifying_values', [l for l, _ in iv])
    if any(_addressy(n) for n in NOISE): bad += 1; print('FAIL _addressy took an ordinary answer for an address')
    for kind, arg, want in CASES:
        got = by_name(arg) if kind == 'name' else by_shape(arg)
        if got != want: bad += 1; print('FAIL', kind, arg, 'got', got, 'want', want)
    print(f'{len(CASES) - bad}/{len(CASES)} cases ok')
    off = offenders()
    try:      # on a developer's machine the data home's real profile is there: no identifying value may sit in ANY file of the repo (JSA-400: a golden set held an address)
        sys.path.insert(0, os.path.join(ROOT, 'config')); import paths as jpaths
        # test_all.sh runs on a clone whose identity is already swapped for the fictional one (JSA-403) and exports JSA_REAL_HOME = the live data home
        real_home = os.environ.get('JSA_REAL_HOME')
        real = json.load(open(os.path.join(os.path.expanduser(real_home), 'config', 'profile.json') if real_home else jpaths.config('profile.json'), encoding='utf-8'))
        fk = {str(v).lower() for v in json.load(open(os.path.join(ROOT, 'config', 'fixtures', 'fake_identity.json'), encoding='utf-8')).values()}
        hits = value_hits(ROOT, [(l, v) for l, v in identifying_values(real) if v.lower() not in fk])      # the fictional identity itself is meant to be in the repo
        hits = [(f, l) for f, l in hits if not (f == 'LICENSE' and l == 'name')]       # the copyright holder's name in the licence's Required Notice is meant to be public
        for f, label in hits: print(f'REAL {label.upper()} of the user in the product repo: {f} — facts belong in the data home; the repo uses config/fixtures/fake_identity.json'); off.append((f, label))
        print(f'real-value scan: {len(identifying_values(real))} identifying values, {len(hits)} file(s) hit')
    except Exception as e:
        print(f'real-value scan skipped ({type(e).__name__}: no data home profile here)')
    for f, why in off: print('PERSONAL FACT FILE in the product repo:', f, f'({why}) — facts belong in the data home')
    return 1 if (bad or off) else 0


if __name__ == '__main__':
    sys.exit(main())
