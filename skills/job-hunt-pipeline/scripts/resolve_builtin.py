#!/usr/bin/env python3
"""Built In job → the company's own application URL, without a Built In login (JSA-004).

Built In hides the apply link from anonymous visitors ("Log In to apply"; `applyUrl` is empty), and logging in would need
Joey's password. So: read the posting's schema.org JobPosting (title + company), find the company's Greenhouse / Lever /
Ashby board (tokens already seen in data/store/jobs.jsonl for that company, then slug guesses of the name), list the board
through its public API and take the posting whose title matches. No match = None with the reason; never a guess.

    python3 resolve_builtin.py https://builtin.com/job/<slug>/<id>
    python3 resolve_builtin.py --all [--limit N] [--write]   # 可投 / 待核实 Built In rows, ~1.5 s each; --write stores ats_url / ats_resolved
    python3 resolve_builtin.py --all --chrome [--write]      # same, read in the job Chrome after Joey logged in to Built In there
"""
import json, os, re, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'}
BOARD_RX = [('greenhouse', r'greenhouse\.io/(?:embed/job_app\?for=|v1/boards/)?([\w-]+)'), ('lever', r'jobs\.(?:eu\.)?lever\.co/([\w.-]+)'),
            ('ashby', r'jobs\.ashbyhq\.com/([^/?#]+)')]
STOP = {'the', 'a', 'an', 'and', 'of', 'for', 'in', 'to', '-', 'u', 's', 'us', 'usa'}
SUFFIX = re.compile(r'\b(inc|llc|corp|corporation|co|company|ltd|group|technologies|technology|holdings|labs?)\b\.?', re.I)


def get(url, timeout=25, tries=4):
    """GET with backoff on 429 / 5xx (Built In throttles bursts: 2026-10-30 a 2-worker run got 400+ HTTP errors)."""
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or n == tries - 1:
                raise
            time.sleep(int(e.headers.get('Retry-After') or 0) or 8 * (n + 1))
    raise RuntimeError('unreachable')


def posting_of(page):
    """(title, company) from the Built In page's JobPosting JSON-LD (Built In escapes the type as ld&#x2B;json)."""
    for m in re.finditer(r'<script[^>]+type="application/ld(?:\+|&#x2B;)json"[^>]*>(.*?)</script>', page, re.S):
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue
        for x in (d.get('@graph') if isinstance(d, dict) and '@graph' in d else [d]):
            if isinstance(x, dict) and x.get('@type') == 'JobPosting':
                org = x.get('hiringOrganization') or {}
                return x.get('title', ''), (org.get('name') if isinstance(org, dict) else str(org)) or ''
    return None, None


def words(s):
    s = re.sub(r'[^a-z0-9 ]+', ' ', (s or '').lower())
    return {w for w in s.split() if w not in STOP}


def similarity(a, b):
    A, B = words(a), words(b)
    return len(A & B) / max(1, len(A | B))


def company_key(name):
    return ' '.join(SUFFIX.sub(' ', re.sub(r'[^a-z0-9& ]+', ' ', (name or '').lower())).split())


def known_boards(jobs):
    """company key → [(ats, token)] from every row whose URL is a Greenhouse / Lever / Ashby posting."""
    out = {}
    for j in jobs:
        for ats, rx in BOARD_RX:
            m = re.search(rx, j.get('url') or '')
            if m and m.group(1) not in ('embed', 'jobs'):
                lst = out.setdefault(company_key(j.get('company')), [])
                if (ats, m.group(1)) not in lst:
                    lst.append((ats, m.group(1)))
    return out


def guesses(company):
    k = company_key(company)
    base = [k.replace(' ', ''), k.replace(' ', '-'), k.split()[0] if k else '']
    return [(ats, t) for t in dict.fromkeys(x for x in base if x) for ats in ('greenhouse', 'lever', 'ashby')]


def board_postings(ats, token):
    """[(title, url)] of one board; [] when the board does not exist."""
    try:
        if ats == 'greenhouse':
            d = json.loads(get(f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs'))
            # the board URL (not absolute_url, which may be a company page with ?gh_jid=) — plan_build reads it directly
            return [(j['title'], f'https://job-boards.greenhouse.io/{token}/jobs/{j["id"]}') for j in d.get('jobs', [])]
        if ats == 'lever':
            d = json.loads(get(f'https://api.lever.co/v0/postings/{token}?mode=json'))
            return [(j['text'], j['hostedUrl']) for j in d] if isinstance(d, list) else []
        if ats == 'ashby':
            d = json.loads(get(f'https://api.ashbyhq.com/posting-api/job-board/{token}'))
            return [(j['title'], j['jobUrl']) for j in d.get('jobs', [])]
    except Exception:
        return []
    return []


def best_match(title, postings, floor=0.75):
    scored = sorted(((similarity(title, t), t, u) for t, u in postings), reverse=True)
    if not scored or scored[0][0] < floor:
        return None
    if len(scored) > 1 and scored[1][0] == scored[0][0] and scored[1][2] != scored[0][2]:
        return None                                   # two equally good postings (several cities) → do not guess
    return scored[0]


TRACKING = re.compile(r'^(iisn|iis|utm_[a-z]+|source|src|gh_src)$', re.I)


def clean(url):
    """Drop tracking parameters (Built In adds iisn / iis; utm_*), keep everything the form needs."""
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k)]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))


