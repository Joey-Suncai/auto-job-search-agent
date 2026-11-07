#!/usr/bin/env python3
"""Wellfound internship search as a weekly source (2026-11-03, JSA-108: signed-in sample 903 cards → 499 relevant, 48 % in the store).

Runs in the job Chrome (CDP 9222, Joey's weekly full refresh — never from a LaunchAgent), where Joey is signed in to
Wellfound. The saved search keeps his roles and locations (PM / DS / DA / BA / DE / MLE; Chicago + United States); the
script only sets the job type: Internship on, Full Time off, "sponsor a visa" off (that flag is per company and leaves 0
internships). Then it scrolls /jobs and reads every `a[href*="/jobs/<id>"]` card; no job page is opened. A sign-in page,
CAPTCHA or "verify you are human" page stops the run and is reported — never solved or worked around.
Kept: the same rules as indeed_search.py (his tracks, not senior, in the U.S., a Summer 2027 internship or a 2027/2028
new-grad title). Dropped: rows already in the store (same Wellfound job id, or same normalised company + title), at most
2 per company. New rows: `source` = wellfound_search, `url` = the Wellfound job page; the gate and `resolve_careers.py`
then find the company's own posting.
usage: python3 wellfound_search.py [--write] [--json <saved cards .json> | --save <cards .json>]   (without --write: print counts only)
Tests (rule 13): scripts/test_wellfound_search.py with DeepSeek cases.
"""
import html, json, os, re, sys, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
from indeed_search import norm, title_key, keep_card, level_of, BLOCK  # noqa: E402

CARDS_JS = """() => [...document.querySelectorAll('a[href*="/jobs/"]')].filter(a => /\\/jobs\\/\\d+/.test(a.getAttribute('href')) && a.innerText.trim()).map(a => {
  let c = a, co = ''; for (let i = 0; i < 12 && c && !co; i++) { c = c.parentElement; const h = c && c.querySelector('h2'); if (h) co = h.innerText; }
  const parts = [], w = document.createTreeWalker(a, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) { const t = n.textContent.trim(); if (t) parts.push(t); }
  return {href: a.getAttribute('href'), text: a.innerText.trim(), parts: parts, company: co}; })"""
WORK = re.compile(r'^(in office|remote|hybrid|onsite|on-site)\s*', re.I)
CUT = re.compile(r'\$|no equity|\d+(\.\d+)?\s*%|€|£', re.I)      # salary / equity glued after the city
UNITS = {'minute': 0, 'hour': 0, 'day': 1, 'week': 7, 'month': 30, 'year': 365}


def job_id(href):
    """Pure (tested). '/jobs/4897782-research-engineer-intern' or a full wellfound.com URL → '4897782' ('' if none)."""
    m = re.search(r'(?:^|wellfound\.com)/jobs/(\d+)', str(href or ''))
    return m.group(1) if m else ''


def posted_date(text, today):
    """Pure (tested). 'POSTED 6 DAYS AGO' / 'Posted 1 month ago' / 'POSTED TODAY' → ISO date relative to `today`
    (a date); a month = 30 days, a year = 365; '' when the text has no such phrase."""
    t = str(text or '').lower()
    if re.search(r'\bposted (today|just now)\b', t):
        return today.isoformat()
    if re.search(r'\bposted yesterday\b', t):
        return (today - dt.timedelta(days=1)).isoformat()
    m = re.search(r'\bposted (\d+|an?|one) (minute|hour|day|week|month|year)s? ago\b', t)
    if not m:
        return ''
    n = 1 if m.group(1) in ('a', 'an', 'one') else int(m.group(1))
    return (today - dt.timedelta(days=n * UNITS[m.group(2)])).isoformat()


def parse_card(rec, today):
    """Pure (tested). One card {'href', 'text', 'company', optional 'parts'} → {'job_id', 'company', 'title', 'location',
    'posted', 'url'}, or None when there is no job id, title or company.
    `parts` (the card's text nodes, one per element) is preferred: title, work mode ("In office" / "Remote" / "Hybrid"),
    one or more cities, salary / equity ("$100k – $110k", "No equity", "0.5% – 1%"), badges ("RECRUITER RECENTLY
    ACTIVE"), "POSTED … AGO"; several cities are joined with "; ". Without `parts`, `text` lines are used: title, then
    the glued work-mode + city line ("In officeNew York City$100k – $110k"), badges, then "POSTED … AGO"."""
    jid = job_id(rec.get('href'))
    parts = [html.unescape(str(x)).strip() for x in (rec.get('parts') or []) if str(x).strip()]
    lines = parts or [x.strip() for x in html.unescape(str(rec.get('text') or '')).split('\n') if x.strip()]
    company = html.unescape(str(rec.get('company') or '')).strip()
    if not jid or not lines or not company:
        return None
    locs, posted, remote = [], '', False
    for x in lines[1:]:
        if x.lower().startswith('posted'):
            posted = posted_date(x, today)
            continue
        if x.isupper() and ' ' in x:                              # badge
            continue
        mode = WORK.match(x)
        if mode:
            remote = remote or mode.group(1).lower() == 'remote'
            x = x[mode.end():]
        x = CUT.split(x, 1)[0].strip()
        if x and (parts or not locs):
            locs.append(x)
    loc = '; '.join(dict.fromkeys(locs)) or ('Remote' if remote else '')
    href = str(rec.get('href'))
    url = href if href.startswith('http') else 'https://wellfound.com' + href
    return {'job_id': jid, 'company': company, 'title': lines[0], 'location': loc, 'posted': posted, 'url': url.split('?')[0]}


