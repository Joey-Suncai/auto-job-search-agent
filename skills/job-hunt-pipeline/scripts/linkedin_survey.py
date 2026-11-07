#!/usr/bin/env python3
"""LinkedIn Easy Apply survey (JSA-176, 2026-11-05): of the U.S. internships that match Joey's tracks, what share is
LinkedIn Easy Apply (applied inside LinkedIn) and what share is "Apply" (goes to the company's site)?

Read-only, in the job Chrome (CDP 9222, Joey signed in). One tab of its own (closed at the end; other tabs untouched):
  1. per keyword: the U.S. internship search (geoId 103644278, f_E=1, posted any time) once without and once with the
     Easy Apply filter (f_AL=true) → the two "N results" counts; the cards of the unfiltered page also say "Easy Apply"
     or not (the list is scrolled, never clicked);
  2. a round-robin sample of the unfiltered cards → each job page (/jobs/view/<id>/) is loaded and its apply control is
     read: "Easy Apply" / "Apply" (external; the link target only when it is in the DOM).
Never clicks, types, saves, follows or applies. 8–15 s between page loads, at most MAX_LOADS loads. A sign-in page, a
security check / CAPTCHA or "unusual activity" stops the run at once (exit 3) — nothing is solved or signed in.
  3. optional `--extra <wellfound method B .json>`: LinkedIn job pages that the Wellfound rows actually open
     (pages[].opened → /jobs/view/<id>) — a random `--extra-n` of them join the sample as their own group.
usage: ~/.job-agent-venv/bin/python linkedin_survey.py --out <survey.json> [--sample 10] [--extra <json> --extra-n 10]
                                   [--seed 176] [--max-loads 40] [--cdp http://127.0.0.1:9222]
       python3 linkedin_survey.py --summary <survey.json>      (offline: print the tables for the report)
Tests (rule 13): scripts/test_linkedin_survey.py with DeepSeek cases (scripts/test_cases/linkedin_survey_*).
"""
import json, math, os, random, re, sys, time, datetime as dt, urllib.parse

KEYWORDS = ["data engineer intern", "data analyst intern", "business intelligence intern", "product manager intern",
            "AI product manager intern", "product analyst intern", "machine learning engineer intern", "AI engineer intern",
            "data scientist intern"]
STARTS = (0, 25)   # two result pages per keyword (25 cards each)
GEO_US = '103644278'
MAX_LOADS = 40
PAUSE = (8, 15)
SIGNIN = re.compile(r'linkedin\.com/(login|authwall|checkpoint|uas/|signup)', re.I)
BLOCK = re.compile(r'verify you are human|are you a robot|security check|captcha|unusual (activity|traffic)|'
                   r'press (and|&) hold|restricted your account|access denied', re.I)
NOTICE = re.compile(r"you(?:'|’)ve reached [^.\n]{0,60}limit|too many requests|try again later|premium[^.\n]{0,40}"
                    r"(?:to see|unlock)", re.I)


# ---------- pure helpers (tested) ----------
def search_url(keyword, easy=False, start=0):
    """Pure (tested). LinkedIn job search (new UI path /jobs/search-results/): U.S. (geoId), posted any time; f_AL=true
    only when `easy`; start only when > 0. No f_E: the new UI drops it (seen 2026-11-05), so "intern" goes in keywords."""
    q = [('keywords', keyword), ('geoId', GEO_US)]
    if easy:
        q.append(('f_AL', 'true'))
    if start and start > 0:
        q.append(('start', str(int(start))))
    return 'https://www.linkedin.com/jobs/search-results/?' + urllib.parse.urlencode(q)


COUNT = re.compile(r'(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kK])?\s*\+?\s*results?\b', re.I)


def parse_count(text):
    """Pure (tested). The first "<number>[K][+] result(s)" in `text` → int; "No matching jobs found" → 0; else None."""
    t = str(text or '')
    m = COUNT.search(t)
    if m:
        n = float(m.group(1).replace(',', ''))
        if m.group(2):
            n *= 1000
        return int(math.floor(n + 0.5))
    if re.search(r'no matching jobs found', t, re.I):
        return 0
    return None


def classify_button(text):
    """Pure (tested). Apply-control text / aria-label → 'easy' | 'external' | 'unknown' (rules in the spec, in order)."""
    t = re.sub(r'\s+', ' ', str(text or '')).strip().lower()
    if 'easy apply' in t:
        return 'easy'
    if re.search(r'applied|application submitted|no longer accepting', t):
        return 'unknown'
    if re.search(r'\bapply\b', t):
        return 'external'
    return 'unknown'


