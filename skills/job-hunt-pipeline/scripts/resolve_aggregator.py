#!/usr/bin/env python3
"""Aggregator link → the company's own posting (JSA-046, 2026-10-31).

1,270 rows in data/store/jobs.jsonl point at aggregators instead of the company form: zapply.jobs and go.vansh.nyc are
redirects (followed); jobright.ai hides the original link and answers scripts with a security check, so a jobright page
is **never fetched** — the row's own company + title are matched against the company's public Greenhouse / Lever /
Ashby board (resolve_builtin.py helpers) and its Workday site's public search (tenants seen on other rows). No match or
two equal matches = unresolved with the reason; never a guess.

Writes ats_url + ats_resolved (how) + ats_resolved_on (date), or ats_unresolved (why); never changes url, elig or any other field. The 08:45 gate
reads ats_url first (gate_run.py) and re-checks a row resolved since its last check, so the real JD is read and the same
posting listed twice becomes 重复. The 08:45 run (run_daily.py gate) resolves new aggregator rows first.

    python3 resolve_aggregator.py <url>                       # one link (redirects only; jobright needs the row)
    python3 resolve_aggregator.py --all [--retry] [--limit N] [--write]
Spec + DeepSeek-written cases: scripts/test_cases/resolve_aggregator_*; harness scripts/test_resolve_aggregator.py.
"""
import json, os, re, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
import resolve_builtin as RB  # noqa: E402  (similarity, best_match, company_key, known_boards, guesses, board_postings, clean)

WD_RX = re.compile(r'https://(([\w-]+)\.wd\d+\.myworkday(?:jobs|site)\.com)/(?:[a-z]{2}-[A-Z]{2}/)?(?:recruiting/[\w-]+/)?([\w-]+)/(?:job|details)/')


def kind(url):
    u = (url or '').lower()
    return 'zapply' if 'zapply.jobs' in u else 'vansh' if 'go.vansh.nyc' in u else 'jobright' if 'jobright.ai/jobs/info/' in u else None


def workday_tenants(jobs):
    """company key → [(host, tenant, site)] from every row whose url / ats_url is a Workday posting."""
    out = {}
    for j in jobs:
        for u in (j.get('url'), j.get('ats_url')):
            m = WD_RX.search(u or '')
            if m:
                lst = out.setdefault(RB.company_key(j.get('company')), [])
                if m.groups() not in lst:
                    lst.append(m.groups())
    return out


def decide(row, follow, known, guesses, tenants, board, wd_search, floor=0.75):
    """Pure (tested; every network call injected) → dict(code, ats_url?, how?, why?) or None (not an aggregator row).
    follow(url) → final URL or None · board(ats, token) → [(title, url)] · wd_search(host, tenant, site, title) → [(title, url)]."""
    k = kind(row.get('url'))
    if not k:
        return None
    if row.get('ats_url'):
        return {'code': 'already'}
    if k in ('zapply', 'vansh'):
        final = follow(row['url'])
        if not final:
            return {'code': 'dead_link', 'why': 'link did not resolve'}
        p = urllib.parse.urlsplit(final)
        if re.search(r'zapply\.jobs|vansh\.nyc', p.netloc):
            if 'zapply.jobs' in p.netloc and re.fullmatch(r'/jobs/?', p.path or ''):
                return {'code': 'expired', 'why': 'zapply link expired (lands on the job list)'}
            return {'code': 'stuck', 'why': 'link did not leave the aggregator'}
        return {'code': 'redirect', 'ats_url': RB.clean(final), 'how': f'{k} redirect'}
    title = (row.get('title') or '').strip()
    if not title:
        return {'code': 'no_title', 'why': 'row has no title to match'}
    n = 0
    for ats, token in list(known) + [g for g in guesses if g not in known]:
        n += 1
        hit = RB.best_match(title, board(ats, token), floor)
        if hit:
            return {'code': 'board', 'ats_url': hit[2], 'how': f'{ats} board "{token}" (title {hit[0]:.2f})'}
    for host, tenant, site in tenants:
        n += 1
        hit = RB.best_match(title, wd_search(host, tenant, site, title), floor)
        if hit:
            return {'code': 'workday', 'ats_url': hit[2], 'how': f'workday search {tenant}/{site} (title {hit[0]:.2f})'}
    return {'code': 'no_match', 'why': f'no matching posting on {n} board(s) for "{title}" at {row.get("company")}'}


# ---------- network (not part of the pure step) ----------
def follow(url):
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=RB.UA), timeout=25) as r:
            return r.geturl()
    except Exception:
        return None


_boards = {}


def board(ats, token):
    if (ats, token) not in _boards:
        _boards[(ats, token)] = RB.board_postings(ats, token)
    return _boards[(ats, token)]


def wd_search(host, tenant, site, title):
    import urllib.request
    body = json.dumps({'appliedFacets': {}, 'limit': 20, 'offset': 0, 'searchText': title}).encode()
    req = urllib.request.Request(f'https://{host}/wday/cxs/{tenant}/{site}/jobs', data=body,
                                 headers={**RB.UA, 'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode('utf-8', 'replace'))
        return [(p['title'], f'https://{host}/{site}{p["externalPath"]}') for p in d.get('jobPostings', []) if p.get('externalPath')]
    except Exception:
        return []


def main(a):
    import store
    if a and not a[0].startswith('--'):
        print(json.dumps(decide({'url': a[0]}, follow, [], [], [], board, wd_search), indent=1)); return 0
    jobs = store.load('jobs')
    known, tenants = RB.known_boards(jobs), workday_tenants(jobs)
    rows = [j for j in jobs if kind(j.get('url')) and not j.get('ats_url') and ('--retry' in a or not j.get('ats_unresolved'))]
    if '--limit' in a:
        rows = rows[:int(a[a.index('--limit') + 1])]
    def one(j):
        ck = RB.company_key(j.get('company'))
        return j['id'], decide(j, follow, known.get(ck, []), RB.guesses(j.get('company')), tenants.get(ck, []), board, wd_search)
    with ThreadPoolExecutor(8) as ex:
        res = dict(ex.map(one, rows))
    from collections import Counter
    print(json.dumps(Counter(f"{kind(j['url'])}:{res[j['id']]['code']}" for j in rows), indent=1))
    if '--write' in a:
        import datetime
        today, by = datetime.date.today().isoformat(), {j['id']: j for j in jobs}
        for i, r in res.items():
            if r.get('ats_url'):
                by[i].update(ats_url=r['ats_url'], ats_resolved=r['how'], ats_resolved_on=today); by[i].pop('ats_unresolved', None)
            elif r.get('why'):
                by[i]['ats_unresolved'] = r['why']
        store.save('jobs', jobs)
        print(f"written: {sum(1 for r in res.values() if r.get('ats_url'))} ats_url, {sum(1 for r in res.values() if r.get('why'))} ats_unresolved")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
