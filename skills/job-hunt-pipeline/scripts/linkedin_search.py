#!/usr/bin/env python3
"""LinkedIn job search as a weekly source (JSA-069, 2026-11-03; rebuilt from SKILL.md §1C step 1 and the 11-01 output
`data/raw/jsa_linkedin_2026-11-01.json` — the 11-01 scratchpad script was lost).

Runs in the job Chrome (CDP 9222, Joey signed in to LinkedIn; the weekly full refresh 「全量刷新」 — never from a
LaunchAgent). One new tab opens the search-results pages only (14 queries × start 0 / 25 / 50, 6–10 s apart) and reads
the job cards (`[componentkey^="job-card-component-ref-<jobId>"]`, their text lines). No job page is opened and no link
is followed anywhere else (JSA-114). A sign-in / authwall / checkpoint / challenge page stops the run and is reported —
never solved or worked around.
Kept: the same rules as indeed_search.py (his tracks, not senior / PhD / MBA, in the U.S., a Summer 2027 internship or a
2027/2028 new-grad title). Dropped: rows already in the store (same LinkedIn job id in `url` / `ats_url`, or same
normalised company + title) and repeats inside the run. New rows: `source` = linkedin (Sources label "LinkedIn"),
`url` = https://www.linkedin.com/jobs/view/<id>/, tier = the company's tier in the store (else C); the gate and
`resolve_careers.py` (company + title only) then find the company's own posting.
usage: python3 linkedin_search.py [--write] [--json <saved cards .json>] [--save <cards .json>]
                                  [--today YYYY-MM-DD] [--as-of YYYY-MM-DD]
  without --write: counts only · a live run saves its cards to data/raw/jsa_linkedin_<today>.json unless --save is given ·
  --as-of: replay against the store as it was before that date (rows added on / after it count as unknown; no --write)
Tests (rule 13): scripts/test_linkedin_search.py with DeepSeek cases.
"""
import collections, json, os, re, sys, time, random, datetime as dt, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, HERE)
from indeed_search import norm, title_key, keep_card, level_of, BLOCK  # noqa: E402

QUERIES = ["data analyst intern 2027", "product manager intern 2027", "AI engineer intern 2027", "data engineer intern 2027",
           "business analyst intern 2027", "product analyst intern 2027", "AI product intern 2027",
           "quantitative analyst intern 2027", "business intelligence intern 2027", "machine learning intern 2027",
           "associate product manager intern", "generative AI intern 2027", "analytics engineer intern 2027",
           "data science intern 2027"]
STARTS = (0, 25, 50)
CARDS_JS = """() => [...document.querySelectorAll('[componentkey^="job-card-component-ref-"]')].map(e => ({
  id: e.getAttribute('componentkey').replace('job-card-component-ref-', ''),
  lines: e.innerText.split('\\n').map(s => s.trim()).filter(Boolean)}))"""
SIGNIN = re.compile(r'linkedin\.com/(login|authwall|checkpoint|uas/|signup)', re.I)
UNITS = {'minute': 0, 'hour': 0, 'day': 1, 'week': 7, 'month': 30, 'year': 365}
MODE = re.compile(r'\s*\((on-site|onsite|hybrid|remote)\)\s*$', re.I)
SCORE_NOTE = 'linkedin full refresh default (tier of the company / tier median)'


def rel_date(text, today):
    """Pure (tested). 'Posted 2 weeks ago' / '3 days ago' / 'Reposted One Month Ago' / 'Yesterday' / 'Today' /
    '5 hours ago' → ISO date relative to `today` (a date); a week = 7 days, a month = 30, a year = 365; '' otherwise."""
    t = str(text or '').strip().lower()
    t = re.sub(r'^(re)?posted\s+', '', t)
    if re.fullmatch(r'(today|just now)', t):
        return today.isoformat()
    if t == 'yesterday':
        return (today - dt.timedelta(days=1)).isoformat()
    m = re.fullmatch(r'(\d+|an?|one) (minute|hour|day|week|month|year)s? ago', t)
    if not m:
        return ''
    n = 1 if m.group(1) in ('a', 'an', 'one') else int(m.group(1))
    return (today - dt.timedelta(days=n * UNITS[m.group(2)])).isoformat()


def job_id(u):
    """Pure (tested). A LinkedIn job URL (/jobs/view/<id>, ?currentJobId=<id>) → the numeric id ('' if none)."""
    m = re.search(r'linkedin\.com(?:/[^?#\s]*?)?(?:/jobs/view/(?:[^/?#\s]*?-)?(\d{6,})(?:[/?#]|$)|[?&]currentJobId=(\d{6,}))', str(u or ''), re.I)
    return (m.group(1) or m.group(2)) if m else ''


