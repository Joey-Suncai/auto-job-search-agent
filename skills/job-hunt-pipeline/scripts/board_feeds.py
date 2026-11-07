#!/usr/bin/env python3
"""Two job boards from kalil0321/ats-scrapers as weekly sources (JSA-139, 2026-11-04; Joey: 「求职网站也要搬，我已经做好的可以对比一下，
看看有没有优化的，没有做好的就直接搬。」 — comparison in references/ats_scrapers_port_2026-11-04.md).

Plain HTTP, no browser, no sign-in, no key; ≥ 1 s between requests (ats_search.fetch); a 403 / 406 / 429 / challenge page
stops that board and is reported — never worked around.
  yc   Y Combinator startup jobs: the public role pages `ycombinator.com/jobs/role/<role>[/<city>]` carry their postings as
       the page's `data-page` JSON (`props.jobPostings`: title, companyName, location, type, visa, url). 4 roles × 9 places
       = 36 pages. (ats-scrapers walks every hiring company's page instead: ~1,000 requests a week for the same data.)
  wwr  We Work Remotely: the all-jobs RSS and the 5 category feeds that can hold his roles (each caps at 100 items);
       items are deduped on <guid>; the title is "Company: Role"; location = region / state / country.
Kept: dice_search.keep (his tracks, not senior, U.S., Summer 2027 intern or new-grad / entry title, not an off-track role).
Dropped: rows already in the store (same board id, or same normalised company + title key / alt key), at most 2 per
company. New rows: `source` = yc_board / wwr_board, `url` = the board's posting page, `visa` = YC's "Will sponsor" etc.
Not ported, and why (JSA-139): Remote OK (robots.txt disallows ClaudeBot and AI use), Welcome to the Jungle (needs the
Algolia key embedded in their page), an Ashby employer (contract marketplace; anonymous Bearer header), and the non-U.S. boards.
usage: python3 board_feeds.py [--board yc|wwr|all] [--write] [--save <cards.json>] [--json <cards.json>]   (without --write: counts only)
Tests (rule 13): scripts/test_board_feeds.py with DeepSeek cases.
"""
import datetime as dt, html as H, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
from indeed_search import norm, title_key, level_of  # noqa: E402
from dice_search import alt_key, keep  # noqa: E402

YC_ROLES = ['software-engineer', 'product-manager', 'science', 'operations']
YC_PLACES = ['', 'san-francisco', 'new-york', 'seattle', 'boston', 'austin', 'chicago', 'los-angeles', 'remote']
WWR_FEEDS = ['remote-jobs', 'categories/all-other-remote-jobs', 'categories/remote-back-end-programming-jobs',
             'categories/remote-full-stack-programming-jobs', 'categories/remote-management-and-finance-jobs',
             'categories/remote-product-jobs']
ID_RX = {'yc': re.compile(r'ycombinator\.com/companies/[\w-]+/jobs/([\w-]+)', re.I),
         'wwr': re.compile(r'weworkremotely\.com/remote-jobs/([\w-]+)', re.I)}


def parse_yc(page):
    """Pure (tested). A YC jobs page → cards from the `data-page` attribute's JSON `props.jobPostings` (HTML entities
    decoded first): {'board': 'yc', 'id': the url's last path segment, 'company': companyName, 'title', 'location',
    'url': 'https://www.ycombinator.com' + url, 'type', 'visa'}; postings without a title or url are skipped; [] when the
    attribute is missing or not JSON."""
    m = re.search(r'data-page="([^"]+)"', str(page or ''))
    try:
        posts = (json.loads(H.unescape(m.group(1))).get('props') or {}).get('jobPostings') or [] if m else []
    except (ValueError, AttributeError):
        posts = []
    out = []
    for p in posts:
        u, t = (p or {}).get('url') or '', ((p or {}).get('title') or '').strip()
        if not u or not t:
            continue
        out.append({'board': 'yc', 'id': u.rstrip('/').split('/')[-1], 'company': (p.get('companyName') or '').strip(), 'title': t,
                    'location': (p.get('location') or '').strip(), 'url': u if u.startswith('http') else 'https://www.ycombinator.com' + u,
                    'type': p.get('type') or '', 'visa': p.get('visa') or ''})
    return out


def _tag(item, name):
    m = re.search(rf'<{name}>(.*?)</{name}>', item, re.S)
    v = m.group(1) if m else ''
    v = re.sub(r'^<!\[CDATA\[(.*)\]\]>$', r'\1', v.strip(), flags=re.S)
    return H.unescape(re.sub(r'<[^>]+>', ' ', v) if name != 'title' else v).strip()


