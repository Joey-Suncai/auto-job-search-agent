#!/usr/bin/env python3
"""Indeed search as a weekly source (2026-11-03, JSA-110: 50 sampled roles, ~60 % already in the store, ~20 new).

Runs in the job Chrome (CDP 9222, Joey's weekly full refresh — never from a LaunchAgent): 8 searches × first result page,
8–14 s apart. The cards come from the page's own job-card data (`window.mosaic.providerData["mosaic-provider-jobcards"]`);
no job page is opened. A challenge page (CAPTCHA / "verify you are human" / Cloudflare) stops the run and is reported —
never solved or worked around.
Kept: his tracks (data / analytics / BI / product / AI), not senior, in the U.S., and either a Summer 2027 internship
(wd_search.keep_posting) or a new-grad / entry title with no year other than 2027 / 2028. Dropped: rows already in the
store (same Indeed job key, or same normalised company + title), at most 2 per company. New rows: `source` =
indeed_search, `url` = the Indeed job page; the gate and the ATS search (`resolve_careers.py`) then find the posting.
usage: python3 indeed_search.py [--write] [--html <dir of saved search pages>]   (without --write: print counts only)
Tests (rule 13): scripts/test_indeed_search.py with DeepSeek cases.
"""
import json, os, re, sys, time, random, datetime as dt, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
from wd_search import keep_posting as _intern_ok  # noqa: E402
from us_location import is_non_us  # noqa: E402

QUERIES = ["data analyst intern", "data engineer intern", "product manager intern", "business intelligence intern",
           "AI engineer intern", "data analyst new grad", "associate product manager", "data engineer new grad"]
TRK = re.compile(r'\b(data|analy\w*|ai|a\.i\.|machine learning|ml|llm|genai|agent\w*|product|business intelligence|bi|insights?)\b', re.I)
SENIOR = re.compile(r'\b(senior|sr\.?|staff|principal|lead|director|head of|vp|vice president|manager ii|architect|phd|ph\.d|postdoc|mba)\b', re.I)
NEWGRAD = re.compile(r'\b(new grad(uate)?|new college grad|recent grad(uate)?|entry[- ]level|junior|associate product manager|apm|early career|university grad(uate)?|graduate program|rotational|class of 202[78]|202[78] start)\b', re.I)
OFFTERM = re.compile(r'\b(fall|autumn|spring|winter|co-?op|year[- ]round|part[- ]time|sprint season)\b', re.I)
BLOCK = re.compile(r'verify you are human|are you a robot|just a moment|security check|captcha|access denied|unusual (activity|traffic)|press (and|&) hold', re.I)
SUFFIX = r"\b(inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|limited|plc|lp|llp|holdings?|group|the|usa|us|america|na|n\.a|services|technologies|technology|labs?|global|international)\b"


def norm(c):
    """Company key, the same as build_jobs.py / append_new.py."""
    c = (c or "").lower().replace("&", " and "); c = re.sub(r"\.com\b", "", c); c = re.sub(r"[^a-z0-9 ]+", " ", c); c = re.sub(SUFFIX, " ", c)
    return re.sub(r"\s+", " ", c).strip()


def title_key(t):
    """Pure (tested). Title key for duplicates: lower case, brackets / years / seasons / 'intern' / 'new grad' dropped."""
    t = re.sub(r'\(.*?\)|\[.*?\]', ' ', str(t or '').lower())
    t = re.sub(r'\b(20\d\d|summer|internships?|interns?|new grad(uate)?|remote|usa?)\b', ' ', t)
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def parse_cards(html):
    """Pure (tested). An Indeed search page → [{'jobkey', 'company', 'title', 'location', 'posted', 'job_types'}]."""
    m = re.search(r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});\s*window', str(html or ''), re.S)
    if not m:
        return []
    try:
        res = json.loads(m.group(1))['metaData']['mosaicProviderJobCardsModel']['results']
    except (ValueError, KeyError, TypeError):
        return []
    out = []
    for r in res:
        if not r.get('jobkey') or not r.get('title'):
            continue
        ms = r.get('pubDate')
        posted = dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc).date().isoformat() if str(ms or '').isdigit() else ''
        out.append({'jobkey': str(r['jobkey']).lower(), 'company': r.get('company') or '', 'title': r['title'],
                    'location': r.get('formattedLocation') or '', 'posted': posted, 'job_types': list(r.get('jobTypes') or [])})
    return out