def known(rows):
    """Pure (tested). Store rows → (Wellfound job ids, {(norm company, title_key)})."""
    ids, pairs = set(), set()
    for r in rows:
        for u in (r.get('url'), r.get('ats_url')):
            if 'wellfound.com' in str(u or '') and job_id(u):
                ids.add(job_id(u))
        pairs.add((norm(r.get('company')), title_key(r.get('title'))))
    return ids, pairs


def pick_new(cards, ids, pairs):
    """Pure (tested). Parsed cards → kept, not in the store, no repeats, at most 2 per company (page order kept)."""
    ids, pairs, per, new = set(ids), set(pairs), {}, []
    for c in cards:
        p = (norm(c['company']), title_key(c['title']))
        if c['job_id'] in ids or p in pairs or not keep_card(c['title'], c['location']):
            continue
        if per.get(p[0], 0) >= 2:
            continue
        per[p[0]] = per.get(p[0], 0) + 1; ids.add(c['job_id']); pairs.add(p)
        new.append(c)
    return new


def to_rows(new, rows, today):
    """Pure. New cards → store rows with the next free J-ids after `rows`."""
    nid = max([int(re.sub(r'\D', '', r['id']) or 0) for r in rows if str(r.get('id', '')).startswith('J')] or [0]) + 1
    out = []
    for n in new:
        out.append({'id': f'J{nid:05d}', 'company': n['company'], 'title': n['title'], 'location': n['location'],
                    'url': n['url'], 'tier': 'C', 'score': 45, 'score_note': 'wellfound_search default (tier median)',
                    'level': level_of(n['title']), 'added': today, 'source': 'wellfound_search', 'posted': n['posted']})
        nid += 1
    return out


def _checked(pg, label):
    return pg.get_by_text(label, exact=True).last.evaluate(
        "e => { const i = (e.htmlFor && document.getElementById(e.htmlFor)) || (e.closest('label') || e.parentElement).querySelector('input'); return i ? i.checked : null }")


def fetch_cards(cdp='http://127.0.0.1:9222', max_links=2500):
    """Network. One new tab in the job Chrome → (raw cards, note). Stops at a sign-in or challenge page."""
    from playwright.sync_api import sync_playwright
    want = {'Internship': True, 'Full Time': False, 'Only show companies that can sponsor a visa': False}
    cards, note = [], ''
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(cdp).contexts[0]
        pg = ctx.new_page(); pg.set_viewport_size({'width': 1300, 'height': 900})
        try:
            pg.goto('https://wellfound.com/jobs', wait_until='load', timeout=90000); pg.wait_for_timeout(6000)
            body = pg.inner_text('body')[:3000]
            if re.search(r'/login|/profile/edit|/onboarding', pg.url) or BLOCK.search(pg.title()) or (len(body) < 1500 and BLOCK.search(body)):
                return [], f'stopped at {pg.url} (sign-in / onboarding / challenge) — nothing solved'
            pg.locator('[data-test=SearchBar-ToggleFilterControlPanelButton]').click(); pg.wait_for_timeout(2500)
            for lab, on in want.items():
                if _checked(pg, lab) is not on:
                    pg.get_by_text(lab, exact=True).last.click(); pg.wait_for_timeout(1500)
            bad = [lab for lab, on in want.items() if _checked(pg, lab) is not on]
            if bad:
                return [], f'job-type filter did not stick: {bad} — stopped'
            pg.get_by_text('View results', exact=True).click(); pg.wait_for_timeout(5000)
            m = re.search(r'([\d,]+) results', pg.inner_text('body'))
            search = pg.locator('[data-test=SearchBar]').inner_text().replace('\n', ' | ')
            last, same = -1, 0
            for _ in range(250):
                pg.mouse.wheel(0, 5000); pg.wait_for_timeout(2000)
                n = pg.evaluate("() => document.querySelectorAll('a[href*=\"/jobs/\"]').length")
                same = same + 1 if n == last else 0; last = n
                if same >= 4 or n > max_links:
                    break
            if BLOCK.search(pg.title()):
                note = 'challenge page while scrolling — kept the cards read so far'
            cards = pg.evaluate(CARDS_JS)
            note = (note + ' · ' if note else '') + f"{m.group(1) if m else '?'} results · search: {search[:160]}"
        finally:
            pg.close()
    return cards, note


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    rows = store.load('jobs')
    today = dt.date.today()
    if '--json' in a:                       # saved sampler output: {"jobs": [{href, title(text), company}]} or a list
        d = json.load(open(a[a.index('--json') + 1]))
        raw = [{'href': j['href'], 'text': j.get('text') or j.get('title'), 'parts': j.get('parts'), 'company': j.get('company')} for j in (d.get('jobs') if isinstance(d, dict) else d)]
        note = 'saved cards'
    else:
        raw, note = fetch_cards()
        if '--save' in a:
            json.dump({'jobs': raw, 'note': note}, open(a[a.index('--save') + 1], 'w'), indent=1)
    seen, cards = set(), []
    for r in raw:
        c = parse_card(r, today)
        if c and c['job_id'] not in seen:
            seen.add(c['job_id']); cards.append(c)
    ids, pairs = known(rows)
    kept = [c for c in cards if keep_card(c['title'], c['location'])]
    new = to_rows(pick_new(cards, ids, pairs), rows, today.isoformat())
    print(f'{len(raw)} links · {len(cards)} cards · {len(kept)} kept · {len(new)} new' + (f' · {note}' if note else ''))
    if '--write' not in a:
        for n in new:
            print(' ', n['level'][:8], n['company'][:24], '|', n['title'][:60], '|', n['location'][:24])
        return
    store.save('jobs', rows + new)
    print(f'appended {len(new)} rows to data/store/jobs.jsonl (run the gate next)')


if __name__ == '__main__':
    main(sys.argv[1:])
