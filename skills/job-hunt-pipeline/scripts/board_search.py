#!/usr/bin/env python3
"""Lever / Ashby job-board search (2026-11-02, JSA-050: Ashby and Lever need more test internships than the store holds).

Every Lever site and Ashby organisation already linked from data/store/jobs.jsonl is read through its public board API —
no login, no browser:
  Lever  https://api.lever.co/v0/postings/<site>?mode=json          (text, categories.location, hostedUrl, id)
  Ashby  https://api.ashbyhq.com/posting-api/job-board/<org>         (jobs: title, location, jobUrl, id, isListed)
Kept: internship titles for summer / 2027 in the U.S. (wd_search.keep_posting, the same filter as the Workday search);
dropped: postings already in the store (by posting id), companies with a tier A/B role (never used for tests), unlisted
Ashby postings; at most 2 per company, Joey's tracks (tier C) before other fields (tier D). New rows are appended with
`added` = today, `source` = lever_search / ashby_search; the gate (`run_daily.py gate`) then reads each JD.
usage: python3 board_search.py [--write] [--only lever|ashby] [--extra references/extra_boards.txt]      (without --write: print counts only)
Tests (rule 13): scripts/test_board_search.py with DeepSeek cases.
"""
import json, os, re, sys, threading, time, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
from wd_search import keep_posting as _wd_keep, UA  # noqa: E402


def keep_posting(title, location):
    """Pure (tested). wd_search.keep_posting — the non-U.S. check is us_location.is_non_us, shared with the Workday search
    (JSA-084: the old extra list here missed Auckland / New Zealand)."""
    return _wd_keep(title, location)

TRK = re.compile(r'\b(data|analy|analytics|ai\b|a\.i\.|machine learning|ml\b|product|business intelligence|bi\b|insight|quant|statist)', re.I)
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def parse_board(url):
    """Pure (tested). A Lever / Ashby job or board URL → ('lever' | 'ashby', board name lower-case) or None.
    https://jobs.lever.co/a Lever employer/abc-…/apply → ('lever', 'quantco'); https://jobs.ashbyhq.com/mercor/… → ('ashby', 'mercor')."""
    m = re.search(r'^https?://jobs(?:\.eu)?\.lever\.co/([^/?#]+)', str(url or ''), re.I)
    if m:
        return 'lever', m.group(1).lower()
    m = re.search(r'^https?://jobs\.ashbyhq\.com/([^/?#]+)', str(url or ''), re.I)
    if m and m.group(1).lower() not in ('api', 'embed'):
        return 'ashby', m.group(1).lower()
    return None


def posting_id(url):
    """Pure (tested). The posting UUID in a Lever / Ashby URL (lower-case), or ''."""
    m = re.search(UUID, str(url or ''), re.I)
    return m.group(0).lower() if m else ''


def board_postings(kind, data):
    """Pure (tested). A board API response → [{'id', 'title', 'location', 'url', 'posted'}] (unlisted Ashby jobs dropped)."""
    out = []
    if kind == 'lever':
        for p in data if isinstance(data, list) else []:
            cat = p.get('categories') or {}
            loc = cat.get('location') or ' / '.join(cat.get('allLocations') or [])
            posted = dt.datetime.fromtimestamp(p['createdAt'] / 1000, dt.timezone.utc).date().isoformat() if p.get('createdAt') else ''
            out.append({'id': str(p.get('id') or '').lower(), 'title': p.get('text') or '', 'location': loc,
                        'url': p.get('hostedUrl') or '', 'posted': posted})
    elif kind == 'ashby':
        for p in (data or {}).get('jobs') or []:
            if p.get('isListed') is False:
                continue
            locs = [p.get('location') or ''] + [s.get('location') or '' for s in p.get('secondaryLocations') or [] if isinstance(s, dict)]
            if p.get('isRemote') and not any(re.search('remote', x, re.I) for x in locs):
                locs.append('Remote')
            out.append({'id': str(p.get('id') or '').lower(), 'title': p.get('title') or '', 'location': ' / '.join(x for x in locs if x),
                        'url': p.get('jobUrl') or '', 'posted': (p.get('publishedAt') or '')[:10]})
    return out


def parse_extra(text):
    """Pure (tested). Lines of an extra-boards file → [('lever' | 'ashby', board lower-case)]; '#' comments, blank lines,
    unknown kinds and duplicates dropped; a full jobs.lever.co / jobs.ashbyhq.com URL is accepted too (JSA-072)."""
    out = []
    for line in str(text or '').splitlines():
        s = line.split('#', 1)[0].strip()
        if not s:
            continue
        b = parse_board(s) or (lambda m: (m.group(1).lower(), m.group(2).strip().lower()) if m else None)(
            re.match(r'^(lever|ashby)\s*:\s*([A-Za-z0-9_.-]+)\s*$', s, re.I))
        if b and b not in out:
            out.append(b)
    return out


