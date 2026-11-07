#!/usr/bin/env python3
"""Dice search as a weekly source (2026-11-03, JSA-111: 50 sampled roles, ~42 % already in the store, ~29 new — most of them
staffing / government-contractor "junior" roles, ~6 real target employers).

Plain HTTP, no browser, no sign-in: Dice's own SEO search pages (`/jobs/q-<query>-jobs`, listed in its sitemap
`sitemap_ts.xml` and allowed by robots.txt — the `/jobs?q=` form is disallowed there, so it is not used). 13 pages × first
20 cards, 1.5–2.5 s apart. A 403 / 429 / 202 / empty body or a challenge page stops the run and is reported — never
worked around.
Kept: indeed_search.keep_card (his tracks, not senior, U.S., Summer 2027 intern or new-grad / entry title) and not an
off-track role (sales, marketing, security, AML, QA, audit, design …). Dropped: rows already in the store (same Dice job
id, or same normalised company + title_key, or + alt_key — Dice writes "Title (Team) - 2027 Start" where the company
site writes "Title - Team - 2027 Start"), at most 2 per company. New rows: `source` = dice_search, `url` = the Dice job page.
usage: python3 dice_search.py [--write] [--html <dir of saved search pages>]   (without --write: print counts only)
Tests (rule 13): scripts/test_dice_search.py with DeepSeek cases.
"""
import json, os, re, sys, time, random, datetime as dt, html as H, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
from indeed_search import norm, title_key, keep_card, level_of  # noqa: E402

QUERIES = ['Business+Analyst+Intern', 'Engineering+Intern', 'Research+Intern', 'Entry+Level+Data+Analyst', 'Junior+Data+Analyst',
           'Entry+Level+Data+Scientist', 'Entry+Level+Data+Engineer', 'Entry+Level+Machine+Learning+Engineer',
           'Entry+Level+AI+Engineer', 'Junior+BI+Analyst', 'Entry+Level+Business+Data+Analyst', 'Entry+Level+Product+Manager',
           'Entry+Level+Analytics+Analyst']
OFF = re.compile(r'\b(design(er)?|sales|marketing|security|cyber|soc|audit\w*|quality|qa|fraud|aml|anti-money|credit|investment|'
                 r'accounting|hardware|mechanical|electrical|creative|customer|recruit\w*|hr|people|edi|helpdesk|help desk)\b', re.I)
BLOCK = re.compile(r'verify you are human|are you a robot|just a moment|human verification|captcha|access denied|unusual (activity|traffic)', re.I)
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'


def alt_key(title):
    """Pure (tested). Second title key: lower case, bracket text KEPT as words, 20xx years / 'start' / 'summer' dropped,
    every run of non-alphanumeric characters → one space."""
    t = str(title or '').lower()
    t = re.sub(r'\b(20\d\d|start|summer)\b', ' ', t)
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def keep(title, location):
    """Pure (tested). indeed_search.keep_card and not an off-track role."""
    return keep_card(title, location) and not OFF.search(str(title or ''))


def parse_cards(html):
    """Pure (tested). A Dice search page → [{'guid', 'company', 'title', 'location'}] in page order."""
    out = []
    for seg in str(html or '').split('data-testid="job-card"')[1:]:
        m = re.search(r'aria-label="View Details for (.*?) \(([0-9a-f]+)\)"', seg)
        if not m:
            continue
        title = H.unescape(m.group(1)).strip()
        g = re.search(r'href="/job-detail/([0-9a-f-]+)"', seg, re.I)
        txt = [H.unescape(t).strip() for t in re.split(r'<[^>]+>', seg[:8000])]
        txt = [t for t in txt if t]
        company = txt[1] if len(txt) > 1 and txt[0].startswith('role=') else ''
        loc = ''
        for i, t in enumerate(txt):
            if t == title and i + 1 < len(txt):
                loc = txt[i + 1]; break
        out.append({'guid': (g.group(1) if g else m.group(2)).lower(), 'company': company, 'title': title, 'location': loc})
    return out