def resolve(builtin_url, boards, page=None, follow=None):
    """→ dict(ats_url, ats, title, matched_title, score, how) or dict(error=…).
    follow(url) → final URL: the logged-in job Chrome opens Built In's ApplyRedirect (navigation only, nothing sent)."""
    try:
        page = page if page is not None else get(builtin_url)
    except Exception as e:
        return {'error': f'Built In page unreadable ({type(e).__name__})'}
    m = re.search(r'"applyUrl":"([^"]+)"', page)
    if m and m.group(1).startswith('http') and 'builtin.com' not in m.group(1):
        return {'ats_url': clean(m.group(1).replace('\\/', '/')), 'ats': 'page', 'how': 'applyUrl on the page'}
    if m and 'ApplyRedirect' in m.group(1) and follow:      # logged in: Built In's own redirect to the company form
        try:
            final = follow('https://builtin.com' + m.group(1) if m.group(1).startswith('/') else m.group(1))
        except Exception as e:
            final = ''
        if final.startswith('http') and 'builtin.com' not in final:
            return {'ats_url': clean(final), 'ats': 'redirect', 'how': 'Built In apply redirect (logged in)'}
    title, company = posting_of(page)
    if not title:
        return {'error': 'no JobPosting data on the Built In page'}
    cands = boards.get(company_key(company), []) + [g for g in guesses(company) if g not in boards.get(company_key(company), [])]
    tried = []
    for ats, token in cands:
        posts = board_postings(ats, token)
        tried.append(f'{ats}:{token}({len(posts)})')
        hit = best_match(title, posts)
        if hit:
            return {'ats_url': hit[2], 'ats': ats, 'title': title, 'matched_title': hit[1], 'score': round(hit[0], 2),
                    'how': f'{ats} board "{token}"', 'company': company}
    return {'error': f'no matching posting for "{title}" at {company}', 'tried': tried[:8], 'company': company}


class ChromeReader:
    """Reads Built In pages in the job Chrome (CDP 9222). Joey logs in to Built In there once by hand — the login form has
    a reCAPTCHA Enterprise bot check, which an agent never passes for him (decisions-log 2026-10-30). Logged in, the page's
    Builtin.jobPostInit carries the real applyUrl."""
    def __init__(self, cdp='http://127.0.0.1:9222'):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.ctx = self.pw.chromium.connect_over_cdp(cdp).contexts[0]
        self.page = self.ctx.new_page()

    def __call__(self, url):
        self.page.goto(url, wait_until='domcontentloaded', timeout=45000)
        self.page.wait_for_timeout(1500)
        html = self.page.content()
        if 'Log In to apply' in self.page.inner_text('body'):
            raise PermissionError('not logged in to Built In in the job Chrome — Joey logs in once by hand')
        return html

    def follow(self, url):
        self.page.goto(url, wait_until='domcontentloaded', timeout=45000)
        self.page.wait_for_timeout(2000)
        return self.page.url

    def close(self):
        try: self.page.close(); self.pw.stop()
        except Exception: pass


def main(a):
    import store
    jobs = store.load('jobs')
    boards = known_boards(jobs)
    if '--all' not in a:
        print(json.dumps(resolve(a[0], boards), ensure_ascii=False, indent=1)); return 0
    rows = [j for j in jobs if 'builtin.com/job/' in (j.get('url') or '') and j.get('elig') in ('可投', '待核实')]
    if '--limit' in a:
        rows = rows[:int(a[a.index('--limit') + 1])]
    if '--chrome' in a:                                # Joey logged in to Built In in the job Chrome: read applyUrl there
        cr, res = ChromeReader(), {}
        try:
            for j in rows:
                try:
                    res[j['id']] = resolve(j['url'], boards, page=cr(j['url']), follow=cr.follow)
                except PermissionError as e:
                    print(str(e)); break
                time.sleep(1.5)
        finally:
            cr.close()
    else:
        def one(j):
            time.sleep(1.5)                            # one request every ~1.5 s: Built In throttles bursts
            return j['id'], resolve(j['url'], boards)
        with ThreadPoolExecutor(1) as ex:
            res = dict(ex.map(one, rows))
    ok = {k: v for k, v in res.items() if v.get('ats_url')}
    for k, v in res.items():
        print(k, '→', v.get('ats_url') or ('— ' + v['error']))
    print(f'resolved {len(ok)} of {len(rows)} Built In rows')
    if '--write' in a and ok:
        for j in jobs:
            if j['id'] in ok:
                j['ats_url'], j['ats_resolved'] = ok[j['id']]['ats_url'], ok[j['id']]['how']
        store.save('jobs', jobs)
        print('written: ats_url / ats_resolved')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
