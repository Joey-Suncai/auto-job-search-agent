#!/usr/bin/env python3
"""Built In job search as a weekly source (JSA-069, 2026-11-03; rebuilt from SKILL.md §1C step 5 and the 11-01 output
`data/raw/jsa_builtin_2026-11-01.json` — the 11-01 scratchpad script was lost).

Runs in the job Chrome (CDP 9222; the weekly full refresh 「全量刷新」 — never from a LaunchAgent). One new tab opens
builtin.com once, then reads the search pages with Built In's own same-origin `fetch('/jobs?search=<q>&country=USA&
allLocations=true&page=N')` + DOMParser (10 queries × ≤ 6 pages, one request at a time, 2–4 s apart — Built In
rate-limits parallel requests). Cards: `div[id^="job-card-"]`, link `a[href*="/job/"]`; no job page is opened.
(`/jobs/entry-level` defaults to remote / hybrid only — not used.) A challenge page or a non-200 answer stops the run
and is reported — never solved or worked around.
Kept: the same rules as indeed_search.py (his tracks, not senior / PhD / MBA, in the U.S., a Summer 2027 internship or a
2027/2028 new-grad title). Dropped: rows already in the store (same Built In job id in `url` / `ats_url` / `elig_key`
"bi:<id>", or same normalised company + title) and repeats inside the run. New rows: `source` = builtin (Sources label
"Built In"), `url` = https://builtin.com/job/<slug>/<id>, tier = the company's tier in the store (else C); then
`resolve_builtin.py --all --chrome --write` finds the real application link and the gate reads the JD.
usage: python3 builtin_search.py [--write] [--json <saved cards .json>] [--save <cards .json>]
                                 [--today YYYY-MM-DD] [--as-of YYYY-MM-DD]
  without --write: counts only · a live run saves its cards to data/raw/jsa_builtin_<today>.json unless --save is given ·
  --as-of: replay against the store as it was before that date (rows added on / after it count as unknown; no --write)
Tests (rule 13): scripts/test_builtin_search.py with DeepSeek cases.
"""
import json, os, re, sys, time, random, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, HERE)
from indeed_search import norm, title_key, keep_card, level_of, BLOCK  # noqa: E402
from linkedin_search import rel_date, company_tiers, next_id  # noqa: E402

QUERIES = ["data science intern", "machine learning intern", "quantitative intern", "business analyst intern",
           "AI engineer intern", "data engineer intern", "data analyst intern", "business intelligence intern",
           "product manager intern", "product analyst intern"]
MAX_PAGES = 6
# in-page: one search page → its cards (text nodes of each card, the job link, the company link)
PAGE_JS = """async (path) => {
  const r = await fetch(path, {credentials: 'include'});
  const html = await r.text();
  const d = new DOMParser().parseFromString(html, 'text/html');
  const cards = [...d.querySelectorAll('div[id^="job-card-"]')].map(c => {
    const a = c.querySelector('a[href*="/job/"]'), co = c.querySelector('a[href*="/company/"]');
    const parts = [], w = d.createTreeWalker(c, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { const t = n.textContent.replace(/\\s+/g, ' ').trim(); if (t && parts[parts.length - 1] !== t) parts.push(t); }
    return {id: c.id.replace('job-card-', ''), href: a ? a.getAttribute('href') : '', title: a ? a.innerText.trim() || a.textContent.trim() : '',
            company: co ? co.textContent.trim() : '', lines: parts};
  });
  return {status: r.status, title: d.title, head: html.slice(0, 3000), cards: cards};
}"""
MODE = re.compile(r'^(in-office|hybrid|remote)( or (in-office|hybrid|remote))?$', re.I)
SALARY = re.compile(r'^\d[\d.]*[KM]?\s*-\s*\d[\d.]*[KM]?\s+(hourly|annually|monthly)$', re.I)
LEVEL = re.compile(r'^(internship|entry level|junior|mid level|senior level|expert/leader)$', re.I)
SCORE_NOTE = 'builtin full refresh default'


