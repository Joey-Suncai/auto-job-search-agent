#!/usr/bin/env python3
"""Workday career-site search (2026-11-01, Joey's full refresh): new internships straight from the companies' Workday sites.

Every Workday tenant already linked from data/store/jobs.jsonl is searched through its public CXS API
(POST https://<host>/wday/cxs/<tenant>/<site>/jobs, the same API prep_wd.py reads a single job from — no login, no browser).
Kept: internship titles for summer / 2027 in the U.S. (keep_posting); dropped: rows already in the store (by Workday job id),
companies with a tier A/B role (never used for tests). New rows are appended to the store with `added` = today,
`source` = workday_search, tier C (Joey's tracks) or D (other fields); the 08:45 gate (or `run_daily.py gate`) then reads
each JD and decides 可投 / 待核实 / 不可投.
usage: python3 wd_search.py [--write] [--limit-tenants N]      (without --write: print counts only)
Tests (rule 13): scripts/test_wd_search.py with DeepSeek cases.
"""
import json, os, re, sys, time, urllib.request, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36',
      'Content-Type': 'application/json', 'Accept': 'application/json'}
from us_location import is_non_us  # noqa: E402  (JSA-084: one shared non-U.S. rule for the Workday and Lever / Ashby searches)


def parse_tenant(url):
    """Pure (tested). Workday job / site URL → (host, tenant, site) or None.
    https://cbrands.wd5.myworkdayjobs.com/en-US/CBI_External_Careers/job/... → ('cbrands.wd5.myworkdayjobs.com', 'cbrands', 'CBI_External_Careers')
    https://wd3.myworkdaysite.com/recruiting/brevanhoward/BH_ExternalCareers/job/... → ('wd3.myworkdaysite.com', 'brevanhoward', 'BH_ExternalCareers')"""
    u = urlsplit(url or '')
    host = (u.hostname or '').lower()
    parts = [p for p in (u.path or '').split('/') if p]
    if host.endswith('.myworkdayjobs.com'):
        tenant = host.split('.')[0]
        parts = [p for p in parts if not re.fullmatch(r'[a-z]{2}-[A-Z]{2}', p)]
        if parts and parts[0] not in ('wday', 'job'):
            return host, tenant, parts[0]
        return None
    if host.endswith('myworkdaysite.com'):
        parts = [p for p in parts if not re.fullmatch(r'[a-z]{2}-[A-Z]{2}', p)]   # JSA-300: an optional locale first
    if host.endswith('myworkdaysite.com') and len(parts) >= 3 and parts[0] == 'recruiting':
        return host, parts[1].lower(), parts[2]
    return None


def job_url(host, tenant, site, path):
    """Pure (tested). The public page of one posting from the CXS search (externalPath "/job/<loc>/<slug>_<id>"):
    https://<tenant>.wdN.myworkdayjobs.com/en-US/<site><path>; on the shared host wdN.myworkdaysite.com the tenant is part of
    the path — https://wdN.myworkdaysite.com/recruiting/<tenant>/<site><path> (no locale, the form the store's links use;
    without the tenant the page answers 500; JSA-300)."""
    path = '/' + str(path or '').lstrip('/')
    if str(host or '').lower().endswith('myworkdaysite.com'):
        return f'https://{host}/recruiting/{tenant}/{site}{path}'
    return f'https://{host}/en-US/{site}{path}'


def keep_posting(title, location):
    """Pure (tested). An internship he could do in Summer 2027 in the U.S.?
    Title must say intern / internship (not "internal"); no fall / spring / winter / co-op / year-round / part-time term;
    an explicit year other than 2027 in the title → no; location must not be clearly outside the U.S. ("Remote" is fine)."""
    t, loc = str(title or ''), str(location or '')
    if not re.search(r'\bintern(ship)?s?\b', t, re.I):
        return False
    if re.search(r'\b(fall|autumn|spring|winter|co-?op|year[- ]round|part[- ]time)\b', t, re.I):
        return False
    years = set(re.findall(r'\b(20\d\d)\b', t))
    if years and years != {'2027'}:
        return False
    if is_non_us(loc):
        return False
    return True


