#!/usr/bin/env python3
"""USAJOBS (U.S. federal government) as a weekly source (2026-11-03; after ats-scrapers usajobs.py, MIT).

Official API: GET https://data.usajobs.gov/api/Search with the headers `Authorization-Key: <key>`, `User-Agent: <the
e-mail the key was issued to>`, `Host: data.usajobs.gov`. The key is free (developer.usajobs.gov) and is read from the
environment (`USAJOBS_API_KEY`, `USAJOBS_USER_AGENT`) or, on Joey's Mac, the Keychain item `jobagent-usajobs` (the user
agent then = config/profile.json accounts.gmail). No key → the run says so and does nothing (the weekly refresh goes on).
Plain HTTP, no browser.

Searches: each track keyword × the hiring paths for students and recent graduates (`HiringPath=student;graduates`),
first 250 results each. Kept: his tracks (indeed_search TRK), not senior (indeed_search SENIOR, plus GS-12 and above),
open now. Most federal postings are for U.S. citizens only — they are KEPT here; the eligibility gate rules them out
for a candidate who is not a citizen (config eligibility, JSA-081), so the same source serves an open-source user who is.
Dropped: rows already in the store (same USAJOBS position id, or same normalised org + title), at most 2 per agency.
New rows: `source` = usajobs_search, `url` = the usajobs.gov position page; the gate reads the posting through the API.
Runs only for a citizen / permanent-resident profile (`runs_for`; `--force` overrides).
usage: python3 usajobs_search.py [--write] [--force] [--json <saved API response .json> …]   (without --write: counts only)
Tests (rule 13): scripts/test_usajobs.py with DeepSeek cases.
"""
import datetime as dt, json, os, re, subprocess, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
from indeed_search import norm, title_key, TRK, SENIOR  # noqa: E402

API = 'https://data.usajobs.gov/api/Search'
QUERIES = ['data analyst', 'data scientist', 'data engineer', 'statistician', 'operations research', 'program analyst',
           'management analyst', 'product manager', 'artificial intelligence', 'economist', 'information technology']
GS_SENIOR = re.compile(r'\bGS-?(1[2-5])\b', re.I)


def runs_for(eligibility):
    """Pure (tested). Should the weekly refresh search USAJOBS for this candidate? Only when `citizen_or_pr` is true
    (almost every federal posting is for U.S. citizens; a candidate who is not one would only get rows the gate rules
    out — Joey 2026-11-03 「同意」). Missing / not a dict / anything but True → False."""
    return isinstance(eligibility, dict) and eligibility.get('citizen_or_pr') is True


def creds():
    """(key, user agent) from the environment, else the Keychain item jobagent-usajobs + the profile e-mail; (None, None)."""
    k, ua = os.environ.get('USAJOBS_API_KEY', '').strip(), os.environ.get('USAJOBS_USER_AGENT', '').strip()
    if not k:
        try:
            k = subprocess.run(['security', 'find-generic-password', '-s', 'jobagent-usajobs', '-w'], capture_output=True,
                               text=True, timeout=10).stdout.strip()
        except Exception:
            k = ''
    if k and not ua:
        try:
            ua = (json.load(open(os.path.join(ROOT, 'config', 'profile.json'))).get('accounts') or {}).get('gmail') or ''
        except (OSError, ValueError):
            ua = ''
    return (k, ua) if k and ua else (None, None)


def items(payload):
    """Pure (tested). An API response → [{'id', 'title', 'org', 'location', 'url', 'posted', 'closes', 'who', 'grade'}]:
    SearchResult.SearchResultItems[].MatchedObjectDescriptor with PositionID, PositionTitle, OrganizationName (else
    DepartmentName), PositionLocationDisplay (else the PositionLocation names "; "-joined), PositionURI, the dates
    PublicationStartDate / ApplicationCloseDate cut to YYYY-MM-DD, UserArea.Details.WhoMayApply.Name (else ''),
    grade = "GS-<LowGrade>" when JobGrade[0].Code is "GS" — JobGrade at the descriptor's top level or in
    UserArea.Details, LowGrade in UserArea.Details or in that JobGrade entry (else ''). Items without an id, title or
    url are skipped."""
    out = []
    res = (payload or {}).get('SearchResult') or {}
    for it in res.get('SearchResultItems') or []:
        d = (it or {}).get('MatchedObjectDescriptor') or {}
        pid, title, url = str(d.get('PositionID') or '').strip(), (d.get('PositionTitle') or '').strip(), d.get('PositionURI')
        if not pid or not title or not url:
            continue
        loc = d.get('PositionLocationDisplay') or '; '.join(l.get('LocationName') for l in d.get('PositionLocation') or []
                                                            if isinstance(l, dict) and l.get('LocationName'))
        det = ((d.get('UserArea') or {}).get('Details') or {}) if isinstance(d.get('UserArea'), dict) else {}
        who = (det.get('WhoMayApply') or {}).get('Name') if isinstance(det.get('WhoMayApply'), dict) else ''
        jgs = d.get('JobGrade') if isinstance(d.get('JobGrade'), list) and d.get('JobGrade') else det.get('JobGrade')   # top level or in Details
        jg = jgs[0] if isinstance(jgs, list) and jgs and isinstance(jgs[0], dict) else {}
        low = det.get('LowGrade') or jg.get('LowGrade')
        grade = f"GS-{low}" if jg.get('Code') == 'GS' and low else ''
        out.append({'id': pid, 'title': title, 'org': d.get('OrganizationName') or d.get('DepartmentName') or '',
                    'location': loc or '', 'url': url, 'posted': str(d.get('PublicationStartDate') or '')[:10],
                    'closes': str(d.get('ApplicationCloseDate') or '')[:10], 'who': who or '', 'grade': grade})
    return out


