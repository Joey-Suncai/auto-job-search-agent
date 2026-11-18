#!/usr/bin/env python3
"""JSA-403: the repo's one fictional identity (config/fixtures/fake_identity.json) and the swap of a real profile's identity onto it.

The product repo never holds the user's own facts, so every test / spec / case that needs a person uses the fictional values.
Those tests still want the user's REAL answers (the rules run on the data home's profile), so test_all.sh runs them on a clone of
the data home whose identity is swapped for the fictional one:  python3 scripts/fake_identity.py --home <clone>
The real values are read from the clone's own config/profile.json at run time and never written anywhere.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(os.path.dirname(HERE), 'config', 'fixtures', 'fake_identity.json')


def fake():
    """The fictional identity (dict of str)."""
    return json.load(open(FIXTURE, encoding='utf-8'))


def _phone_re(phone):
    d = re.sub(r'\D', '', phone)[-10:]
    return re.compile(r'(?<![\w.-])(\+?1[ .-]?)?\(?' + d[:3] + r'\)?[ .-]?' + d[3:6] + r'[ .-]?' + d[6:] + r'(?![\w-])')


def swap_rules(real, fk=None):
    """Pure. (compiled regex, replacement string) pairs, longest / most specific first, that turn a real profile's identity into the fictional one.
    `real` = the parsed real config/profile.json. Values the profile lacks are skipped."""
    fk = fk or fake()
    nm, ct, ans = real.get('name') or {}, real.get('contact') or {}, real.get('answers') or {}
    txt = lambda k: ((ans.get(k) or {}).get('text') or '').strip() if isinstance(ans.get(k), dict) else ''
    out = []
    def add(real_v, fake_v, flags=re.I):
        if real_v and len(real_v) >= 3: out.append((re.compile(re.escape(real_v), flags), fake_v))
    add(nm.get('signature'), fk['signature'], 0)
    add(txt('permanent_address'), fk['permanent_address'])
    add(txt('name_pronunciation'), f"{fk['pronunciation']} (I go by {fk['preferred']})", 0)
    pron = txt('name_pronunciation').split(' (')[0]
    add(pron, fk['pronunciation'])
    add(ct.get('website'), fk['website'])
    add(ct.get('linkedin'), fk['linkedin'])
    for k, f in (('email', 'email'), ('secondary_email', 'secondary_email')):
        add(ct.get(k), fk[f])
    for k in ('gmail', 'workday_email'): add((real.get('accounts') or {}).get(k), fk['email'])
    street = txt('address')
    if street:
        long = re.sub(r'\bS\b', 'South', street); long = re.sub(r'\bAve\b', 'Avenue', long); long = re.sub(r'\bSt\b', 'Street', long)
        add(long, fk['street_long']); add(street, fk['street'])
    csz = txt('city_state_zip')
    add(csz, fk['city_state_zip'])
    zp = txt('zip')
    add(zp, fk['zip'])
    add(f"{nm.get('preferred')} {nm.get('last')}", f"{fk['preferred']} {fk['last']}", 0)
    hs = real.get('high_school') or {}      # the home-country town (high school name / city)
    add(hs.get('city'), fk['hometown'])
    add(nm.get('file_prefix'), fk['file_prefix'])
    add(nm.get('full'), fk['full'])
    if ct.get('phone'): out.append((_phone_re(ct['phone']), lambda m, p=fk['phone']: _phone_like(m.group(0), p)))
    handle = (ct.get('linkedin') or '').rstrip('/').split('/')[-1]
    add(handle, fk['linkedin_handle'])
    gh = (ct.get('website') or '').rstrip('/').split('/')[-1]
    add(gh, fk['github_handle'])
    add(nm.get('first'), fk['first'], 0)
    add(nm.get('last') and f"\"{nm['last']}\"", f"\"{fk['last']}\"", 0)       # a quoted bare last name ("Sun")
    add(nm.get('preferred'), fk['preferred'], 0)
    return out


def _phone_like(shown, fake_phone):
    """The fake phone written the way `shown` wrote the real one (keeps the separators / +1 / parentheses)."""
    d = iter(re.sub(r'\D', '', fake_phone)[-10:])
    skip = max(0, len(re.sub(r'\D', '', shown)) - 10)      # a leading country-code 1 stays
    def one(m):
        nonlocal skip
        if skip: skip -= 1; return m.group(0)
        return next(d)
    return re.sub(r'\d', one, shown)


def apply(text, rules):
    for rx, rep in rules: text = rx.sub(rep, text)
    return text


def swap_home(home):
    """Rewrite the identity inside a (cloned) data home's config/ and facts/ text files. Returns the number of files changed."""
    live = open(os.path.expanduser('~/.config/job-search-agent/home')).read().strip() if os.path.exists(os.path.expanduser('~/.config/job-search-agent/home')) else ''
    if live and os.path.realpath(home) == os.path.realpath(os.path.expanduser(live)):
        raise SystemExit('fake_identity: refusing to rewrite the live data home — run it on a clone')
    prof = os.path.join(home, 'config', 'profile.json')
    if not os.path.exists(prof): raise SystemExit(f'fake_identity: no config/profile.json in {home}')
    real = json.load(open(prof, encoding='utf-8'))
    rules = swap_rules(real)
    n = 0
    for sub in ('config', 'facts'):
        d = os.path.join(home, sub)
        for root, _, files in os.walk(d):
            for f in files:
                if not f.endswith(('.json', '.md', '.txt', '.py', '.js')): continue
                p = os.path.join(root, f)
                try: s = open(p, encoding='utf-8').read()
                except (OSError, UnicodeDecodeError): continue
                t = apply(s, rules)
                if t != s: open(p, 'w', encoding='utf-8').write(t); n += 1
    prefix = (real.get('name') or {}).get('file_prefix')    # generated files carry the name too (<Name>_Resume_….docx)
    if prefix:
        for folder, dirs, files in os.walk(home, topdown=False):         # the whole clone, names only
            for nm in files + dirs:
                if prefix in nm: os.rename(os.path.join(folder, nm), os.path.join(folder, nm.replace(prefix, fake()['file_prefix']))); n += 1
    return n


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--home':
        print(f'fake identity: {swap_home(sys.argv[2])} file(s) of the test home swapped')
    else:
        print(__doc__); sys.exit(2)