def job_id(u):
    """Pure (tested). 'https://builtin.com/job/<slug>/<digits>' or '/job/<slug>/<digits>' (query / '#' / trailing '/'
    allowed) → the digits; '' otherwise."""
    m = re.search(r'(?:builtin\.com)?/job/[^/?#\s]+/(\d+)(?:[/?#]|$)', str(u or ''), re.I)
    return m.group(1) if m else ''


def slug(title):
    return re.sub(r'[^a-z0-9]+', '-', str(title or '').lower()).strip('-')


def parse_card(rec, today):
    """Pure (tested). One card {'id', 'href', 'lines', optional 'title' / 'company'} → {'job_id', 'title', 'company',
    'location', 'remote', 'salary', 'posted', 'bi_level', 'url'}, or None without an id, title or company.
    The job id is the one in href (/job/<slug>/<id>); the card's own id ("job-card-<n>") only without one — the two
    differ on some cards. Lines (as saved on 11-01): company, title, posted ("3 Days Ago", "Reposted One Month Ago", "Yesterday"), work mode
    ("In-Office", "Hybrid", "Remote", "In-Office or Remote", "Remote or Hybrid"), location ("City, ST, USA",
    "3 Locations"), optional "Easy Apply", optional salary ("28K-28K Hourly", "44K-44K Annually"), level
    ("Internship", "Entry level", …). Given 'title' / 'company' win over the first two lines; the other parts are
    found by their shape, the location being the line right after the work mode. remote = "Yes" when the work mode
    starts with Remote, else ''. url = https://builtin.com + href, or /job/<title slug>/<id> without one."""
    jid = job_id(rec.get('href')) or re.sub(r'\D', '', str(rec.get('id') or ''))
    raw = [re.sub(r'\s+', ' ', str(x)).strip() for x in rec.get('lines') or []]
    lines = [x for x in raw if x]
    company = str(rec.get('company') or '').strip() or (raw[0] if raw else '')
    title = str(rec.get('title') or '').strip() or (raw[1] if len(raw) > 1 else '')
    if not jid or not title or not company:
        return None
    out = {'job_id': jid, 'title': title, 'company': company, 'location': '', 'remote': '', 'salary': '', 'posted': '',
           'bi_level': ''}
    rest = [x for x in lines if x not in (title, company)]
    mode_seen = False
    for i, x in enumerate(rest):
        if MODE.match(x) and not mode_seen:
            mode_seen = True
            out['remote'] = 'Yes' if x.lower().startswith('remote') else ''
            nxt = rest[i + 1] if i + 1 < len(rest) else ''
            if nxt and not (SALARY.match(nxt) or LEVEL.match(nxt) or MODE.match(nxt) or nxt.lower() == 'easy apply'):
                out['location'] = nxt
        elif SALARY.match(x) and not out['salary']:
            out['salary'] = x
        elif LEVEL.match(x) and not out['bi_level']:
            out['bi_level'] = x
        elif not out['posted'] and rel_date(x, today):
            out['posted'] = rel_date(x, today)
    href = str(rec.get('href') or '')
    if job_id(href) == jid:
        out['url'] = href if href.startswith('http') else 'https://builtin.com' + href.split('?')[0].split('#')[0]
    else:
        out['url'] = f'https://builtin.com/job/{slug(title)}/{jid}'
    return out


def known(rows):
    """Pure (tested). Store rows → (Built In job ids from url / ats_url / elig_key "bi:<id>", {(norm company, title_key)})."""
    ids, pairs = set(), set()
    for r in rows:
        for u in (r.get('url'), r.get('ats_url')):
            if job_id(u):
                ids.add(job_id(u))
        m = re.fullmatch(r'bi:(\d+)', str(r.get('elig_key') or ''))
        if m:
            ids.add(m.group(1))
        pairs.add((norm(r.get('company')), title_key(r.get('title'))))
    return ids, pairs


def pick_new(cards, ids, pairs):
    """Pure (tested). Parsed cards → kept (keep_card), not in the store, no repeats inside the run (same id, or same
    company + title key); input order kept. No per-company cap."""
    ids, pairs, new = set(ids), set(pairs), []
    for c in cards:
        p = (norm(c['company']), title_key(c['title']))
        if c['job_id'] in ids or p in pairs or not keep_card(c['title'], c['location']):
            continue
        ids.add(c['job_id']); pairs.add(p); new.append(c)
    return new