def level_of(title, job_types=()):
    """Pure (tested). 'Internship' (a Summer 2027 U.S.-style intern title), 'New Grad / Entry', or None (not kept)."""
    t = str(title or '')
    if OFFTERM.search(t):
        return None
    if re.search(r'\bintern(ship)?s?\b', t, re.I):
        return 'Internship' if _intern_ok(t, '') else None
    years = set(re.findall(r'\b(20\d\d)\b', t))
    if years - {'2027', '2028'}:
        return None
    if NEWGRAD.search(t):
        return 'New Grad / Entry'
    return None


def keep_card(title, location, job_types=()):
    """Pure (tested). His track, not senior, in the U.S., and level_of() is not None."""
    t = str(title or '')
    if not TRK.search(t) or SENIOR.search(t) or is_non_us(location):
        return False
    return level_of(t, job_types) is not None


def known(rows):
    """Pure (tested). Store rows → (Indeed job keys, {(norm company, title_key)})."""
    keys, pairs = set(), set()
    for r in rows:
        for u in (r.get('url'), r.get('ats_url')):
            m = re.search(r'indeed\.com/.*[?&]jk=([0-9a-f]+)', str(u or ''), re.I)
            if m:
                keys.add(m.group(1).lower())
        pairs.add((norm(r.get('company')), title_key(r.get('title'))))
    return keys, pairs


def pick_new(cards, keys, pairs):
    """Pure (tested). Cards → kept, not in the store, no repeats, at most 2 per company (store order kept)."""
    keys, pairs, per, new = set(keys), set(pairs), {}, []
    for c in cards:
        p = (norm(c['company']), title_key(c['title']))
        if c['jobkey'] in keys or p in pairs or not keep_card(c['title'], c['location'], c.get('job_types')):
            continue
        if per.get(p[0], 0) >= 2:
            continue
        per[p[0]] = per.get(p[0], 0) + 1; keys.add(c['jobkey']); pairs.add(p)
        new.append(c)
    return new


def to_rows(new, rows, today):
    """Pure (tested). New cards → store rows with the next free J-ids after `rows`."""
    nid = max([int(re.sub(r'\D', '', r['id']) or 0) for r in rows if str(r.get('id', '')).startswith('J')] or [0]) + 1
    out = []
    for n in new:
        out.append({'id': f'J{nid:05d}', 'company': n['company'], 'title': n['title'], 'location': n['location'],
                    'url': f"https://www.indeed.com/viewjob?jk={n['jobkey']}", 'tier': 'C', 'score': 45,
                    'score_note': 'indeed_search default (tier median)', 'level': level_of(n['title'], n.get('job_types')),
                    'added': today, 'source': 'indeed_search', 'posted': n['posted']})
        nid += 1
    return out


def search_url(q):
    return 'https://www.indeed.com/jobs?' + urllib.parse.urlencode({'q': q, 'l': 'United States'})


def fetch_pages(cdp='http://127.0.0.1:9222'):
    """Network. One new tab in the job Chrome; stops at the first challenge page. → (html pages, note)."""
    from playwright.sync_api import sync_playwright
    pages, note = [], ''
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(cdp).contexts[0]
        pg = ctx.new_page()
        try:
            for i, q in enumerate(QUERIES):
                pg.goto(search_url(q), wait_until='domcontentloaded', timeout=45000); pg.wait_for_timeout(6000)
                body = pg.inner_text('body')[:3000]
                if BLOCK.search(pg.title()) or (len(body) < 1500 and BLOCK.search(body)):
                    note = f'challenge page at query {i + 1} ({q}) — stopped, nothing solved'
                    break
                pages.append(pg.content())
                time.sleep(8 + random.random() * 6)
        finally:
            pg.close()
    return pages, note


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    rows = store.load('jobs')
    if '--html' in a:
        d = a[a.index('--html') + 1]
        pages, note = [open(os.path.join(d, f), errors='replace').read() for f in sorted(os.listdir(d)) if f.startswith('indeed') and f.endswith('.html')], 'saved pages'
    else:
        pages, note = fetch_pages()
    cards = [c for h in pages for c in parse_cards(h)]
    keys, pairs = known(rows)
    new = to_rows(pick_new(cards, keys, pairs), rows, dt.date.today().isoformat())
    print(f'{len(pages)} pages · {len(cards)} cards · {len(new)} new' + (f' · {note}' if note else ''))
    if '--write' not in a:
        for n in new:
            print(' ', n['level'][:8], n['company'][:24], '|', n['title'][:60], '|', n['location'][:24])
        return
    store.save('jobs', rows + new)
    print(f'appended {len(new)} rows to data/store/jobs.jsonl (run the gate next)')


if __name__ == '__main__':
    main(sys.argv[1:])