def job_key(external_path):
    """Pure (tested). The Workday job id at the end of a posting path ("…/Data-Intern_R-12345" → "r-12345")."""
    m = re.search(r'_([A-Za-z0-9-]+)$', str(external_path or '').rstrip('/'))
    return m.group(1).lower() if m else ''


def search(host, tenant, site, text='intern', page=20, max_pages=5):
    out = []
    for i in range(max_pages):
        body = json.dumps({'appliedFacets': {}, 'limit': page, 'offset': i * page, 'searchText': text}).encode()
        req = urllib.request.Request(f'https://{host}/wday/cxs/{tenant}/{site}/jobs', data=body, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode('utf-8', 'replace'))
        except Exception:
            break
        posts = d.get('jobPostings') or []
        out += posts
        if len(posts) < page:
            break
        time.sleep(0.3)
    return out


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    rows = store.load('jobs')
    keys, tenants, ab, comp = set(), {}, set(), {}
    for r in rows:
        for u in (r.get('ats_url'), r.get('url')):
            t = parse_tenant(u or '')
            if t:
                tenants.setdefault(t, r.get('company') or '')
                k = job_key(u.split('?')[0])
                if k: keys.add(k)
        if r.get('tier') in ('A', 'B') or r.get('tier_orig') in ('A', 'B'):
            ab.add((r.get('company') or '').lower())
    items = list(tenants.items())
    if '--limit-tenants' in a: items = items[:int(a[a.index('--limit-tenants') + 1])]
    print(f'{len(items)} Workday tenants')
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda it: (it, search(*it[0])), items))
    new, seen, percomp = [], set(), {}
    TRK = re.compile(r'\b(data|analy|analytics|ai\b|a\.i\.|machine learning|ml\b|product|business intelligence|bi\b|insight|quant|statist)', re.I)
    for ((host, tenant, site), company), posts in res:
        if company.lower() in ab:
            continue
        for p in sorted(posts, key=lambda p: 0 if TRK.search(p.get('title', '')) else 1):
            title, loc, path = p.get('title', ''), p.get('locationsText', ''), p.get('externalPath', '')
            k = job_key(path)
            if not k or k in keys or k in seen or not keep_posting(title, loc):
                continue
            if percomp.get(company, 0) >= 2:                 # at most 2 per company, like cert_supply (Ryan lists a dozen engineering interns)
                continue
            # Joey's tracks first: C before D within a company
            seen.add(k); percomp[company] = percomp.get(company, 0) + 1
            new.append({'company': company, 'title': title, 'location': loc,
                        'url': job_url(host, tenant, site, path), 'posted': p.get('postedOn', ''),
                        'tier': 'C' if TRK.search(title) else 'D'})
    print(f'{sum(len(p) for _, p in res)} postings read · {len(new)} new internships kept '
          f'(C {sum(1 for n in new if n["tier"] == "C")}, D {sum(1 for n in new if n["tier"] == "D")})')
    if '--write' not in a:
        for n in new[:40]: print(' ', n['tier'], n['company'][:26], '|', n['title'][:60], '|', n['location'][:30])
        return
    nums = [int(re.sub(r'\D', '', r['id']) or 0) for r in rows if str(r.get('id', '')).startswith('J')]
    nid = max(nums) + 1
    today = dt.date.today().isoformat()
    for n in new:
        rows.append({'id': f'J{nid:05d}', 'company': n['company'], 'title': n['title'], 'location': n['location'],
                     'url': n['url'], 'ats_url': n['url'], 'tier': n['tier'], 'score': 45 if n['tier'] == 'C' else 35,   # store median of the tier (no pipeline score yet)
                     'score_note': 'workday_search default (tier median)', 'level': 'Internship', 'added': today,
                     'source': 'workday_search', 'posted': n['posted'],
                     'track': 'Data Sci / Analytics' if n['tier'] == 'C' else 'Other'})
        nid += 1
    store.save('jobs', rows)
    print(f'appended {len(new)} rows to data/store/jobs.jsonl (run the gate next)')


if __name__ == '__main__':
    main(sys.argv[1:])