def _host(u):
    try:
        p = urllib.parse.urlsplit(str(u or '').strip())
    except ValueError:
        return ''
    if p.scheme.lower() not in ('http', 'https') or not p.hostname:
        return ''
    h = p.hostname.lower()
    return h[4:] if h.startswith('www.') else h


def link_target(href):
    """Pure (tested). Apply-link href → destination host (lowercase, no www.); LinkedIn redirects decoded; other
    linkedin.com links → 'linkedin'; relative / empty / non-http → ''."""
    h = _host(href)
    if not h:
        return ''
    if h == 'linkedin.com' or h.endswith('.linkedin.com'):
        p = urllib.parse.urlsplit(str(href).strip())
        if h == 'linkedin.com' and re.match(r'/(redir/redirect|safety/go)', p.path):
            u = urllib.parse.parse_qs(p.query).get('url')
            if u:
                return _host(u[0])
        return 'linkedin'
    return h


def card_easy(lines):
    """Pure (tested). A search card's text lines → True when one line is exactly "Easy Apply" (case-insensitive)."""
    return any(str(x).strip().lower() == 'easy apply' for x in lines or [])


def card_title(lines):
    """Pure (tested). Card lines → the job title: the first line without a trailing "(Verified job)"; "" for no lines."""
    lines = [str(x).strip() for x in lines or [] if str(x).strip()]
    return re.sub(r'\s*\(verified job\)\s*$', '', lines[0], flags=re.I).strip() if lines else ''


def intern_title(title):
    """Pure (tested). True when the title has the whole word intern / interns / internship / internships / co-op / coop."""
    return bool(re.search(r'\b(intern|interns|internship|internships|co-op|coop)\b', str(title or ''), re.I))


def pick_sample(groups, n):
    """Pure (tested). [[keyword, [ids]], …] → up to n ids, round-robin over the groups, repeats skipped."""
    out, seen = [], set()
    if not n or n <= 0:
        return out
    lists = [list(g[1] or []) for g in groups]
    for i in range(max([len(x) for x in lists] or [0])):
        for ids in lists:
            if i < len(ids) and ids[i] not in seen:
                seen.add(ids[i]); out.append(ids[i])
                if len(out) >= n:
                    return out
    return out


def share(part, total):
    """Pure (tested). part / total to 3 decimals; None when total is 0 / None or part is None."""
    if part is None or not total:
        return None
    return round(part / total, 3)


