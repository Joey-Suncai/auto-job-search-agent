#!/usr/bin/env python3
"""Personal-data and secret scan for the public export (JSA-078, ADR-0005). Read-only.

Terms come from the PRIVATE config/ (the real values to keep out): e-mails, phone in any common format, street address,
legal first name, profile handles, the home folder path, every name in config/connections.json — plus generic secret
patterns (API keys, private keys, SEVIS / A-numbers). Allowed: the copyright line in LICENSE.
usage: python3 scripts/public/scan.py <dir>          exit 1 when anything is found
Tests (rule 13): scripts/test_export_public.py with DeepSeek cases.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SECRETS = [('anthropic key', r'sk-ant-[A-Za-z0-9_-]{20,}'), ('api key', r'\bsk-[A-Za-z0-9]{32,}'),
           ('private key', r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), ('github token', r'\bgh[pousr]_[A-Za-z0-9]{30,}'),
           ('SEVIS id', r'\bN00\d{8}\b'), ('A-number', r'\bA-?\d{8,9}\b(?=.{0,40}(alien|uscis|a-number))')]
ALLOW = {('LICENSE', 'legal first name'),   # "Copyright (c) 2026 Alex Rivera"
         ('README.md', 'website handle')}     # the public repo's own URL: github.com/example/auto-job-search-agent


def phone_re(phone):
    """Pure (tested). '555-010-2030' → a regex for 5550102030 / 555-010-2030 / (555) 010-2030 / +1 555.010.2030 …"""
    d = re.sub(r'\D', '', phone or '')[-10:]
    if len(d) < 10:
        return None
    return r'(?<!\d)(?:\+?1[\s.-]?)?\(?' + d[:3] + r'\)?[\s.-]?' + d[3:6] + r'[\s.-]?' + d[6:] + r'(?!\d)'


def terms_from(profile, connections=None, home=None):
    """Pure (tested). The private profile (+ connections, home path) → [(label, regex)] of values that must not ship."""
    t, c = [], profile.get('contact') or {}
    for e in {c.get('email'), (profile.get('accounts') or {}).get('gmail'), (profile.get('accounts') or {}).get('workday_email')} - {None, ''}:
        t.append(('e-mail', re.escape(e)))
        t.append(('e-mail user', r'\b' + re.escape(e.split('@')[0]) + r'\b'))
    if phone_re(c.get('phone')):
        t.append(('phone', phone_re(c.get('phone'))))
    street = ((profile.get('answers') or {}).get('address') or {}).get('text')
    if street:
        t.append(('street address', re.escape(street).replace(r'\ ', r'\s+')))
    first = (profile.get('name') or {}).get('first')
    if first and len(first) >= 4:
        t.append(('legal first name', r'\b' + re.escape(first) + r'\b'))
    for k in ('linkedin', 'website'):
        h = (c.get(k) or '').rstrip('/').split('/')[-1]
        if len(h) >= 4:
            t.append((k + ' handle', r'\b' + re.escape(h) + r'\b'))
    ans = profile.get('answers') or {}
    z = (ans.get('zip') or {}).get('text')
    if z and len(z) >= 5:
        t.append(('zip code', r'(?<!\d)' + re.escape(z) + r'(?!\d)'))
    g = (ans.get('gpa') or {}).get('text')
    if g and re.match(r'^\d\.\d{2}$', g):
        t.append(('GPA', r'(?<![\d.])' + re.escape(g) + r'(?![\d])'))
    for k in ('gender', 'race'):                         # the candidate's own EEO answer stated next to the topic
        v = (ans.get(k) or {}).get('text')
        if v and not re.search(r"wish|decline|prefer not", v, re.I):
            t.append((f'EEO answer ({k})', r'\b' + k + r'\b[^\n]{0,12}(?-i:\b' + re.escape(v) + r'\b)'))   # as written (capitalised): "male or female" in a label regex is no answer
    cz = (profile.get('work_auth') or {}).get('citizenship')
    if cz:
        t.append(('citizenship', r'citizenship[^\n]{0,25}\b' + re.escape(cz) + r'\b'))
    if home:
        t.append(('home folder', re.escape(home.rstrip('/')) + r'\b'))
    for people in ((connections or {}).get('connections') or {}).values():
        for p in people:
            if p and p[0]:
                t.append(('connection name', r'\b' + re.escape(p[0]) + r'\b'))
    for line in ((connections or {}).get('alumni_link') or {}).values():
        m = re.match(r'([A-Z][\w.-]+(?: [A-Z][\w.-]+){1,3})', line)
        if m:
            t.append(('connection name', r'\b' + re.escape(m.group(1)) + r'\b'))
    return t + SECRETS


def find_hits(rel, text, terms, allow=ALLOW):
    """Pure (tested). Text of one file → ['path:line: label: match'] for every term found (case-insensitive)."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for label, rx in terms:
            if (rel, label) in allow:
                continue
            m = re.search(rx, line, re.I)
            if m:
                out.append(f'{rel}:{n}: {label}: {m.group(0)[:60]}')
    return out


def load_terms():
    j = lambda n: json.load(open(os.path.join(ROOT, 'config', n), encoding='utf-8')) if os.path.exists(os.path.join(ROOT, 'config', n)) else {}
    prof = j('profile.json')
    if not prof:
        raise SystemExit('scan: config/profile.json (the private values to look for) is missing')
    return terms_from(prof, j('connections.json'), os.path.expanduser('~'))


def scan_tree(d, terms=None):
    terms = terms or load_terms()
    hits = []
    for base, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in ('.git', 'node_modules')]
        for f in files:
            p = os.path.join(base, f); rel = os.path.relpath(p, d)
            try:
                text = open(p, encoding='utf-8').read()
            except (UnicodeDecodeError, OSError):
                if not open(p, 'rb').read(5) == b'%PDF-' or os.path.getsize(p) > 1024:   # tiny dummy test PDFs are fine
                    hits.append(f'{rel}: binary file (not allowed in the export)')
                continue
            hits += find_hits(rel, text, terms)
    return hits


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    h = scan_tree(sys.argv[1])
    for x in h:
        print(x)
    print(f'{len(h)} hit(s)')
    sys.exit(1 if h else 0)