def to_rows(new, rows, today):
    """Pure (tested). New cards → store rows (fields as the 11-01 Built In rows) with the next free J-ids after `rows`."""
    nid, tiers, out = next_id(rows), company_tiers(rows), []
    for n in new:
        r = {'id': f'J{nid:05d}', 'company': n['company'], 'title': n['title'], 'location': n['location'], 'url': n['url'],
             'tier': tiers.get(norm(n['company']), 'C'), 'score': 45, 'score_note': SCORE_NOTE,
             'level': level_of(n['title']), 'added': today, 'source': 'builtin', 'posted': n['posted'], 'salary': n['salary']}
        if n.get('remote'):
            r['remote'] = n['remote']
        out.append(r); nid += 1
    return out


def page_path(q, page):
    from urllib.parse import urlencode
    return '/jobs?' + urlencode({'search': q, 'country': 'USA', 'allLocations': 'true', 'page': page})


def fetch_cards(cdp='http://127.0.0.1:9222'):
    """Network. One new tab on builtin.com in the job Chrome; same-origin fetches of the search pages → (raw cards with
    'query', note). Stops at a challenge page or a non-200 answer. First live run: the next full refresh (「全量刷新」)
    — not run when this was written."""
    from playwright.sync_api import sync_playwright
    cards, note = [], ''
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(cdp).contexts[0]
        pg = ctx.new_page()
        try:
            pg.goto('https://builtin.com/jobs', wait_until='domcontentloaded', timeout=60000); pg.wait_for_timeout(4000)
            body = pg.inner_text('body')[:3000]
            if BLOCK.search(pg.title()) or (len(body) < 1500 and BLOCK.search(body)):
                return [], f'challenge page at {pg.url[:120]} — stopped, nothing solved'
            for q in QUERIES:
                for n in range(1, MAX_PAGES + 1):
                    res = pg.evaluate(PAGE_JS, page_path(q, n))
                    if res['status'] != 200 or BLOCK.search(res['title'] or '') or (not res['cards'] and BLOCK.search(res['head'] or '')):
                        return cards, f'stopped at "{q}" page {n} (HTTP {res["status"]}, {res["title"][:60]!r}) — nothing solved'
                    cards += [dict(c, query=q) for c in res['cards']]
                    time.sleep(2 + random.random() * 2)
                    if not res['cards']:
                        break
        finally:
            pg.close()
    return cards, note


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    rows = store.load('jobs')
    today = dt.date.fromisoformat(a[a.index('--today') + 1]) if '--today' in a else dt.date.today()
    if '--json' in a:
        raw, note = json.load(open(a[a.index('--json') + 1])), 'saved cards'
    else:
        raw, note = fetch_cards()
        out = a[a.index('--save') + 1] if '--save' in a else jpaths.data('raw', f'jsa_builtin_{today}.json')
        json.dump(raw, open(out, 'w'), indent=1)
    base = rows
    if '--as-of' in a:
        if '--write' in a:
            sys.exit('--as-of is a replay check only; it cannot be combined with --write')
        cut = a[a.index('--as-of') + 1]
        base = [r for r in rows if (r.get('added') or '') < cut]
    cards = [c for c in (parse_card(r, today) for r in raw) if c]
    ids, pairs = known(base)
    kept = [c for c in cards if keep_card(c['title'], c['location'])]
    new = to_rows(pick_new(cards, ids, pairs), base, today.isoformat())
    print(f'{len(raw)} cards · {len(cards)} parsed · {len(kept)} kept · {len(new)} new' + (f' · {note}' if note else ''))
    if '--write' not in a:
        for n in new:
            print(' ', n['level'][:8], n['tier'], n['company'][:24], '|', n['title'][:60], '|', n['location'][:24])
        return
    store.save('jobs', rows + new)
    print(f'appended {len(new)} rows to data/store/jobs.jsonl (run the gate next)')


if __name__ == '__main__':
    main(sys.argv[1:])