def board_name(board):
    """Pure (tested). A company name for a board with no store row: 'rhombus-systems' → 'Rhombus Systems'."""
    return ' '.join(w.capitalize() for w in re.split(r'[-_.]+', str(board or '')) if w) or str(board or '')


def fetch(kind, board):
    url = (f'https://api.lever.co/v0/postings/{board}?mode=json' if kind == 'lever'
           else f'https://api.ashbyhq.com/posting-api/job-board/{board}')
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except Exception:
        return None


def known(rows):
    """Pure (tested). Store rows → (posting ids already in the store, {(kind, board): company}, lower-case tier A/B companies)."""
    keys, boards, ab = set(), {}, set()
    for r in rows:
        for u in (r.get('ats_url'), r.get('url')):
            b = parse_board(u or '')
            if b:
                boards.setdefault(b, r.get('company') or '')
            k = posting_id(u or '')
            if k:
                keys.add(k)
        if r.get('tier') in ('A', 'B') or r.get('tier_orig') in ('A', 'B'):
            ab.add((r.get('company') or '').lower())
    return keys, boards, ab


def pick_new(keys, ab, results):
    """Pure (tested). [(((kind, board), company), board API data or None)] → new internship postings: not in `keys`,
    not a tier A/B company, keep_posting, at most 2 per company with Joey's tracks first (tier C, else D)."""
    keys, new, percomp = set(keys), [], {}
    for ((kind, board), company), data in results:
        if data is None or company.lower() in ab:
            continue
        posts = [p for p in board_postings(kind, data) if p['id'] and p['id'] not in keys and keep_posting(p['title'], p['location'])]
        for p in sorted(posts, key=lambda p: 0 if TRK.search(p['title']) else 1):
            if percomp.get(company, 0) >= 2 or p['id'] in keys:
                continue
            percomp[company] = percomp.get(company, 0) + 1; keys.add(p['id'])
            new.append(dict(p, company=company, kind=kind, tier='C' if TRK.search(p['title']) else 'D'))
    return new


def to_rows(new, rows, today):
    """Pure (tested). New postings → store rows with the next free J-ids after `rows`."""
    nid = max([int(re.sub(r'\D', '', r['id']) or 0) for r in rows if str(r.get('id', '')).startswith('J')] or [0]) + 1
    out = []
    for n in new:
        out.append({'id': f'J{nid:05d}', 'company': n['company'], 'title': n['title'], 'location': n['location'],
                    'url': n['url'], 'ats_url': n['url'], 'tier': n['tier'], 'score': 45 if n['tier'] == 'C' else 35,
                    'score_note': f"{n['kind']}_search default (tier median)", 'level': 'Internship', 'added': today,
                    'source': f"{n['kind']}_search", 'posted': n['posted'],
                    'track': 'Data Sci / Analytics' if n['tier'] == 'C' else 'Other'})
        nid += 1
    return out


def fetch_all(items, workers=8, deadline=1200):
    """Network. Read every board with `workers` threads; whatever is unfinished after `deadline` seconds counts as
    unreadable (None) so the 08:15 refresh never hangs on a slow board (2026-11-02: big boards took 60-130 s each)."""
    got, lock, queue = {}, threading.Lock(), list(items)

    def work():
        while True:
            with lock:
                if not queue:
                    return
                it = queue.pop(0)
            got[it[0]] = fetch(*it[0])
    for _ in range(workers):
        threading.Thread(target=work, daemon=True).start()
    end = time.time() + deadline
    while time.time() < end and len(got) < len(items):
        time.sleep(1)
    return [(it, got.get(it[0])) for it in items]


def search(rows, extra=None, only=None, today=None):
    """Network. Every board in `rows` (+ the `extra` file) → (new store rows, counts line). Used by main() and by the 08:15
    refresh (scripts/daily/run_daily.py, JSA-076), which appends the rows after its own append-only check."""
    keys, boards, ab = known(rows)
    if extra:                                            # boards outside the store (JSA-072)
        for b in parse_extra(open(extra, encoding='utf-8').read()):
            boards.setdefault(b, board_name(b[1]))
    items = [it for it in boards.items() if not only or it[0][0] == only]
    res = fetch_all(items)
    new = pick_new(keys, ab, res)
    failed = sum(1 for _, d in res if d is None)
    line = (f"{len(items)} boards ({failed} unreadable) · " +
            ' · '.join(f"{k}: {sum(1 for n in new if n['kind'] == k)} new" for k in ('lever', 'ashby')))
    return to_rows(new, rows, today or dt.date.today().isoformat()), line


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    rows = store.load('jobs')
    added, line = search(rows, a[a.index('--extra') + 1] if '--extra' in a else None,
                         a[a.index('--only') + 1] if '--only' in a else None)
    print(line)
    if '--write' not in a:
        for n in added[:60]:
            print(' ', n['source'][:2], n['tier'], n['company'][:24], '|', n['title'][:60], '|', n['location'][:28])
        return
    store.save('jobs', rows + added)
    print(f'appended {len(added)} rows to data/store/jobs.jsonl (run the gate next)')


if __name__ == '__main__':
    main(sys.argv[1:])
