#!/usr/bin/env python3
"""Company → ATS hints from the public ats-scrapers inventory (JSA-069, 2026-11-03; Joey: 「可以用名单。」).

Data: references/ats_inventory/*.csv, a copy of kalil0321/ats-scrapers `ats-companies/` (MIT, LICENSE + SOURCE.md
there). Columns name,slug,url (phenom.csv: url,name,…). Each url goes through resolve_careers.detect_ats, so a hit
is (system, ident) in the same form the rest of the pipeline uses; rows whose url names no system detect_ats knows are
kept only for phenom / successfactors (ident = the career site's host).

A hit is a hint, never an answer: the caller confirms it on the system's live listing before using it (resolve_careers
per_company), and every ats_url is still read before --apply. One loader for resolve_careers.py and ats_search.py.

    python3 ats_inventory.py "Two Sigma"      # print the hints for a name
"""
import csv, glob, os, re, sys, threading, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, '..', 'references', 'ats_inventory')
FILE_SYSTEM = {'phenom': 'phenom', 'successfactors': 'successfactors'}     # custom-domain career sites
NOT_A_NAME = {'apply', 'careers', 'career', 'jobs', 'job', 'join', 'work', 'home', 'recruiting', 'talent', 'hiring'}
_index, _lock = None, threading.Lock()


def keys(name):
    """Name → match keys: the distinctive words squashed ('Ingredion Incorporated' → 'ingredion') and the company key
    squashed ('Two Sigma' → 'twosigma'). Keys under 3 characters and bare words like 'Apply' / 'Careers' give none."""
    import resolve_careers as RC
    out = []
    for k in (''.join(RC.company_words(name)), re.sub(r'[^a-z0-9]', '', RC.RB.company_key(name or ''))):
        if len(k) >= 3 and k not in NOT_A_NAME and k not in out:
            out.append(k)
    return out


def hint_of(fname, name, url):
    """One inventory row → (system, ident) or None. Pure (tested)."""
    import resolve_careers as RC
    found = RC.detect_ats(url or '')
    if found:
        return found[0]
    sysname = FILE_SYSTEM.get(fname)
    host = (urllib.parse.urlsplit(url or '').hostname or '').lower()
    if sysname and host and (name or '').strip().lower() not in NOT_A_NAME:
        return sysname, host
    return None


def rows(path):
    """(name, url) of one CSV; phenom.csv has the url first, keka.csv has only name,url."""
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        for r in csv.reader(f):
            if not r or r[0] in ('name', 'url'):
                continue
            if r[0].startswith('http'):
                yield (r[1] if len(r) > 1 else ''), r[0]
            elif len(r) == 2 and r[1].startswith('http'):          # keka.csv: name,url (JSA-137)
                yield r[0], r[1]
            elif len(r) >= 3:
                yield r[0], r[2]


def index(directory=DIR):
    """{key: [(system, ident)]} over every CSV (loaded once)."""
    global _index
    with _lock:
        if _index is not None and directory == DIR:
            return _index
        idx = {}
        for p in sorted(glob.glob(os.path.join(directory, '*.csv'))):
            fname = os.path.basename(p)[:-4]
            for name, url in rows(p):
                h = hint_of(fname, name, url)
                if not h:
                    continue
                for k in keys(name):
                    lst = idx.setdefault(k, [])
                    if h not in lst:
                        lst.append(h)
        if directory == DIR:
            _index = idx
        return idx


def lookup(company, directory=DIR):
    """Company → [(system, ident)] hints, no duplicates; [] when the inventory does not name it."""
    out = []
    idx = index(directory)
    for k in keys(company):
        for h in idx.get(k, []):
            if h not in out:
                out.append(h)
    return out


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    for c in sys.argv[1:]:
        print(c, '→', lookup(c))