def keep(item, today):
    """Pure (tested). His tracks (TRK on the title), not senior (SENIOR on the title, or grade GS-12 … GS-15), and not
    closed (closes empty or on / after `today`, ISO dates compared as text)."""
    t = item.get('title') or ''
    if not TRK.search(t) or SENIOR.search(t) or GS_SENIOR.search(item.get('grade') or ''):
        return False
    return not item.get('closes') or item['closes'] >= today


def known(rows):
    """Pure (tested). Store rows → (USAJOBS position ids, {(norm org/company, title_key)})."""
    ids, pairs = set(), set()
    for r in rows:
        for u in (r.get('url'), r.get('ats_url')):
            m = re.search(r'usajobs\.gov(?::443)?/(?:job|GetJob/ViewDetails)/(\d+)', str(u or ''), re.I)
            if m:
                ids.add(m.group(1))
        pairs.add((norm(r.get('company')), title_key(r.get('title'))))
    return ids, pairs


def pick_new(found, ids, pairs, today):
    """Pure (tested). Kept items not in the store and not repeated, at most 2 per organisation, in order."""
    ids, pairs, per, new = set(ids), set(pairs), {}, []
    for it in found:
        p = (norm(it['org']), title_key(it['title']))
        m = re.search(r'/(\d+)/?$', it['url'])
        pid = m.group(1) if m else it['id']
        if pid in ids or p in pairs or not keep(it, today) or per.get(p[0], 0) >= 2:
            continue
        per[p[0]] = per.get(p[0], 0) + 1; ids.add(pid); pairs.add(p)
        new.append(it)
    return new


def to_rows(new, rows, today):
    nid = max([int(re.sub(r'\D', '', r['id']) or 0) for r in rows if str(r.get('id', '')).startswith('J')] or [0]) + 1
    out = []
    for n in new:
        out.append({'id': f'J{nid:05d}', 'company': n['org'], 'title': n['title'], 'location': n['location'], 'url': n['url'],
                    'tier': 'C', 'score': 45, 'score_note': 'usajobs_search default (tier median)', 'level': 'New Grad / Entry'
                    if re.search(r'recent graduate', n['title'], re.I) else 'Internship' if re.search(r'\b(intern(ship)?|student trainee|student)\b', n['title'], re.I)
                    else 'New Grad / Entry',
                    'added': today, 'source': 'usajobs_search', 'posted': n['posted'], 'usajobs_who': n['who']})
        nid += 1
    return out


def search(key, ua, q):
    url = API + '?' + urllib.parse.urlencode({'Keyword': q, 'HiringPath': 'student;graduates', 'ResultsPerPage': 250, 'Page': 1})
    req = urllib.request.Request(url, headers={'Authorization-Key': key, 'User-Agent': ua, 'Host': 'data.usajobs.gov'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    rows = store.load('jobs')
    today = dt.date.today().isoformat()
    if '--json' in a:
        payloads = [json.load(open(f)) for f in a[a.index('--json') + 1:] if not f.startswith('--')]
        note = 'saved responses'
    else:
        try:
            elig = json.load(open(os.path.join(ROOT, 'config', 'profile.json'))).get('eligibility')
        except (OSError, ValueError):
            elig = None
        if not runs_for(elig) and '--force' not in a:
            print('usajobs: skipped — the profile is not a U.S. citizen / permanent resident (federal postings are citizens-only); --force runs it anyway'); return
        key, ua = creds()
        if not key:
            print('usajobs: no API key (USAJOBS_API_KEY / Keychain jobagent-usajobs) — skipped'); return
        payloads, note = [], ''
        for q in QUERIES:
            try:
                payloads.append(search(key, ua, q))
            except Exception as e:
                note = f'stopped at "{q}": {type(e).__name__} {str(e)[:80]}'; break
            time.sleep(1.5)
    found = [i for p in payloads for i in items(p)]
    ids, pairs = known(rows)
    new = to_rows(pick_new(found, ids, pairs, today), rows, today)
    print(f'{len(payloads)} searches · {len(found)} postings · {sum(1 for i in found if keep(i, today))} kept · {len(new)} new'
          + (f' · {note}' if note else ''))
    if '--write' not in a:
        for n in new:
            print(' ', n['level'][:8], n['company'][:28], '|', n['title'][:55], '|', n['usajobs_who'][:30])
        return
    store.save('jobs', rows + new)
    print(f'appended {len(new)} rows to data/store/jobs.jsonl (run the gate next)')


if __name__ == '__main__':
    main(sys.argv[1:])