def parse_card(rec, today):
    """Pure (tested). One card {'id', 'lines'} → {'job_id', 'title', 'company', 'location', 'remote', 'salary',
    'posted', 'li_alumni', 'li_connections'}, or None without an id or three lines.
    Lines: title (a first line "<title> (Verified job)" followed by the plain title counts once; an exact repeat of
    the title also counts once), company, location ("City, ST (On-site)" → location "City, ST", "(Remote)" → remote
    "Yes"), then insights in any order: "N connection(s) work(s) here" → li_connections, "N school alumni work(s)
    here" → li_alumni, a line starting with "$" → salary, "Posted … ago" (else a bare "… ago") → posted (ISO)."""
    jid = re.sub(r'\D', '', str(rec.get('id') or ''))
    lines = [str(x).strip() for x in rec.get('lines') or [] if str(x).strip()]
    if not jid or not lines:
        return None
    t0 = re.sub(r'\s*\(verified job\)\s*$', '', lines[0], flags=re.I)
    rest = lines[1:] if len(lines) > 1 and lines[1] == t0 else [t0] + lines[1:]
    if len(rest) < 3:
        return None
    title, company, loc = rest[0], rest[1], rest[2]
    m = MODE.search(loc)
    out = {'job_id': jid, 'title': title, 'company': company, 'location': MODE.sub('', loc).strip(),
           'remote': 'Yes' if m and m.group(1).lower() == 'remote' else '', 'salary': '', 'posted': '',
           'li_alumni': 0, 'li_connections': 0}
    bare = ''
    for x in rest[3:]:
        if (mm := re.fullmatch(r'(\d[\d,]*) connections? works? here', x, re.I)):
            out['li_connections'] = int(mm.group(1).replace(',', ''))
        elif (mm := re.fullmatch(r'(\d[\d,]*) school alumni works? here', x, re.I)):
            out['li_alumni'] = int(mm.group(1).replace(',', ''))
        elif x.startswith('$') and not out['salary']:
            out['salary'] = x
        elif re.match(r'(re)?posted\b', x, re.I) and not out['posted']:
            out['posted'] = rel_date(x, today)
        elif not bare and rel_date(x, today):
            bare = rel_date(x, today)
    out['posted'] = out['posted'] or bare
    return out


def known(rows):
    """Pure (tested). Store rows → (LinkedIn job ids in url / ats_url, {(norm company, title_key)})."""
    ids, pairs = set(), set()
    for r in rows:
        for u in (r.get('url'), r.get('ats_url')):
            if job_id(u):
                ids.add(job_id(u))
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


def company_tiers(rows):
    """Pure (tested). Store rows → {norm company: its most common tier among A / B / C / D} (ties: the better tier)."""
    cnt = collections.defaultdict(collections.Counter)
    for r in rows:
        t = r.get('tier_orig') or r.get('tier')
        if t in ('A', 'B', 'C', 'D'):
            cnt[norm(r.get('company'))][t] += 1
    return {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, c in cnt.items() if k}


def next_id(rows):
    return max([int(re.sub(r'\D', '', r['id']) or 0) for r in rows if str(r.get('id', '')).startswith('J')] or [0]) + 1


def to_rows(new, rows, today):
    """Pure (tested). New cards → store rows (fields as the 11-01 LinkedIn rows) with the next free J-ids after `rows`."""
    nid, tiers, out = next_id(rows), company_tiers(rows), []
    for n in new:
        r = {'id': f'J{nid:05d}', 'company': n['company'], 'title': n['title'], 'location': n['location'],
             'url': f"https://www.linkedin.com/jobs/view/{n['job_id']}/", 'tier': tiers.get(norm(n['company']), 'C'),
             'score': 45, 'score_note': SCORE_NOTE, 'level': level_of(n['title']), 'added': today, 'source': 'linkedin',
             'posted': n['posted'], 'salary': n['salary'], 'li_alumni': n['li_alumni'], 'li_connections': n['li_connections']}
        if n.get('remote'):
            r['remote'] = n['remote']
        out.append(r); nid += 1
    return out


def search_url(q, start=0):
    return 'https://www.linkedin.com/jobs/search-results/?' + urllib.parse.urlencode(
        {'keywords': f'{q} in United States', 'f_TPR': 'r2592000', 'start': start})


def fetch_cards(cdp='http://127.0.0.1:9222'):
    """Network. One new tab in the job Chrome, search pages only → (raw cards with 'query', note). Stops at a sign-in
    or challenge page. First live run: the next full refresh (「全量刷新」) — not run when this was written."""
    from playwright.sync_api import sync_playwright
    cards, note = [], ''
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(cdp).contexts[0]
        pg = ctx.new_page(); pg.set_viewport_size({'width': 1300, 'height': 900})
        try:
            for q in QUERIES:
                for s in STARTS:
                    pg.goto(search_url(q, s), wait_until='domcontentloaded', timeout=60000); pg.wait_for_timeout(5000)
                    body = pg.inner_text('body')[:3000]
                    if SIGNIN.search(pg.url) or BLOCK.search(pg.title()) or (len(body) < 1500 and BLOCK.search(body)):
                        return cards, f'stopped at {pg.url[:120]} (sign-in / challenge, query "{q}" start {s}) — nothing solved'
                    last, same = -1, 0
                    for _ in range(12):           # the result list loads its cards as it scrolls
                        n = pg.evaluate("""() => { const c = document.querySelectorAll('[componentkey^="job-card-component-ref-"]');
                            if (c.length) c[c.length - 1].scrollIntoView(); return c.length; }""")
                        same = same + 1 if n == last else 0; last = n
                        if same >= 2:
                            break
                        pg.wait_for_timeout(1200)
                    got = pg.evaluate(CARDS_JS)
                    cards += [dict(c, query=q) for c in got]
                    if len(got) < 20:             # last page of this query
                        break
                    time.sleep(6 + random.random() * 4)
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
        out = a[a.index('--save') + 1] if '--save' in a else jpaths.data('raw', f'jsa_linkedin_{today}.json')
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