def known(rows):
    """Pure (tested). Store rows → (Dice job ids, {(norm company, title_key)} ∪ {(norm company, alt_key)})."""
    ids, pairs = set(), set()
    for r in rows:
        for u in (r.get('url'), r.get('ats_url')):
            m = re.search(r'dice\.com/job-detail/([0-9a-f-]+)', str(u or ''), re.I)
            if m:
                ids.add(m.group(1).lower())
        c = norm(r.get('company'))
        pairs.add((c, title_key(r.get('title')))); pairs.add((c, alt_key(r.get('title'))))
    return ids, pairs


def pick_new(cards, ids, pairs):
    """Pure (tested). Cards → kept, not in the store, no repeats, at most 2 per company (page order kept)."""
    ids, pairs, per, new = set(ids), set(pairs), {}, []
    for c in cards:
        co = norm(c['company'])
        p, q = (co, title_key(c['title'])), (co, alt_key(c['title']))
        if c['guid'] in ids or p in pairs or q in pairs or not keep(c['title'], c['location']):
            continue
        if per.get(co, 0) >= 2:
            continue
        per[co] = per.get(co, 0) + 1; ids.add(c['guid']); pairs.add(p); pairs.add(q)
        new.append(c)
    return new


def to_rows(new, rows, today):
    """Pure. New cards → store rows with the next free J-ids after `rows`."""
    nid = max([int(re.sub(r'\D', '', r['id']) or 0) for r in rows if str(r.get('id', '')).startswith('J')] or [0]) + 1
    out = []
    for n in new:
        out.append({'id': f'J{nid:05d}', 'company': n['company'], 'title': n['title'], 'location': n['location'],
                    'url': f"https://www.dice.com/job-detail/{n['guid']}", 'tier': 'C', 'score': 45,
                    'score_note': 'dice_search default (tier median)', 'level': level_of(n['title']),
                    'added': today, 'source': 'dice_search', 'posted': ''})
        nid += 1
    return out


def page_url(q):
    return f'https://www.dice.com/jobs/q-{q}-jobs'


def fetch_pages():
    """Network. Plain GETs, 1.5–2.5 s apart; stops at the first block. → (html pages, note)."""
    pages, note = [], ''
    for i, q in enumerate(QUERIES):
        try:
            r = urllib.request.urlopen(urllib.request.Request(page_url(q), headers={'User-Agent': UA, 'Accept-Language': 'en-US'}), timeout=30)
            h, code = r.read().decode('utf-8', 'replace'), r.status
        except urllib.error.HTTPError as e:
            note = f'HTTP {e.code} at page {i + 1} ({q}) — stopped'; break
        if code != 200 or len(h) < 5000 or (len(h) < 30000 and BLOCK.search(h)):
            note = f'blocked / empty page at page {i + 1} ({q}, HTTP {code}, {len(h)} bytes) — stopped'; break
        pages.append(h)
        time.sleep(1.5 + random.random())
    return pages, note


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    rows = store.load('jobs')
    if '--html' in a:
        d = a[a.index('--html') + 1]
        pages, note = [open(os.path.join(d, f), errors='replace').read() for f in sorted(os.listdir(d)) if f.endswith('.html')], 'saved pages'
    else:
        pages, note = fetch_pages()
    cards = [c for h in pages for c in parse_cards(h)]
    ids, pairs = known(rows)
    new = to_rows(pick_new(cards, ids, pairs), rows, dt.date.today().isoformat())
    print(f'{len(pages)} pages · {len(cards)} cards · {len(new)} new' + (f' · {note}' if note else ''))
    if '--write' not in a:
        for n in new:
            print(' ', n['level'][:8], n['company'][:24], '|', n['title'][:60], '|', n['location'][:24])
        return
    store.save('jobs', rows + new)
    print(f'appended {len(new)} rows to data/store/jobs.jsonl (run the gate next)')


if __name__ == '__main__':
    main(sys.argv[1:])