def wellfound_linkedin(path):
    """Wellfound method B pages → [{'job_id', 'row_id', 'title'}] for the pages that opened a LinkedIn job page."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from linkedin_search import job_id
    out, seen = [], set()
    for pg in json.load(open(path)).get('pages') or []:
        for u in pg.get('opened') or []:
            j = job_id(u)
            if j and j not in seen:
                seen.add(j); out.append({'job_id': j, 'row_id': pg.get('id'), 'title': (pg.get('title') or '')[:90]})
                break
    return out


# ---------- browser (live) ----------
CARDS_JS = """() => {
  const els = [...document.querySelectorAll('[componentkey^="job-card-component-ref-"], li[data-occludable-job-id], [data-job-id]')];
  const seen = new Set(), out = [];
  for (const e of els) {
    let id = e.getAttribute('data-occludable-job-id') || e.getAttribute('data-job-id') ||
             (e.getAttribute('componentkey') || '').replace('job-card-component-ref-', '');
    id = (id || '').replace(/\\D/g, '');
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push({id, lines: e.innerText.split('\\n').map(s => s.trim()).filter(Boolean).slice(0, 14)});
  }
  return out;
}"""
SCROLL_JS = """() => { const c = document.querySelectorAll('[componentkey^="job-card-component-ref-"], li[data-occludable-job-id]');
  if (c.length) c[c.length - 1].scrollIntoView(); return c.length; }"""
APPLY_JS = """() => {
  const out = [];
  for (const e of document.querySelectorAll('button, a')) {
    const t = (e.innerText || '').trim().replace(/\\s+/g, ' ');
    const al = e.getAttribute('aria-label') || '';
    if (t.length > 80) continue;
    if (!/\\bapply\\b|applied|no longer accepting/i.test(t + ' ' + al)) continue;
    const r = e.getBoundingClientRect();
    out.push({tag: e.tagName, text: t, aria: al.slice(0, 160), href: (e.getAttribute('href') || '').slice(0, 600),
              cls: (e.className && e.className.baseVal === undefined ? e.className : '').slice(0, 120),
              visible: r.width > 0 && r.height > 0});
    if (out.length >= 12) break;
  }
  const body = document.body ? document.body.innerText : '';
  return {controls: out, closed: /no longer accepting applications/i.test(body), head: body.slice(0, 600)};
}"""


def decide(controls):
    """First visible control (DOM order) that classifies as easy / external decides; else unknown."""
    for want_visible in (True, False):
        for c in controls:
            if want_visible and not c.get('visible'):
                continue
            k = classify_button(c.get('text') or '')
            if k == 'unknown':
                k = classify_button(c.get('aria') or '')
            if k != 'unknown':
                return k, (link_target(c.get('href')) if k == 'external' else ''), c
    return 'unknown', '', None


class Stop(Exception):
    pass


def run(out_path, sample_n=10, cdp='http://127.0.0.1:9222', extra=None, extra_n=10, seed=176):
    from playwright.sync_api import sync_playwright
    res = {'started': dt.datetime.now().isoformat(timespec='seconds'), 'keywords': [], 'sample': [], 'events': [],
           'loads': 0, 'stopped': ''}

    def save():
        res['finished'] = dt.datetime.now().isoformat(timespec='seconds')
        json.dump(res, open(out_path, 'w'), indent=1, ensure_ascii=False)

    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(cdp).contexts[0]
        pg = ctx.new_page(); pg.set_viewport_size({'width': 1300, 'height': 900})

        def load(url):
            if res['loads'] >= MAX_LOADS:
                raise Stop(f'page-load budget {MAX_LOADS} reached')
            if res['loads']:
                time.sleep(random.uniform(*PAUSE))
            res['loads'] += 1
            pg.goto(url, wait_until='domcontentloaded', timeout=60000)
            pg.wait_for_timeout(4500)
            body = pg.inner_text('body')[:4000]
            title = pg.title()
            if SIGNIN.search(pg.url) or (re.search(r'\bjoin now\b', body[:800], re.I) and re.search(r'\bsign in\b', body[:800], re.I)):
                raise Stop(f'sign-in page at {pg.url[:140]}')
            if BLOCK.search(title) or (len(body) < 1500 and BLOCK.search(body)) or re.search(r'unusual activity|quick security check|complete (?:a|this) security check', body[:2000], re.I):
                raise Stop(f'security check / unusual activity at {pg.url[:140]} (title "{title[:80]}")')
            if (m := NOTICE.search(body)):
                res['events'].append({'url': pg.url[:200], 'notice': m.group(0)})
            return body

        def cards():
            last, same = -1, 0
            for _ in range(8):
                n = pg.evaluate(SCROLL_JS)
                same = same + 1 if n == last else 0; last = n
                if same >= 2:
                    break
                pg.wait_for_timeout(1200)
            return pg.evaluate(CARDS_JS)

        try:
            for kw in KEYWORDS:
                row = {'keyword': kw, 'pages': []}
                for st in STARTS:
                    u = search_url(kw, False, st)
                    body = load(u)
                    m = COUNT.search(body)
                    cs = cards()
                    row['pages'].append({'url': u, 'final_url': pg.url[:300], 'count': parse_count(body),
                                         'count_text': body[max(0, m.start() - 10):m.end()] if m else '',
                                         'cards': [{'id': c['id'], 'lines': c['lines'][:4], 'title': card_title(c['lines']),
                                                    'intern': intern_title(card_title(c['lines'])), 'easy': card_easy(c['lines'])}
                                                   for c in cs]})
                    if not cs:
                        row['pages'][-1]['head'] = body[:800]
                    save()
                    if len(cs) < 20:
                        break
                seen, allc = set(), []
                for pgd in row['pages']:
                    for c in pgd['cards']:
                        if c['id'] not in seen:
                            seen.add(c['id']); allc.append(c)
                row['cards'] = allc
                res['keywords'].append(row)
                if len(res['keywords']) == 1 and not allc:
                    raise Stop('first search page shows no cards — page layout not understood (see head)')
                save()
                it = [c for c in allc if c['intern']]
                print(f"{kw}: cards {len(allc)} (Easy Apply {sum(c['easy'] for c in allc)}) · intern titles {len(it)}"
                      f" (Easy Apply {sum(c['easy'] for c in it)})", flush=True)
            groups = [[r['keyword'], [c['id'] for c in r['cards'] if c['intern']]] for r in res['keywords']]
            meta = {c['id']: (r['keyword'], c) for r in res['keywords'] for c in r['cards']}
            todo = [('search', j) for j in pick_sample(groups, sample_n)]
            if extra:
                pool = wellfound_linkedin(extra)
                res['wellfound_pool'] = len(pool)
                ex = random.Random(seed).sample(pool, min(extra_n, len(pool)))
                taken = {j for _, j in todo}
                for e in ex:
                    if e['job_id'] not in taken:
                        todo.append(('wellfound', e['job_id']))
                        meta[e['job_id']] = (f"wellfound {e['row_id']}", {'lines': [e['title'], '', ''], 'easy': None})
                # interleave the two groups so a stop part-way leaves both represented
                a1, a2 = [t for t in todo if t[0] == 'search'], [t for t in todo if t[0] == 'wellfound']
                todo = [t for pair in zip(a1, a2) for t in pair] + a1[len(a2):] + a2[len(a1):]
            for grp, jid in todo:
                load(f'https://www.linkedin.com/jobs/view/{jid}/')
                try:
                    pg.wait_for_selector('.jobs-apply-button, button[aria-label*="pply"], a[aria-label*="pply"]', timeout=6000)
                except Exception:
                    pass
                info = pg.evaluate(APPLY_JS)
                kind, target, ctl = decide(info['controls'])
                kw, c = meta[jid]
                res['sample'].append({'id': jid, 'group': grp, 'keyword': kw, 'card': c['lines'][:3], 'card_easy': c['easy'],
                                      'final_url': pg.url[:300], 'kind': kind, 'target': target,
                                      'control': ctl, 'controls': info['controls'], 'closed': info['closed'],
                                      'head': '' if ctl else info['head']})
                save()
                print(f"  {jid} {kind:8} {target:28} {' | '.join(c['lines'][:2])[:70]}", flush=True)
        except Stop as e:
            res['stopped'] = str(e)
            print('STOPPED:', e, flush=True)
        finally:
            save()
            try:
                pg.close()
            except Exception:
                pass
    return res


def summary(res):
    lines = ['| Keyword | Cards read | "Easy Apply" on card | share | Intern-titled cards | of them Easy Apply | share |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    uniq = {}
    for r in res['keywords']:
        cs = r.get('cards') or []
        it = [c for c in cs if c.get('intern')]
        for c in cs:
            uniq.setdefault(c['id'], c)
        ce, ie = sum(c['easy'] for c in cs), sum(c['easy'] for c in it)
        lines.append(f"| {r['keyword']} | {len(cs)} | {ce} | {share(ce, len(cs))} | {len(it)} | {ie} | {share(ie, len(it))} |")
    u = list(uniq.values()); ui = [c for c in u if c.get('intern')]
    ue, uie = sum(c['easy'] for c in u), sum(c['easy'] for c in ui)
    lines.append(f"| **all keywords, unique jobs** | {len(u)} | {ue} | {share(ue, len(u))} | {len(ui)} | {uie} | {share(uie, len(ui))} |")
    s = res['sample']
    lines.append('')
    for g in ('all', 'search', 'wellfound'):
        gs = [y for y in s if g == 'all' or y.get('group', 'search') == g]
        k = {x: sum(1 for y in gs if y['kind'] == x) for x in ('easy', 'external', 'unknown')}
        cl = sum(1 for y in gs if y.get('closed'))
        lines.append(f"Sample {g}: {len(gs)} job pages · easy {k['easy']} · external {k['external']} · unknown {k['unknown']}"
                     f" · 'no longer accepting' shown {cl}")
    lines += ['', '| # | Group | Keyword / row | Title | Company | Button | Target |', '| ---: | --- | --- | --- | --- | --- | --- |']
    for i, y in enumerate(s, 1):
        c = y['card'] + ['', '', '']
        t0 = re.sub(r'\s*\(verified job\)\s*$', '', c[0], flags=re.I)
        comp = c[2] if c[1] == t0 else c[1]
        ctl = (y.get('control') or {}).get('text') or ''
        lines.append(f"| {i} | {y.get('group', 'search')} | {y['keyword']} | {t0[:60]} | {comp[:30]} | {y['kind']} ({ctl[:30]})"
                     f"{' closed' if y.get('closed') else ''} | {y['target'] or '—'} |")
    return '\n'.join(lines)


def main(a):
    if '--summary' in a:
        print(summary(json.load(open(a[a.index('--summary') + 1])))); return
    if '--out' not in a:
        sys.exit(__doc__)
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    global MAX_LOADS
    MAX_LOADS = int(arg('--max-loads', MAX_LOADS))
    res = run(arg('--out', None), int(arg('--sample', 10)), arg('--cdp', 'http://127.0.0.1:9222'),
              arg('--extra', None), int(arg('--extra-n', 10)), int(arg('--seed', 176)))
    sys.exit(3 if res['stopped'] and 'budget' not in res['stopped'] else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