def parse_wwr(xml):
    """Pure (tested). A We Work Remotely RSS feed → cards: per <item>, title "Company: Role" split on the first ': '
    (no colon → company '', title whole); id = the last path segment of <link>; location = <region>, <state>, <country>
    (non-empty, in that order) joined ', '; type = <type>; items without a title or link are skipped."""
    out = []
    for it in re.findall(r'<item>(.*?)</item>', str(xml or ''), re.S):
        t, link = _tag(it, 'title'), _tag(it, 'link')
        if not t or not link:
            continue
        co, _, role = t.partition(': ')
        if not role:
            co, role = '', t
        out.append({'board': 'wwr', 'id': link.rstrip('/').split('/')[-1], 'company': co.strip(), 'title': role.strip(),
                    'location': ', '.join(x for x in (_tag(it, 'region'), _tag(it, 'state'), _tag(it, 'country')) if x),
                    'url': link, 'type': _tag(it, 'type'), 'visa': ''})
    return out


def known(rows):
    """Pure (tested). Store rows → ({(board, id)} from url / ats_url, {(norm company, title_key)} ∪ {(norm company, alt_key)})."""
    ids, pairs = set(), set()
    for r in rows:
        for u in (r.get('url'), r.get('ats_url')):
            for b, rx in ID_RX.items():
                m = rx.search(str(u or ''))
                if m:
                    ids.add((b, m.group(1).lower()))
        c = norm(r.get('company'))
        pairs.add((c, title_key(r.get('title')))); pairs.add((c, alt_key(r.get('title'))))
    return ids, pairs


def pick_new(cards, ids, pairs):
    """Pure (tested). Cards → kept (dice_search.keep on title + location), not in the store, each (board, id) and
    (company, title) once, at most 2 per normalised company; card order kept."""
    ids, pairs, per, new = set(ids), set(pairs), {}, []
    for c in cards:
        co = norm(c['company'])
        k, p, q = (c['board'], str(c['id']).lower()), (co, title_key(c['title'])), (co, alt_key(c['title']))
        if k in ids or p in pairs or q in pairs or not keep(c['title'], c['location']) or per.get(co, 0) >= 2:
            continue
        per[co] = per.get(co, 0) + 1; ids.add(k); pairs.add(p); pairs.add(q)
        new.append(c)
    return new


def to_rows(new, rows, today):
    """Pure. New cards → store rows with the next free J-ids after `rows`."""
    nid = max([int(re.sub(r'\D', '', r['id']) or 0) for r in rows if str(r.get('id', '')).startswith('J')] or [0]) + 1
    out = []
    for n in new:
        out.append({'id': f'J{nid:05d}', 'company': n['company'], 'title': n['title'], 'location': n['location'], 'url': n['url'],
                    'tier': 'C', 'score': 45, 'score_note': f"{n['board']}_board default (tier median)", 'level': level_of(n['title']),
                    'added': today, 'source': f"{n['board']}_board", 'posted': '', **({'visa': n['visa']} if n.get('visa') else {})})
        nid += 1
    return out


def fetch_cards(board):
    """Network. → (cards, note). Stops a board at the first wall (ats_search.Blocked)."""
    import ats_search as AS
    urls = ([f"https://www.ycombinator.com/jobs/role/{r}" + (f'/{p}' if p else '') for r in YC_ROLES for p in YC_PLACES]
            if board == 'yc' else [f'https://weworkremotely.com/{f}.rss' for f in WWR_FEEDS])
    cards, seen, note = [], set(), ''
    for u in urls:
        try:
            st, _, body = AS.fetch(u)
        except AS.Blocked as e:
            note = f'{e} — stopped'; break
        if st != 200:
            continue
        for c in parse_yc(body) if board == 'yc' else parse_wwr(body):
            if (c['board'], c['id']) not in seen:
                seen.add((c['board'], c['id'])); cards.append(c)
    return cards, note


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    rows = store.load('jobs')
    b = a[a.index('--board') + 1] if '--board' in a else 'all'
    boards = ['yc', 'wwr'] if b == 'all' else [b]
    if '--json' in a:
        cards, notes = json.load(open(a[a.index('--json') + 1])), ['saved cards']
    else:
        cards, notes = [], []
        for bd in boards:
            got, note = fetch_cards(bd)
            cards += got
            notes += [f'{bd}: {len(got)} cards' + (f' ({note})' if note else '')]
    if '--save' in a:
        json.dump(cards, open(a[a.index('--save') + 1], 'w'), ensure_ascii=False, indent=1)
    ids, pairs = known(rows)
    new = to_rows(pick_new(cards, ids, pairs), rows, dt.date.today().isoformat())
    print(f"{len(cards)} cards · {len(new)} new · {' · '.join(notes)}")
    if '--write' not in a:
        for n in new:
            print(' ', n['source'], n['level'][:8], n['company'][:24], '|', n['title'][:60], '|', n['location'][:30], '|', n.get('visa', ''))
        return
    store.save('jobs', rows + new)
    print(f'appended {len(new)} rows to data/store/jobs.jsonl (run the gate next)')


if __name__ == '__main__':
    main(sys.argv[1:])
