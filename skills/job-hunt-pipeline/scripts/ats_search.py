#!/usr/bin/env python3
"""Posting search on the careers systems resolve_careers.py could only name (JSA-112, 2026-11-03).

resolve_careers.py finds a company's ATS from its own website; Workday / Greenhouse / Lever / Ashby were searchable,
every other system ended as `other_system`. This module adds a public, no-login posting list or search for the rest:

    postings(system, ident, query) → [{'title', 'location', 'url'}]      ([] = nothing found / not searchable)

One way to cover every system at once was checked first (2026-11-03): schema.org JobPosting JSON-LD sits on single
posting pages, not on lists, so it cannot find a posting; sitemaps / feeds exist only for some (Avature RSS,
SuccessFactors career sites); rendering and typing into each careers page is slow and different per site; a search
engine `site:` query needs a paid API or scraping behind a bot wall. So: one adapter per system, each a single public
JSON / HTML endpoint, plus one careers-site path (careers.<domain> / jobs.<domain>) that reads both SuccessFactors
career-site search pages and Phenom search pages (the two systems whose ident is only a CDN host).

Compared with kalil0321/ats-scrapers (MIT, commit 6b44a1b, 2026-11-03; see references/ats_search_2026-11-03.md): its
shape (one adapter per system behind a registry, one shared fetcher with retries / backoff / Retry-After) and several
endpoints are adapted here as plain urllib code — SuccessFactors /sitemal.xml, BambooHR /jobs/embed2.php, Avature
SearchJobs pages, Eightfold /api/apply/v2 fallback, UKG loadUrl check, Jobvite paging, Rippling v1 API, iCIMS paging
and its 'Job Locations' label, Teamtailor tt:location. Its TLS-impersonation (httpcloak), cloud-browser
(Browserbase / cloakbrowser) and proxy paths are NOT used: a wall is recorded, never bypassed.
Portions adapted from ats-scrapers: Copyright (c) 2026 Kalil Bouzigues, MIT License (notice in references/ats_search_2026-11-03.md).

ident = what resolve_careers' ATS_RX captured (host / slug), cleaned by clean_ident(); systems whose ident does not
name the company (successfactors, phenom, eightfold, teamtailor) carry the company site as `ident@site`
(with_site()). A security check / bot wall / 429 → that (system, ident) is skipped and recorded in NOTES, never
bypassed. Polite: ≥ 1 s between requests to one host. No LinkedIn / jobright page is ever fetched.

JSA-117 (2026-11-03): Dover (public careers-page JSON), Taleo Business Edition (`*.tbe.taleo.net` searchResults HTML),
Paycom's old `jobs?clientkey=` links (the key is the portal token), SuccessFactors `career4…/career?company=` links and
RMK career sites on their own host (`jobs.weill.cornell.edu`). Still without a search, and why: ADP Recruiting
Management `myjobs.adp.com/<slug>` (only the career-site config and one requisition by id are public; the list is
behind the app's own session), Teamtailor seen only as `www.` / `app.` / `cdn.teamtailor.com` (vendor links, not a
company board). live(system, ident) = does the board list anything now (JSA-119: confirms company-list hints).
JSA-137 (2026-11-04, Joey: 「把 GitHub 里面它的所有系统都搬进来。」): every remaining company system of ats-scrapers —
TikTok / TikTok USDS / ByteDance (one "ATSx" search API; USDS takes its page's anonymous CSRF token), Cornerstone (the
career page's anonymous token → keyword search), Gem (public GraphQL list), PageUp, Personio, Recruiterbox / Trakstar
Hire, Softgarden, join.com, Keka, Gupy, HRMOS, HERP, Beisen — and Eightfold / Avature career sites on the company's own
domain (apply.careers.microsoft.com, careers.ibm.com/en_US: custom_host). Moka (AES-wrapped list) and Darwinbox
(Cloudflare; ats-scrapers impersonates a browser) are only recorded. Job boards in ats-scrapers (Built In, Wellfound, YC,
Seek, USAJobs …) are not company systems and are not ported; Meta / Tesla / Uber stay refused (cloak browser / TLS).
Spec + DeepSeek-written cases: scripts/test_cases/ats_search_*; harness scripts/test_ats_search.py.
"""
import html as H, http.cookiejar, json, re, threading, time, urllib.error, urllib.parse, urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36',
      'Accept': 'application/json, text/html;q=0.9, */*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9'}
SYSTEMS = ('icims', 'oraclecloud', 'successfactors', 'taleo', 'smartrecruiters', 'workable', 'jobvite', 'bamboohr',
           'ultipro', 'eightfold', 'phenom', 'avature', 'jazzhr', 'rippling', 'breezy', 'recruitee', 'teamtailor', 'pinpoint',
           'adp', 'paycom', 'paylocity', 'dayforce', 'brassring', 'clearcompany',        # these six: Joey 「补上」 11-03
           'dover',                                                                      # JSA-117
           'applicantpro',                                                               # JSA-149 (2026-11-04)
           'amazon', 'apple', 'google',                    # big-tech career sites (JSA-133, 2026-11-03, after ats-scrapers)
           'tiktok', 'bytedance', 'cornerstone', 'gem', 'pageup', 'personio', 'recruiterbox', 'softgarden', 'join', 'keka',
           'gupy', 'hrmos', 'herp', 'beisen')             # the rest of ats-scrapers (JSA-137, 2026-11-04)
NEEDS_SITE = ('successfactors', 'phenom', 'eightfold', 'teamtailor')
LISTS = ('workable', 'jobvite', 'bamboohr', 'avature', 'jazzhr', 'rippling', 'breezy', 'recruitee', 'teamtailor', 'pinpoint', 'applicantpro',
         'paylocity', 'dayforce', 'dover', 'gem', 'pageup', 'personio', 'recruiterbox', 'softgarden', 'join', 'keka', 'gupy',
         'hrmos', 'herp')
NOTES = {}                       # (system, ident) → why it was skipped (security check …), for the report
CHALLENGE = re.compile(r'just a moment\.\.\.|cf-chl|challenge-platform|attention required|captcha|are you a robot|'
                       r'access denied|request unsuccessful|incapsula|perimeterx|px-captcha|distil_', re.I)
# hosts / slugs that are the vendor's own infrastructure, not a company board
JUNK = re.compile(r'^(?:www|i|login|cdn\d*|images?|assets?|static|cookie-policy-scripts|api|app|embed|cdn-cgi|job-api|'
                  r'de-de|en-us|en|careers|jobs|staticfe|assets-cdn|pp-cdn|content-us|vs-errors|rmkcdn|performancemanager\d*|'
                  r'hcm\d+|career\d*|apply|community|help|support|portal-oss)$', re.I)       # portal-oss.zhiye.com: Beisen CDN


def root_domain(host):
    """'www.careers.acme.co.uk' → 'acme.co.uk'; 'www.acme.com' → 'acme.com'; a URL is cut to its host."""
    h = (host or '').lower().strip()
    h = (urllib.parse.urlsplit(h if '//' in h else '//' + h).hostname or '') if h else ''      # a URL → its host
    p = h.strip('.').split('.')
    if len(p) >= 3 and p[-2] in ('co', 'com', 'org', 'ac', 'gov', 'net') and len(p[-1]) == 2:
        return '.'.join(p[-3:])
    return '.'.join(p[-2:])


def clean_ident(system, ident):
    """Pure. The board host / slug postings() can use, or None when the ident is vendor infrastructure or an
    employees-only site. Drops a stray '2f' (a URL-encoded '/' glued to the host) and any '@site'."""
    raw = re.sub(r'^2f(?=[a-z0-9-]+\.)', '', (ident or '').split('@')[0].strip().strip('/'), flags=re.I)
    i = raw.lower()
    if not i:
        return None
    if system == 'icims':
        m = re.fullmatch(r'([a-z0-9-]+)\.icims\.com', i)
        if not m or JUNK.match(m.group(1)) or re.search(r'employee|internal', m.group(1)):
            return None
        return i
    if system == 'oraclecloud':
        m = re.fullmatch(r'([a-z0-9-]+)\.fa\.[a-z0-9-]+\.oraclecloud\.com', i)
        return i if m and not re.search(r'-(?:dev|test|stage)\d*\b', m.group(1)) else None
    if system == 'taleo':
        tbe = tbe_ident(i)
        if tbe or '.tbe.taleo.net' in i or i.startswith('tbe.'):
            return tbe                                    # Taleo Business Edition: host/dir/ORG/cws, or nothing
        m = re.fullmatch(r'([a-z0-9-]+)\.taleo\.net', i)
        return i if m and not JUNK.match(m.group(1)) else None
    if system == 'ultipro':
        m = re.fullmatch(r'((?:recruiting\d*|n\d+)\.ultipro\.(?:com|ca))/([a-z0-9]+)/jobboard/([0-9a-f-]{36})', i)
        return f'{m.group(1)}/{m.group(2).upper()}/JobBoard/{m.group(3)}' if m else None
    if system in ('avature', 'eightfold') and not i.endswith(('.avature.net', '.eightfold.ai')):
        return custom_host(system, i)                    # JSA-137: careers.ibm.com/en_US, apply.careers.microsoft.com
    if system in ('bamboohr', 'breezy', 'recruitee', 'pinpoint', 'avature', 'jazzhr', 'eightfold', 'teamtailor', 'applicantpro'):
        dom = {'bamboohr': 'bamboohr.com', 'breezy': 'breezy.hr', 'recruitee': 'recruitee.com', 'pinpoint': 'pinpointhq.com',
               'avature': 'avature.net', 'jazzhr': 'applytojob.com', 'eightfold': 'eightfold.ai', 'teamtailor': 'teamtailor.com',
               'applicantpro': 'applicantpro.com'}[system]
        m = re.fullmatch(r'([a-z0-9-]+)\.' + re.escape(dom), i)
        return i if m and not JUNK.match(m.group(1)) and not re.search(r'employee|internal', m.group(1)) else None
    if system == 'jobvite':                              # 'acme' or 'careers/acme' (both URL shapes, ats-scrapers resolve.py)
        m = re.fullmatch(r'(careers/)?([a-z0-9][a-z0-9_-]*)', i)
        return i if m and not JUNK.match(m.group(2)) and m.group(2) not in ('search', 'viewall') else None
    if system in ('amazon', 'apple', 'google'):          # one company-wide site each: the ident is the name itself
        return system if i == system else None
    if system in ('smartrecruiters', 'workable', 'rippling'):
        return i if re.fullmatch(r'[a-z0-9][a-z0-9_-]*', i) and not JUNK.match(i) else None
    if system == 'successfactors':                       # career?company=<id> keeps the id's case (it matters)
        m = re.fullmatch(r'(career\d*(?:preview)?\.(?:successfactors\.(?:com|eu)|sapsf\.(?:com|eu)))/career\?(?:.*&)?company=([\w.-]+).*',
                         H.unescape(raw), re.I)
        return f'{m.group(1).lower()}/career?company={m.group(2)}' if m else i.split('/')[0]
    if system == 'phenom':
        return i                                         # a CDN host: the company site does the work
    if system == 'dover':                                # apply/<name>/<job uuid> or <name>/careers/<client uuid>
        m = re.fullmatch(r'(?:apply/[^/]+|[^/]+/careers)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', i)
        return f"{'job' if i.startswith('apply/') else 'client'}/{m.group(1)}" if m else None
    if system in ('adp', 'brassring'):                   # the full URL; the client ids sit in its query
        q = urllib.parse.parse_qs(urllib.parse.urlsplit('https://' + H.unescape(H.unescape(i)).split('#')[0]).query)
        q = {k.lower(): v[0] for k, v in q.items()}
        host = i.split('/')[0]
        if system == 'adp':
            ok = re.fullmatch(r'workforcenow(?:\.cloud)?\.adp\.com', host) and re.fullmatch(r'[0-9a-f-]{36}', q.get('cid', '')) \
                and re.fullmatch(r'\d{8}_\d{6}', q.get('ccid', ''))
            return f"{host}/{q['cid']}/{q['ccid']}" if ok else None
        ok = re.fullmatch(r'(?:s?jobs|ts)\.brassring\.com', host) and q.get('partnerid', '').isdigit() and q.get('siteid', '').isdigit()
        return f"{host}/{q['partnerid']}/{q['siteid']}" if ok else None
    if system == 'paycom':                               # /portal/<token>, /jobs/<token>, or the old jobs?clientkey=<token>
        m = re.search(r'/(?:portal|jobs)/([0-9a-f]{32})$', i) or \
            re.search(r'/jobs\?(?:[^#]*&)?clientkey=([0-9a-f]{32})(?![0-9a-f])', H.unescape(H.unescape(i)))
        return m.group(1) if m else None
    if system == 'paylocity':
        m = re.search(r'/recruiting/jobs/(?:all|list)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$', i)
        return m.group(1) if m else None
    if system == 'dayforce':                             # jobs.dayforcehcm.com/[locale/]tenant/board → tenant/board
        seg = [x for x in i.split('/')[1:] if x]
        if seg and re.fullmatch(r'[a-z]{2}(?:-[a-z]{2})?', seg[0]) and len(seg) == 3:
            seg = seg[1:]
        return '/'.join(seg) if len(seg) == 2 and seg[1] != 'jobs' else None
    if system == 'clearcompany':
        m = re.fullmatch(r'apply\.clearcompany\.com/([a-z0-9][a-z0-9_-]*)|([a-z0-9-]+)\.hrmdirect\.com', i)
        if not m or (m.group(1) and JUNK.match(m.group(1))) or m.group(1) == 'v1':
            return None
        return i
    return clean_new(system, i)


CUSTOM_PATH = re.compile(r'(?:[a-z]{2}[_-][a-z]{2}|[a-z]{2}|global|us)', re.I)


def custom_host(system, i):
    """Pure (JSA-137). An Avature / Eightfold career site on the company's own domain (ats-scrapers: 'IBM hosts on
    careers.ibm.com/en_US', 'apply.careers.microsoft.com') → 'host' or 'host/<locale>' (Avature only keeps one locale
    segment such as en_US); None for a bare company home page, a vendor host or a malformed host."""
    host, _, rest = i.partition('/')
    if not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+){2,}', host) or re.search(r'(?:avature\.net|eightfold\.ai)$', host) \
            or root_domain(host) == host or host == 'www.' + root_domain(host):
        return None
    seg = rest.split('/')[0]
    if system == 'avature' and seg and CUSTOM_PATH.fullmatch(seg):
        return f'{host}/{seg[:2].lower()}{seg[2:3]}{seg[3:].upper()}' if len(seg) == 5 else f'{host}/{seg}'
    return host


def clean_new(system, i):
    """Pure (JSA-137). clean_ident for the systems ported from ats-scrapers on 2026-11-04 (lower-cased input)."""
    if system in ('tiktok', 'bytedance'):                # one company-wide site per tenant
        t = {'lifeattiktok.com': 'tiktok', 'api.lifeattiktok.com': 'tiktok', 'careers.tiktokusds.com': 'usds',
             'joinbytedance.com': 'bytedance', 'jobs.bytedance.com': 'bytedance'}.get(i.split('/')[0].removeprefix('www.'), i)
        return t if t in ({'tiktok', 'usds'} if system == 'tiktok' else {'bytedance'}) else None
    if system == 'cornerstone':                          # <slug>.csod.com[/ux/ats/careersite/<site>] → host/site (site 1)
        m = re.fullmatch(r'([a-z0-9-]+)\.csod\.com(?:/ux/ats/careersite/(\d+)(?:/.*)?)?', i)
        return f'{m.group(1)}.csod.com/{m.group(2) or 1}' if m and not JUNK.match(m.group(1)) else None
    if system == 'pageup':                               # <client>/<channel>/<locale>
        m = re.fullmatch(r'(?:mob/)?(\d+)/([a-z0-9-]+)/([a-z]{2}(?:-[a-z]{2})?)(?:/.*)?', i)
        return '/'.join(m.groups()) if m else None
    if system == 'keka':                                 # <tenant>.keka.com[/careers[/<portal>]] → host or host/portal
        m = re.fullmatch(r'([a-z0-9-]+)\.keka\.com(?:/careers(?:/([a-z0-9_-]+))?)?(?:/.*)?', i)
        if not m or JUNK.match(m.group(1)):
            return None
        portal = m.group(2) if m.group(2) not in (None, 'api', 'applyjob', 'jobdetails', 'content') else None
        return f'{m.group(1)}.keka.com' + (f'/{portal}' if portal else '')
    dom = {'personio': r'jobs\.personio\.(?:com|de)', 'softgarden': r'career\.softgarden\.de', 'gupy': r'gupy\.io',
           'beisen': r'zhiye\.com'}.get(system)
    if dom:
        m = re.fullmatch(r'([a-z0-9-]+)\.' + dom, i)
        return i if m and not JUNK.match(m.group(1)) and m.group(1) not in ('portal', 'login', 'vagas') else None
    if system in ('gem', 'recruiterbox', 'join', 'hrmos', 'herp'):    # a board slug
        return i if re.fullmatch(r'[a-z0-9][a-z0-9_.-]*', i) and not JUNK.match(i) and i not in ('jsapi', 'v1', 'pages') else None
    return None


def with_site(systems, site):
    """[(system, ident)] → same list with `ident@site` for the systems whose ident does not name the company."""
    if not site:
        return list(systems)
    return [(s, f'{i}@{site}' if s in NEEDS_SITE and isinstance(i, str) and '@' not in i else i) for s, i in systems]


def site_of(ident):
    return ident.split('@', 1)[1] if isinstance(ident, str) and '@' in ident else ''


def career_hosts(site):
    """Pure. Company site → careers hosts to try, in order: careers.<root>, jobs.<root>."""
    r = root_domain(site)
    return [f'careers.{r}', f'jobs.{r}'] if r and '.' in r else []


VENDOR_HOST = re.compile(r'(?:^|\.)(?:successfactors\.(?:com|eu)|sapsf\.(?:com|eu)|jobs\.sap\.com|phenompeople\.com)$')


def site_hosts(ident, site):
    """Pure (JSA-117). SuccessFactors / Phenom career hosts to try, in order: the ident's own host when it is a company
    career site (an RMK site such as 'jobs.weill.cornell.edu' or 'ey.jobs2web.com', a Phenom host such as
    'jobs.bell.ca'), then career_hosts(site). Vendor hosts (successfactors / sapsf / jobs.sap.com / phenompeople) and
    jobs2web hosts whose first label is vendor infrastructure are never tried; no duplicates."""
    own = (ident or '').split('@')[0].split('/')[0].strip().lower()
    ok = bool(re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+', own)) and not VENDOR_HOST.search(own)
    if own.endswith('.jobs2web.com'):                    # <company>.jobs2web.com, never a vendor label
        ok = ok and own.count('.') == 2 and not JUNK.match(own.split('.')[0])
    elif ok and (root_domain(own) == own or own == 'www.' + root_domain(own)):
        ok = False                                       # the company's home page is the site, not a career host
    return list(dict.fromkeys(([own] if ok else []) + career_hosts(site)))


def tbe_ident(i):
    """Pure (JSA-117). A Taleo Business Edition URL ('phg.tbe.taleo.net/phg03/ats/careers/v2/searchResults?org=ACMEBRIC&cws=1')
    → 'phg.tbe.taleo.net/phg03/ACMEBRIC/1' (org upper-cased, cws defaults to 1); None when it is not one or has no org."""
    u = urllib.parse.urlsplit('https://' + H.unescape(H.unescape((i or '').strip())))
    host, seg = (u.hostname or '').lower(), [x for x in u.path.split('/') if x]
    q = {k.lower(): v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
    if not re.fullmatch(r'[a-z0-9-]+\.tbe\.taleo\.net', host) or not seg or not re.fullmatch(r'[\w-]+', seg[0]) \
            or not re.fullmatch(r'[A-Za-z0-9_-]+', q.get('org', '')):
        return None
    cws = q.get('cws', '1')
    return f"{host}/{seg[0].lower()}/{q['org'].upper()}/{cws if cws.isdigit() else '1'}"


# ---------- network ----------
_last, _hlock = {}, threading.Lock()
_cache, _clock = {}, threading.Lock()
RETRYABLE = {408, 500, 502, 503, 504}       # transient: retried with backoff (ats-scrapers fetch.py)
BLOCKED = {403, 406}                         # a wall for plain clients: recorded, never escalated (no impersonation)


class Blocked(Exception):
    pass


def backoff(attempt, retry_after=None, base=1.5, cap=30.0):
    """Pure. Seconds to wait before retry `attempt` (1 = first retry): a numeric Retry-After header when it is
    ≤ cap, else base · 2^(attempt-1) capped at cap. (After ats-scrapers fetch.py, MIT.)"""
    if isinstance(retry_after, str) and retry_after.strip().isdigit() and int(retry_after) <= cap:
        return float(int(retry_after))
    return min(base * 2 ** (attempt - 1), cap)


def is_blocked(status, body):
    """Pure. A security check / bot wall: 429; 403 / 406 / 202 / 503 with an empty body or a challenge page; or a
    challenge <title> on any status."""
    b = body or ''
    if status == 429:
        return True
    if status in BLOCKED | {202, 503} and (not b.strip() or CHALLENGE.search(b[:20000])):
        return True
    return bool(re.search(r'<title>\s*(just a moment|attention required|access denied|security check)', b[:5000], re.I))


def fetch(url, data=None, headers=None, timeout=20, tries=3, opener=None):
    """→ (status, final_url, text). ≥ 1 s between requests to one host; network errors and 408 / 5xx retried with
    backoff (tries in all), a 429 waits once for Retry-After (≤ 30 s), then counts as blocked. A wall → Blocked."""
    host = urllib.parse.urlsplit(url).hostname or ''
    h = {**UA, **(headers or {})}
    for attempt in range(1, tries + 1):
        with _hlock:
            wait = _last.get(host, 0) + 1.0 - time.time()
            _last[host] = max(time.time(), _last.get(host, 0) + 1.0)
        if wait > 0:
            time.sleep(wait)
        retry_after = None
        try:
            with (opener.open if opener else urllib.request.urlopen)(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
                st, fu, body = r.status, r.geturl(), r.read(4_000_000).decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            try:
                body = e.read(200_000).decode('utf-8', 'replace')
            except Exception:
                body = ''
            st, fu, retry_after = e.code, url, e.headers.get('Retry-After') if e.headers else None
        except Exception:
            if attempt < tries:
                time.sleep(backoff(attempt)); continue
            return 0, url, ''
        if st == 429 and attempt < tries and retry_after:
            time.sleep(backoff(attempt, retry_after)); continue
        if is_blocked(st, body):
            raise Blocked(f'security check on {host} ({st})')
        if st in RETRYABLE and attempt < tries:
            time.sleep(backoff(attempt, retry_after)); continue
        return st, fu, body
    return 0, url, ''


def get_json(url, data=None, headers=None):
    st, _, b = fetch(url, data, {**({'Content-Type': 'application/json'} if data else {}), **(headers or {})})
    if st != 200:
        return None
    try:
        return json.loads(b)
    except ValueError:
        return None


def P(title, location, url):
    return {'title': H.unescape(re.sub(r'\s+', ' ', title or '')).strip(), 'location': H.unescape(re.sub(r'\s+', ' ', location or '')).strip(),
            'url': url}


# ---------- pure parsers (tested) ----------
def parse_icims(page, host):
    """iCIMS search page (in_iframe=1) → postings; location = the 'Job Locations' / 'Location' field just before each
    title (ats-scrapers icims.py names the 'Job Locations' label; we read only 'Location' before, 11-03)."""
    out, seen = [], set()
    for m in re.finditer(r'<a href="(https://' + re.escape(host) + r'/jobs/(\d+)/[^"?]+/job)[^"]*"[^>]*>\s*(?:<span[^>]*>[^<]*</span>\s*)?'
                         r'<h3[^>]*>([^<]+)</h3>', page or '', re.I):
        if m.group(2) in seen:
            continue
        seen.add(m.group(2))
        before = page[max(0, m.start() - 1500):m.start()]
        loc = re.findall(r'field-label">\s*(?:Job\s+)?Locations?\s*</span>\s*<span[^>]*>([^<]+)</span>', before, re.I)
        out.append(P(m.group(3), loc[-1] if loc else '', m.group(1)))
    return out


def parse_rmk(page, base):
    """SuccessFactors career-site search page (/search/?q=) → postings. Job links are /job/… or /<site>/job/… (a
    multi-site career host such as jobs.weill.cornell.edu/NY/job/…, JSA-117)."""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(/(?:[\w-]+/)?job/[^"]+/\d+/?)"[^>]*class="jobTitle-link[^"]*"[^>]*>([^<]+)</a>|'
                         r'<a[^>]+class="jobTitle-link[^"]*"[^>]+href="(/(?:[\w-]+/)?job/[^"]+/\d+/?)"[^>]*>([^<]+)</a>', page or '', re.I):
        href, title = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if href in seen:
            continue
        seen.add(href)
        tail = page[m.end():m.end() + 2500]
        loc = re.search(r'class="jobLocation[^"]*"[^>]*>\s*(?:<span[^>]*>)?\s*([^<]+)', tail) or \
            re.search(r'id="[\w-]*-section-location-value"[^>]*>\s*([^<]+)', tail)        # the tile layout
        out.append(P(title, loc.group(1) if loc else '', urllib.parse.urljoin(base, href)))
    return out


def parse_sitemal(xml):
    """SuccessFactors Recruiting Marketing feed (/sitemal.xml, RSS; found in ats-scrapers successfactors.py) → postings.
    Item titles read 'Title (City, ST, US, 12345)': the last parenthesis holding a comma is the location."""
    out = []
    for t, l in re.findall(r'<item>\s*<title>(.*?)</title>.*?<link>(.*?)</link>', xml or '', re.S):
        t = H.unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', t)).strip()
        m = re.match(r'(.*\S)\s*\(([^()]*,[^()]*)\)\s*$', t)
        out.append(P(m.group(1) if m else t, m.group(2) if m else '', l.strip()))
    return out


def parse_phenom(page):
    """Phenom search-results page → postings from the embedded eagerLoadRefineSearch JSON. url = the posting's own
    Workday / other ATS apply link when the page gives one (minus '/apply'), else <baseUrl>job/<jobId>."""
    i = (page or '').find('"eagerLoadRefineSearch":')
    if i < 0:
        return []
    try:
        d, _ = json.JSONDecoder().raw_decode(page[i + len('"eagerLoadRefineSearch":'):])
    except ValueError:
        return []
    base = (re.search(r'"baseUrl":"([^"]+)"', page) or [None, ''])[1]
    out = []
    for j in ((d.get('data') or {}).get('jobs') or []):
        apply = j.get('applyUrl') or ''
        if re.search(r'myworkdayjobs\.com|myworkdaysite\.com|greenhouse\.io|lever\.co|ashbyhq\.com', apply):
            url = re.sub(r'/apply/?$', '', apply)
        elif base and j.get('jobId'):
            url = f"{base}job/{j['jobId']}"
        else:
            continue
        out.append(P(j.get('title'), j.get('cityStateCountry') or j.get('location') or '', url))
    return out


def parse_oracle(d, host, site):
    """recruitingCEJobRequisitions JSON → postings; the id falls back to RequisitionNumber (ats-scrapers oracle.py)."""
    items = (d or {}).get('items') or []
    out = []
    for it in items[:1]:
        for r in it.get('requisitionList') or []:
            rid = r.get('Id') or r.get('RequisitionNumber')
            if rid:
                out.append(P(r.get('Title'), r.get('PrimaryLocation'),
                             f'https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{rid}'))
    return out


def parse_taleo(d, host, cs):
    out = []
    for r in (d or {}).get('requisitionList') or []:
        col = r.get('column') or []
        if not col or not r.get('contestNo'):
            continue
        loc = ''
        if len(col) > 1:
            try:
                loc = '; '.join(json.loads(col[1])) if col[1].startswith('[') else col[1]
            except ValueError:
                loc = col[1]
        out.append(P(col[0], loc, f'https://{host}/careersection/{cs}/jobdetail.ftl?job={r["contestNo"]}&lang=en'))
    return out


def parse_tbe(page):
    """Taleo Business Edition searchResults page → postings: each `<h4 class="oracletaleocwsv2-head-title"><a href=…
    viewRequisition…>Title</a></h4>` followed by its `<div tabindex="0">` lines (city, state …) as the location."""
    out, seen = [], set()
    for m in re.finditer(r'<h4[^>]*oracletaleocwsv2-head-title[^>]*>\s*<a[^>]+href="([^"]*viewRequisition[^"]*)"[^>]*>(.*?)</a>\s*</h4>(.*?)</div>\s*<!--/\.accordion-head-info',
                         page or '', re.S | re.I):
        u = H.unescape(m.group(1))
        if not u.startswith('https://') or u in seen:
            continue
        seen.add(u)
        loc = [re.sub(r'<[^>]+>', '', x).strip() for x in re.findall(r'<div[^>]*>(.*?)</div>', m.group(3) + '</div>', re.S)]
        out.append(P(re.sub(r'<[^>]+>', '', m.group(2)), ', '.join(x for x in loc if x and not x.isdigit()), u))
    return out


def parse_dover(d, name):
    """Dover careers-page jobs JSON (`results[]`) → postings; only published, non-sample jobs; url =
    https://app.dover.com/apply/<name, URL-quoted>/<id>; location = the locations' names joined '; '."""
    out = []
    for j in (d or {}).get('results') or [] if isinstance(d, dict) else []:
        if not isinstance(j, dict) or not j.get('id') or not j.get('title') or j.get('is_published') is False or j.get('is_sample'):
            continue
        locs = [l.get('name') or (l.get('location_option') or {}).get('display_name') or '' for l in j.get('locations') or [] if isinstance(l, dict)]
        out.append(P(j['title'], '; '.join(dict.fromkeys(x for x in locs if x)),
                     f"https://app.dover.com/apply/{urllib.parse.quote(name or 'company')}/{j['id']}"))
    return out


def parse_jazz(page, host):
    """JazzHR board → postings. Two markups: the /apply list (<a href="https://<host>/apply/<id>/<slug>">Title</a>,
    location after fa-map-marker) and the /apply/jobs table (<a class="job_title_link" href="/apply/jobs/details/<id>">,
    location in the next <td>; ats-scrapers jazzhr.py)."""
    out, seen = [], set()
    for m in re.finditer(r'<a href="(https://' + re.escape(host) + r'/apply/(\w+)/[^"]*)">\s*([^<]+?)\s*</a>', page or ''):
        loc = re.search(r"fa-map-marker'></i>([^<]+)", page[m.end():m.end() + 600])
        seen.add(m.group(2)); out.append(P(m.group(3), loc.group(1) if loc else '', m.group(1)))
    for m in re.finditer(r'<a[^>]*href="(/apply/jobs/details/(\w+))[^"]*"[^>]*>\s*([^<]+?)\s*</a>', page or ''):
        if m.group(2) in seen:
            continue
        seen.add(m.group(2))
        loc = re.search(r'</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>', page[m.end():m.end() + 800])
        out.append(P(m.group(3), loc.group(1) if loc else '', f'https://{host}{m.group(1)}'))
    return out


def parse_jobvite(page, slug):
    out = []
    for m in re.finditer(r'<a[^>]+href="(/' + re.escape(slug) + r'/job/\w+)"[^>]*>\s*([^<]+?)\s*</a>', page or '', re.I):
        loc = re.search(r'jv-job-list-location">(.*?)</td', page[m.end():m.end() + 1500], re.S)
        out.append(P(m.group(2), re.sub(r'<[^>]+>', ' ', loc.group(1)) if loc else '', 'https://jobs.jobvite.com' + m.group(1)))
    return out


def jobvite_range(page):
    """Pure. Jobvite's '1-50 of 63' pagination text → (start, end, total), or None."""
    m = re.search(r'jv-pagination-text">\s*(\d+)\s*-\s*(\d+)\s+of\s+(\d+)', page or '', re.I)
    return tuple(int(x) for x in m.groups()) if m else None


def parse_rss(xml):
    """RSS items → postings. A Teamtailor <tt:location> (<tt:city>, <tt:name>) inside the item is the location
    (ats-scrapers teamtailor.py)."""
    out = []
    for item in re.findall(r'<item>(.*?)</item>', xml or '', re.S):
        t, l = re.search(r'<title>(.*?)</title>', item, re.S), re.search(r'<link>(.*?)</link>', item, re.S)
        if not t or not l:
            continue
        loc = re.findall(r'<tt:(?:city|name)>\s*(?:<!\[CDATA\[)?([^<\]]+)', item)
        out.append(P(re.sub(r'<!\[CDATA\[|\]\]>', '', t.group(1)), ', '.join(dict.fromkeys(x.strip() for x in loc)),
                     l.group(1).strip()))
    return out


def parse_avature(page):
    """Avature SearchJobs page → postings (ats-scrapers avature.py: no JSON API; every tenant links JobDetail pages).
    The JobDetail slug starts with the location ('Darlington-South-Carolina-United-States-<title>'): the words before
    'United-States' + ', United States' are the location; a slug that starts with 'United-States' → 'United States'."""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+/JobDetail/([^"/]+)/(\d+))"[^>]*>\s*([^<]{2,200}?)\s*</a>', page or ''):
        if m.group(3) in seen or not re.search(r'[A-Za-z]', m.group(4)):
            continue
        seen.add(m.group(3))
        slug = m.group(2)
        k = slug.find('United-States')
        loc = '' if k < 0 else ('United States' if k == 0 else slug[:k].strip('-').replace('-', ' ') + ', United States')
        out.append(P(m.group(4), loc, m.group(1)))
    return out


def parse_adp(d, host, cid, ccid):
    """ADP Workforce Now job-requisitions JSON → postings (endpoint and fields after ats-scrapers adp.py, MIT)."""
    out = []
    for it in (d or {}).get('jobRequisitions') or []:
        if not isinstance(it, dict) or not it.get('itemID'):
            continue
        locs = [((l.get('nameCode') or {}).get('shortName') or '') for l in it.get('requisitionLocations') or [] if isinstance(l, dict)]
        q = urllib.parse.urlencode({'cid': cid, 'ccId': ccid, 'lang': 'en_US', 'jobId': it['itemID'], 'source': 'CC2'})
        out.append(P(it.get('requisitionTitle'), '; '.join(x for x in locs if x),
                     f'https://{host}/mascsr/default/mdf/recruitment/recruitment.html?{q}'))
    return out


def paycom_config(page):
    """Pure. A Paycom portal page → (session JWT, API service URL) or None. The portal hands every visitor an
    anonymous session token in `var configsFromHost = {…}; var Mountable`; the service URL must be https on
    *.paycomonline.net (ats-scrapers paycom.py checks the same)."""
    m = re.search(r'var configsFromHost = (\{.*?\});\s*var Mountable', page or '', re.S)
    if not m:
        return None
    try:
        cfg = json.loads(m.group(1)); lib = json.loads(cfg.get('libConfig') or '{}')
    except ValueError:
        return None
    jwt, svc = cfg.get('sessionJWT'), lib.get('atsPortalMantleServiceUrl') or ''
    u = urllib.parse.urlsplit(svc)
    if not jwt or u.scheme != 'https' or not re.fullmatch(r'(?:[\w-]+\.)*paycomonline\.net', u.hostname or '') \
            or u.query or u.fragment or u.username or u.port not in (None, 443):
        return None
    return jwt, svc.rstrip('/')


def parse_paylocity(page, guid=''):
    """Paylocity board page → postings from `window.pageData = {…}` (Jobs; internal jobs skipped; ats-scrapers
    paylocity.py). url = /Recruiting/Jobs/Details/<JobId>; location = JobLocation City, State, else LocationName."""
    m = re.search(r'\bwindow\.pageData\s*=\s*', page or '')
    if not m:
        return []
    try:
        d, _ = json.JSONDecoder().raw_decode(page[m.end():])
    except ValueError:
        return []
    out = []
    for j in d.get('Jobs') or []:
        if not isinstance(j, dict) or j.get('IsInternal') or not j.get('JobId'):
            continue
        jl = j.get('JobLocation') if isinstance(j.get('JobLocation'), dict) else {}
        loc = ', '.join(x for x in (jl.get('City'), jl.get('State')) if x) or j.get('LocationName') or ''
        out.append(P(j.get('JobTitle'), loc, f"https://recruiting.paylocity.com/Recruiting/Jobs/Details/{j['JobId']}"))
    return out


def parse_dayforce(d, tenant, board):
    """Dayforce JobFeeds JSON (a list) → postings; url = JobDetailsUrl when it is on jobs.dayforcehcm.com, else
    https://jobs.dayforcehcm.com/en-US/<tenant>/<board>/jobs/<ReferenceNumber> (ats-scrapers dayforce.py)."""
    out = []
    for it in d if isinstance(d, list) else []:
        if not isinstance(it, dict) or not it.get('Title') or not it.get('ReferenceNumber'):
            continue
        u = it.get('JobDetailsUrl') or ''
        if urllib.parse.urlsplit(u).hostname != 'jobs.dayforcehcm.com':
            u = f"https://jobs.dayforcehcm.com/en-US/{tenant}/{board}/jobs/{it['ReferenceNumber']}"
        out.append(P(it['Title'], ', '.join(x for x in (it.get('City'), it.get('State')) if x), u))
    return out


def brassring_session(page):
    """Pure. A BrassRing TGnewUI home page → (__RequestVerificationToken, CookieValue) or None — the anonymous
    session values the page's own search script sends (the RFT header and encryptedSessionValue)."""
    def hidden(attr):                                  # <input …> with that attribute, attributes in any order
        for tag in re.findall(r'<input\b[^>]*>', page or '', re.I):
            if re.search(attr, tag, re.I):
                v = re.search(r'\bvalue="([^"]*)"', tag)
                if v:
                    return H.unescape(v.group(1))
        return None
    t, c = hidden(r'\bname="__RequestVerificationToken"'), hidden(r'\bid="CookieValue"')
    return (t, c) if t and c else None


def parse_brassring(d):
    """BrassRing search JSON → postings: Jobs.Job[] with Questions (jobtitle, reqid, any *location* / *city* field)
    and Link."""
    out = []
    for j in ((d or {}).get('Jobs') or {}).get('Job') or []:
        q = {(x.get('QuestionName') or '').lower(): x.get('Value') or '' for x in j.get('Questions') or [] if isinstance(x, dict)}
        loc = next((re.sub(r'<[^>]+>', ' ', v) for k, v in q.items() if re.search(r'location|city', k) and v), '')
        if q.get('jobtitle') and j.get('Link'):
            out.append(P(q['jobtitle'], loc, j['Link']))
    return out


def clearcompany_site_id(page):
    """Pure. ClearCompany hosted careers page → the widget's data-site-id (a GUID), or None."""
    m = re.search(r'data-site-id="([0-9a-fA-F-]{36})"', page or '')
    return m.group(1) if m else None


def parse_clearcompany(d):
    """careers-api.clearcompany.com/v1/<siteId> JSON → postings; url = applyLink without a trailing '/apply'."""
    out = []
    for j in (d or {}).get('results') or []:
        u = re.sub(r'/apply/?$', '', j.get('applyLink') or '')
        if j.get('positionTitle') and u.startswith('https://'):
            out.append(P(j['positionTitle'], j.get('location') or '', u))
    return out


# ---------- adapters: one per system, (board, ident, query) → postings ----------
def _icims(i, ident, q):
    """Keyword search, pages pr=0.. until a page adds no new posting (≤ 3; ats-scrapers paginates the same way)."""
    out, ids = [], set()
    for page in range(3):
        st, _, html = fetch(f'https://{i}/jobs/search?ss=1&searchKeyword={urllib.parse.quote(q)}&pr={page}&in_iframe=1')
        got = [p for p in parse_icims(html, i) if p['url'] not in ids] if st == 200 else []
        if not got:
            break
        ids |= {p['url'] for p in got}; out += got
    return out


def _oracle(i, ident, q):
    for site in ('CX_1', 'CX', 'CX_2', 'CX_1001'):
        d = get_json(f'https://{i}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList'
                     f'&finder=findReqs;siteNumber={site},keyword={urllib.parse.quote(q)},limit=50')   # limit inside finder
        if d and (d.get('items') or [{}])[0].get('TotalJobsCount') is not None:
            return parse_oracle(d, i, site)
    return []


def _taleo(i, ident, q):
    if '/' in i:                                         # Business Edition: one public results page (whole list)
        host, d, org, cws = i.split('/')
        st, _, page = fetch(f'https://{host}/{d}/ats/careers/v2/searchResults?org={org}&cws={cws}')
        return parse_tbe(page) if st == 200 else []
    for cs in ('ex', '2', '1', 'external', '10000', 'jobsearch'):
        st, fu, page = fetch(f'https://{i}/careersection/{cs}/jobsearch.ftl?lang=en')
        if 'taleo.net' not in fu:
            continue
        m = re.search(r'portal=(\d+)', page or '')
        if st != 200 or not m or 'Career Section Unavailable' in page:
            continue
        body = {'multilineEnabled': False, 'sortingSelection': {'sortBySelectionParam': '3', 'ascendingSortingOrder': 'false'},
                'fieldData': {'fields': {'KEYWORD': q, 'LOCATION': '', 'CATEGORY': ''}, 'valid': True},
                'filterSelectionParam': {'searchFilterSelections': []},
                'advancedSearchFiltersSelectionParam': {'searchFilterSelections': []}, 'pageNo': 1}
        d = get_json(f'https://{i}/careersection/rest/jobboard/searchjobs?lang=en&portal={m.group(1)}',
                     json.dumps(body).encode(), {'tz': 'GMT-05:00'})
        return parse_taleo(d, i, cs)
    return []


def ukg_load_url(page, host, tenant):
    """Pure. The board page's `loadUrl: "…/JobBoardView/LoadSearchResults"` → the board base URL when it stays on the
    same host and tenant, else None (ats-scrapers ukg.py checks the same before posting)."""
    m = re.search(r'\bloadUrl:\s*"([^"]+)"', page or '')
    if not m:
        return None
    u = urllib.parse.urljoin(f'https://{host}/', H.unescape(m.group(1)))
    p = urllib.parse.urlsplit(u)
    seg = [s for s in p.path.split('/') if s]
    if p.hostname != host or len(seg) != 5 or seg[0].lower() != tenant.lower() or seg[1].lower() != 'jobboard' \
            or not re.fullmatch(r'[0-9a-f-]{36}', seg[2], re.I) or seg[3:] != ['JobBoardView', 'LoadSearchResults']:
        return None
    return f'https://{host}/{seg[0]}/JobBoard/{seg[2]}'


def _ultipro(i, ident, q):
    host, tenant, _, board = i.split('/')
    base = f'https://{host}/{tenant}/JobBoard/{board}'
    st, _, page = fetch(base + '/')
    base = (ukg_load_url(page, host, tenant) if st == 200 else None) or base
    body = {'opportunitySearch': {'Top': 50, 'Skip': 0, 'QueryString': q, 'Filters': [],
                                  'OrderBy': [{'Value': 'postedDateDesc', 'PropertyName': 'PostedDate', 'Ascending': False}]},
            'matchCriteria': {'PreferredJobs': [], 'Educations': [], 'LicenseAndCertifications': [], 'Skills': [],
                              'hasNoLicenses': False, 'SkippedSkills': []}}
    d = get_json(base + '/JobBoardView/LoadSearchResults', json.dumps(body).encode(), {'X-Requested-With': 'XMLHttpRequest'})
    out = []
    for o in (d or {}).get('opportunities') or []:
        locs = [', '.join(x for x in ((l.get('Address') or {}).get('City'), ((l.get('Address') or {}).get('State') or {}).get('Code')) if x)
                for l in o.get('Locations') or []]
        out.append(P(o.get('Title'), '; '.join(x for x in locs if x), f'{base}/OpportunityDetail?opportunityId={o["Id"]}'))
    return out


def _careers_site(system, hosts, q):
    """SuccessFactors / Phenom career site on one of `hosts` (site_hosts()). SuccessFactors: the /search/?q= results,
    else the whole /sitemal.xml feed (ats-scrapers successfactors.py)."""
    for h in hosts:
        st, fu, page = fetch(f'https://{h}/')
        if st != 200:
            continue
        if system == 'phenom' or 'phApp' in page:
            base = (re.search(r'"baseUrl":"([^"]+)"', page) or [None, ''])[1] or fu.rstrip('/') + '/'
            st, fu, p2 = fetch(base + 'search-results?keywords=' + urllib.parse.quote(q))
            got = parse_phenom(p2) if st == 200 else []
            if got or 'phApp' in page:
                return got
        st, fu, p2 = fetch(f'https://{h}/search/?q=' + urllib.parse.quote(q))
        if st == 200 and 'jobTitle-link' in p2:
            got = parse_rmk(p2, fu)
            if got:
                return got
        st, _, xml = fetch(f'https://{h}/sitemal.xml')
        if st == 200 and '<rss' in xml[:500]:
            return parse_sitemal(xml)
    return []


def _sf(i, ident, q):
    """The RMK career site: a `career?company=<id>` link first (it redirects there when the company has one), then
    site_hosts()."""
    hosts = site_hosts(i, site_of(ident))
    if '/career?company=' in i:
        st, fu, _ = fetch(f'https://{i}&career_ns=job_listing_summary&navBarLevel=JOB_SEARCH')
        h = (urllib.parse.urlsplit(fu).hostname or '').lower() if st == 200 else ''
        hosts = ([h] if h and not VENDOR_HOST.search(h) else []) + [x for x in hosts if x != h]
    return _careers_site('successfactors', hosts, q)


def _phenom(i, ident, q):
    return _careers_site('phenom', site_hosts(i, site_of(ident)), q)


def _eightfold(i, ident, q):
    """PCSX search (10 per page, start = 0, 10, 20); a tenant that answers 'not authorized for PCSX' / 'PCSX is not
    enabled' is read through the older /api/apply/v2/jobs instead (ats-scrapers eightfold.py)."""
    own = '' if i.endswith('.eightfold.ai') else root_domain(i)        # custom domain (apply.careers.microsoft.com)
    doms = list(dict.fromkeys(x for x in (own, root_domain(site_of(ident)), f"{i.split('.')[0]}.com" if not own else '') if x))
    for dom in doms:
        out = []
        for api in ('pcsx/search', 'apply/v2/jobs'):
            for start in (0, 10, 20):
                st, _, b = fetch(f'https://{i}/api/{api}?domain={dom}&query={urllib.parse.quote(q)}&location=&start={start}')
                if st == 403 and re.search(r'not authorized for pcsx|pcsx is not enabled', b, re.I):
                    break
                try:
                    d = json.loads(b) if st == 200 else {}
                except ValueError:
                    d = {}
                pos = (d.get('data') or {}).get('positions') or d.get('positions') or []
                for p in pos:
                    u = p.get('positionUrl') or p.get('canonicalPositionUrl') or (f"/careers/job/{p['id']}" if p.get('id') else '')
                    if u:
                        out.append(P(p.get('name'), '; '.join(p.get('standardizedLocations') or p.get('locations') or
                                                              ([p['location']] if p.get('location') else [])),
                                     u if u.startswith('http') else f'https://{i}{u}'))
                if len(pos) < 10:
                    break
            if out:
                return out
    return []


def _smartrecruiters(i, ident, q):
    """Server-side q= search (ats-scrapers pulls the whole board with limit / offset; one search is cheaper)."""
    d = get_json(f'https://api.smartrecruiters.com/v1/companies/{i}/postings?q={urllib.parse.quote(q)}&limit=100')
    return [P(j.get('name'), ', '.join(x for x in ((j.get('location') or {}).get('city'), (j.get('location') or {}).get('region')) if x),
              f'https://jobs.smartrecruiters.com/{i}/{j["id"]}') for j in (d or {}).get('content') or [] if j.get('id')]


def _workable(i, ident, q):
    d = get_json(f'https://apply.workable.com/api/v1/widget/accounts/{i}')
    return [P(j.get('title'), ', '.join(x for x in (j.get('city'), j.get('state')) if x), j.get('shortlink') or j.get('url'))
            for j in (d or {}).get('jobs') or [] if j.get('shortlink') or j.get('url')]


def _jobvite(i, ident, q):
    """/<tenant>/search?p=N pages until '1-50 of 63' says the end (≤ 5 pages), else the /jobs page; a redirect to
    jobvite.com/support = no such tenant (ats-scrapers jobvite.py)."""
    out = []
    for p in range(5):
        st, fu, page = fetch(f'https://jobs.jobvite.com/{i}/search?p={p}')
        if st != 200 or 'jobs.jobvite.com' not in fu:
            break
        out += parse_jobvite(page, i)
        r = jobvite_range(page)
        if not r or r[1] >= r[2]:
            break
    if not out:
        st, fu, page = fetch(f'https://jobs.jobvite.com/{i}/jobs')
        out = parse_jobvite(page, i) if st == 200 and 'jobs.jobvite.com' in fu else []
    return out


def _bamboohr(i, ident, q):
    """/careers/list JSON, else the /jobs/embed2.php widget (ats-scrapers bamboohr.py: /careers/list is retired on
    many tenants; embed2.php answers JSON with departments → positions)."""
    d = get_json(f'https://{i}/careers/list')
    if d and d.get('result') is not None:
        return [P(j.get('jobOpeningName'), ', '.join(x for x in ((j.get('location') or {}).get('city'), (j.get('location') or {}).get('state')) if x),
                  f'https://{i}/careers/{j["id"]}') for j in d['result'] if j.get('id')]
    d = get_json(f'https://{i}/jobs/embed2.php')
    return [P(p.get('name'), p.get('location') or '', p.get('url') or f'https://{i}/careers/{p["id"]}')
            for dep in (d or {}).get('departments') or [] for p in dep.get('positions') or [] if p.get('id')]


def _avature(i, ident, q):
    """Keyword path /careers/SearchJobs/<query> (pages by jobOffset, ≤ 3), else the RSS feed. A 406 / empty 202 is a
    wall for plain clients → recorded (ats-scrapers escalates to a TLS-impersonation client or a cloud browser;
    we do not)."""
    out = []
    if q:
        for off in range(0, 36, 12):
            st, _, page = fetch(f'https://{i}/careers/SearchJobs/{urllib.parse.quote(q)}?jobRecordsPerPage=12&jobOffset={off}')
            got = [p for p in parse_avature(page) if p['url'] not in {x['url'] for x in out}] if st == 200 else []
            if not got:
                break
            out += got
    if not out:
        st, _, xml = fetch(f'https://{i}/careers/SearchJobs/feed/')
        out = parse_rss(xml) if st == 200 else []
    return out


def _jazzhr(i, ident, q):
    st, _, page = fetch(f'https://{i}/apply')
    out = parse_jazz(page, i) if st == 200 else []
    if not out:
        st, _, page = fetch(f'https://{i}/apply/jobs')
        out = parse_jazz(page, i) if st == 200 else []
    return out


def _rippling(i, ident, q):
    """ats.rippling.com board API, else api.rippling.com/platform/api/ats/v1 (ats-scrapers rippling.py)."""
    d = get_json(f'https://ats.rippling.com/api/v2/board/{i}/jobs')
    out = [P(j.get('name'), '; '.join(l.get('name', '') for l in j.get('locations') or []), j.get('url'))
           for j in (d or {}).get('items') or [] if j.get('url')]
    if not out:
        d = get_json(f'https://api.rippling.com/platform/api/ats/v1/board/{i}/jobs')
        out = [P(j.get('name'), (j.get('workLocation') or {}).get('label', ''), j.get('url') or f"https://ats.rippling.com/{i}/jobs/{j['uuid']}")
               for j in d or [] if isinstance(j, dict) and (j.get('url') or j.get('uuid'))]
    return out


def _breezy(i, ident, q):
    st, fu, b = fetch(f'https://{i}/json')
    if st != 200 or urllib.parse.urlsplit(fu).hostname != i:           # a redirect to breezy.hr = no such board
        return []
    try:
        d = json.loads(b)
    except ValueError:
        return []
    return [P(j.get('name'), ', '.join(x for x in ((j.get('location') or {}).get('city'), ((j.get('location') or {}).get('state') or {}).get('id')) if x),
              j.get('url')) for j in d or [] if isinstance(j, dict) and j.get('url')]


def parse_applicantpro(page_html, data, host):
    """Pure (tested). ApplicantPro (JSA-149): the board page carries `"domain_id":"<n>"`; `/core/jobs/<n>?getParams={}`
    answers {"data": {"jobs": [{id, title, city, abbreviation, iso3, workplaceType}]}} → postings with the job page
    https://<host>/jobs/<id>. Location = "city, state" (plus "Remote" when the job says fully remote)."""
    out = []
    for j in ((data or {}).get('data') or {}).get('jobs') or []:
        if not isinstance(j, dict) or not j.get('id') or not j.get('title'):
            continue
        loc = ', '.join(x for x in (j.get('city'), j.get('abbreviation') or j.get('state')) if x)   # the API says abbreviation
        if re.search(r'remote', str(j.get('workplaceType') or ''), re.I):
            loc = (loc + '; Remote') if loc else 'Remote'
        out.append(P(j['title'], loc, f'https://{host}/jobs/{j["id"]}'))
    return out


def applicantpro_site_id(page_html):
    """Pure (tested). The first "domain_id":"<digits>" in the board page, else ''."""
    m = re.search(r'"domain_id"\s*:\s*"?(\d+)', page_html or '')
    return m.group(1) if m else ''


def _applicantpro(i, ident, q):
    st, fu, b = fetch(f'https://{i}/jobs/')
    if st != 200 or urllib.parse.urlsplit(fu).hostname != i:
        return []
    sid = applicantpro_site_id(b)
    if not sid:
        return []
    return parse_applicantpro(b, get_json(f'https://{i}/core/jobs/{sid}?getParams=%7B%7D'), i)


def _recruitee(i, ident, q):
    d = get_json(f'https://{i}/api/offers/')
    return [P(j.get('title'), j.get('location') or j.get('city') or '', j.get('careers_url')) for j in (d or {}).get('offers') or []
            if j.get('careers_url')]


def _teamtailor(i, ident, q):
    if not re.fullmatch(r'[a-z0-9-]+\.teamtailor\.com', i):
        return []
    st, _, xml = fetch(f'https://{i}/jobs.rss')
    return parse_rss(xml) if st == 200 else []


def _pinpoint(i, ident, q):
    d = get_json(f'https://{i}/postings.json')
    return [P(j.get('title'), (j.get('location') or {}).get('name') or (j.get('location') or {}).get('city') or '', j.get('url'))
            for j in (d or {}).get('data') or [] if j.get('url')]


def _dover(i, ident, q):
    """app.dover.com public JSON: a job id → its client id (application-portal-job), then the client's careers page
    (name) and its jobs list (pages by `next`, ≤ 5)."""
    kind, uid = i.split('/')
    if kind == 'job':
        d = get_json(f'https://app.dover.com/api/v1/inbound/application-portal-job/{uid}')
        uid = (d or {}).get('client_id') or ''
        if not re.fullmatch(r'[0-9a-f-]{36}', uid):
            return []
    info = get_json(f'https://app.dover.com/api/v1/careers-page/{uid}') or {}
    out, url = [], f'https://app.dover.com/api/v1/careers-page/{uid}/jobs'
    for _ in range(5):
        d = get_json(url)
        out += parse_dover(d, info.get('name') or '')
        url = (d or {}).get('next') or ''
        if not url.startswith('https://app.dover.com/'):
            break
    return out


def _adp(i, ident, q):
    host, cid, ccid = i.split('/')
    base = f'https://{host}/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions'
    hd = {'Accept': 'application/json', 'Accept-Language': 'en_US', 'locale': 'en_US'}
    out = []
    for skip in range(0, 500, 100):
        d = get_json(f"{base}?{urllib.parse.urlencode({'cid': cid, 'ccId': ccid, 'lang': 'en_US', 'locale': 'en_US', '$skip': skip, '$top': 100, 'userQuery': q})}",
                     headers=hd)
        got = parse_adp(d, host, cid, ccid)
        out += got
        total = ((d or {}).get('meta') or {}).get('totalNumber') or 0
        if len(got) < 100 or skip + 100 >= total:
            break
    return out


def _paycom(i, ident, q):
    st, _, page = fetch(f'https://www.paycomonline.net/v4/ats/web.php/portal/{i}/career-page')
    cfg = paycom_config(page) if st == 200 else None
    if not cfg:
        return []
    jwt, svc = cfg
    body = {'skip': 0, 'take': 100, 'filtersForQuery': {'distanceFrom': 0, 'workEnvironments': [], 'positionTypes': [],
            'educationLevels': [], 'categories': [], 'travelTypes': [], 'shiftTypes': [], 'otherFilters': [],
            'keywordSearchText': q, 'location': '', 'sortOption': ''}}
    d = get_json(svc + '/api/ats/job-posting-previews/search', json.dumps(body).encode(),
                 {'Authorization': jwt, 'Locale': 'en-US', 'Portal-Host-Referrer': f'https://www.paycomonline.net/v4/ats/web.php/portal/{i}/career-page'})
    return [P(j.get('jobTitle'), j.get('locations') if isinstance(j.get('locations'), str) else '',
              f"https://www.paycomonline.net/v4/ats/web.php/portal/{i}/jobs/{j['jobId']}")
            for j in (d or {}).get('jobPostingPreviews') or [] if isinstance(j, dict) and j.get('jobId')]


def _paylocity(i, ident, q):
    st, _, page = fetch(f'https://recruiting.paylocity.com/Recruiting/Jobs/All/{i}')
    return parse_paylocity(page, i) if st == 200 else []


def _dayforce(i, ident, q):
    tenant, board = i.split('/')
    st, _, b = fetch(f'https://www.dayforcehcm.com/api/{tenant}/V1/JobFeeds?includeActivePostingOnly=true&internalJobBoardCode={board}',
                     headers={'Accept': 'application/json'})
    try:
        return parse_dayforce(json.loads(b), tenant, board) if st == 200 else []
    except ValueError:
        return []


def _brassring(i, ident, q):
    """Home page (keeps its cookies) → the page's anonymous session values → the same keyword search its script
    posts (ProcessSortAndShowMoreJobs). No login, no CAPTCHA; a wall → recorded."""
    import http.cookiejar
    host, partner, site = i.split('/')
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    st, _, page = fetch(f'https://{host}/TGnewUI/Search/Home/Home?partnerid={partner}&siteid={site}', opener=op)
    ses = brassring_session(page) if st == 200 else None
    if not ses:
        return []
    body = {'partnerId': partner, 'siteId': site, 'keyword': q, 'location': '', 'keywordCustomSolrFields': '',
            'locationCustomSolrFields': '', 'linkId': '', 'Latitude': 0, 'Longitude': 0, 'facetfilterfields': {'Facet': []},
            'powersearchoptions': {'PowerSearchOption': []}, 'SortType': 'LastUpdated', 'pageNumber': 1,
            'encryptedSessionValue': ses[1]}
    st, _, b = fetch(f'https://{host}/TgNewUI/Search/Ajax/ProcessSortAndShowMoreJobs', json.dumps(body).encode(),
                     {'Content-Type': 'application/json; charset=utf-8', 'RFT': ses[0]}, opener=op)
    try:
        return parse_brassring(json.loads(b)) if st == 200 else []
    except ValueError:
        return []


def _clearcompany(i, ident, q):
    u = f'https://{i}' if i.startswith('apply.') else f'https://{i}/employment/job-openings.php?search=true'
    st, _, page = fetch(u)
    sid = clearcompany_site_id(page) if st == 200 else None
    if not sid:
        return []
    return parse_clearcompany(get_json(f'https://careers-api.clearcompany.com/v1/{sid}?keywords={urllib.parse.quote(q)}'))


# One adapter per system behind one interface (ats-scrapers' ScraperRegistry shape, without the async client).
def parse_amazon(d):
    """Pure (tested). amazon.jobs `search.json` → [{title, location, url}]: `jobs[].title`, `normalized_location`
    (else `location`), url = https://www.amazon.jobs + `job_path` (else /en/jobs/<id_icims>); rows without a title or a
    path / id are skipped."""
    out = []
    for j in (d or {}).get('jobs') or []:
        path = j.get('job_path') or (f"/en/jobs/{j['id_icims']}" if j.get('id_icims') else '')
        if j.get('title') and path:
            out.append(P(j['title'], j.get('normalized_location') or j.get('location') or '',
                         path if path.startswith('http') else 'https://www.amazon.jobs' + path))
    return out


def _amazon(i, ident, q):
    """amazon.jobs keyword search, U.S. only, first 50 (ats-scrapers amazon.py pages the whole site; one title is enough)."""
    return parse_amazon(get_json('https://www.amazon.jobs/en/search.json?' + urllib.parse.urlencode(
        {'base_query': q, 'country': 'USA', 'result_limit': 50, 'offset': 0, 'sort': 'relevant'})))


def parse_apple(d):
    """Pure (tested). jobs.apple.com `/api/v1/search` → [{title, location, url}], one entry per (posting × location):
    `res.searchResults[]` (or `searchResults[]`) with `postingTitle`, `locations[].name`, url =
    https://jobs.apple.com/en-us/details/<positionId>/<transformedPostingTitle> (slug 'role' when missing); a posting
    without locations gives one entry with location ''; entries without a title or positionId are skipped."""
    res = (d or {}).get('res') if isinstance((d or {}).get('res'), dict) else (d or {})
    out = []
    for it in res.get('searchResults') or []:
        pid, title = it.get('positionId') or it.get('id'), it.get('postingTitle')
        if not pid or not title:
            continue
        url = f"https://jobs.apple.com/en-us/details/{pid}/{it.get('transformedPostingTitle') or 'role'}"
        locs = [l.get('name') for l in it.get('locations') or [] if l.get('name')] or ['']
        out += [P(title, loc, url) for loc in locs]
    return out


def _apple(i, ident, q):
    """CSRF token, then the public search (ats-scrapers apple.py) with the keyword and the U.S. location filter."""
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    h = {'Origin': 'https://jobs.apple.com', 'Referer': 'https://jobs.apple.com/en-us/search', 'Accept': 'application/json'}
    try:
        with op.open(urllib.request.Request('https://jobs.apple.com/api/v1/CSRFToken', headers={**UA, **h}), timeout=20) as r:
            tok = r.headers.get('x-apple-csrf-token')
    except Exception:
        return []
    if not tok:
        return []
    body = json.dumps({'query': q, 'filters': {'locations': ['postLocation-USA']}, 'page': 1, 'locale': 'en-us', 'sort': '',
                       'format': {'longDate': 'MMMM D, YYYY', 'mediumDate': 'MMM D, YYYY'}}).encode()
    st, _, txt = fetch('https://jobs.apple.com/api/v1/search', body, {**h, 'Content-Type': 'application/json', 'X-Apple-CSRF-Token': tok}, opener=op)
    try:
        return parse_apple(json.loads(txt)) if st == 200 else []
    except ValueError:
        return []


def parse_google_list(page):
    """Pure (tested). A Google Careers results page → [{title, location, url}]: every link whose aria-label is
    "Learn more about <Title>" and whose href holds jobs/results/<digits> (attributes in double or single quotes); url = https://www.google.com/about/careers/
    applications/ + the href without a leading './' or '/about/careers/applications/' and without its query; location ''
    (the gate reads it from the posting). Duplicate urls are kept once, in page order."""
    out, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*>', str(page or ''), re.I):
        tag = m.group(0)
        lab = re.search(r'aria-label=(["\'])Learn more about (.+?)\1', tag)
        href = re.search(r'href=(["\'])([^"\']*jobs/results/\d+[^"\']*)\1', tag)
        if not lab or not href:
            continue
        h = H.unescape(href.group(2)).split('?')[0]
        h = re.sub(r'^(\./|/?about/careers/applications/|https://www\.google\.com/about/careers/applications/)', '', h)
        url = 'https://www.google.com/about/careers/applications/' + h.lstrip('/')
        if url not in seen:
            seen.add(url); out.append(P(H.unescape(lab.group(2)).strip(), '', url))
    return out


def _google(i, ident, q):
    """The public results page with the keyword, U.S. only (ats-scrapers google.py reads the same aria-label links)."""
    st, _, page = fetch('https://www.google.com/about/careers/applications/jobs/results?' + urllib.parse.urlencode(
        {'q': q, 'location': 'United States', 'hl': 'en_US'}))
    return parse_google_list(page) if st == 200 else []


# ---------- JSA-137 (2026-11-04): the rest of the ats-scrapers systems (Joey: 「把 GitHub 里面它的所有系统都搬进来。」) ----------
# Each one public, no login: the JSON / HTML the system's own careers page reads. Rewritten here from the endpoint
# notes in ats-scrapers (MIT, commit 6b44a1b); its code is not used. Moka (AES-wrapped list) and Darwinbox
# (Cloudflare, ats-scrapers needs its TLS-impersonation client) are detected and recorded only.
THRONE = {   # ByteDance's careers SaaS ("ATSx"): tenant → (API host, website-path header, site origin, posting URL prefix)
    'tiktok': ('api.lifeattiktok.com', 'tiktok', 'https://lifeattiktok.com', 'https://lifeattiktok.com/search/'),
    'usds': ('careers.tiktokusds.com', 'usds', 'https://careers.tiktokusds.com', 'https://careers.tiktokusds.com/usds/position/'),
    'bytedance': ('jobs.bytedance.com', 'en', 'https://joinbytedance.com', 'https://joinbytedance.com/search/'),
}


def throne_location(item):
    """Pure. A Throne / ATSx post's `city_info` parent chain → 'San Jose, California, United States of America';
    else the `city_list` names joined with '; '; else ''."""
    parts, node = [], (item or {}).get('city_info')
    while isinstance(node, dict):
        n = node.get('en_name') or node.get('name')
        if isinstance(n, str) and n:
            parts.append(n)
        node = node.get('parent')
    if parts:
        return ', '.join(parts)
    names = [c.get('en_name') or c.get('name') for c in (item or {}).get('city_list') or [] if isinstance(c, dict)]
    return '; '.join(dict.fromkeys(n for n in names if n))


def parse_throne(d, tenant):
    """Pure. `…/search/job/posts` JSON → postings; url = the tenant's posting prefix + id (+ '/detail' for USDS)."""
    pre = THRONE[tenant][3]
    out = []
    for j in ((d or {}).get('data') or {}).get('job_post_list') or []:
        if j.get('id') and (j.get('title') or j.get('name')):
            out.append(P(j.get('title') or j.get('name'), throne_location(j),
                         f"{pre}{j['id']}" + ('/detail' if tenant == 'usds' else '')))
    return out


def _throne(tenant, q):
    """Keyword search, 100 per page, ≤ 3 pages. USDS first takes the anonymous CSRF token its own page asks for
    (`/api/v1/csrf/token`) — the same call the site's script makes, no login."""
    api, path, origin, _ = THRONE[tenant]
    h = {'website-path': path, 'Origin': origin, 'Referer': origin + '/', 'Content-Type': 'application/json'}
    op, url = None, f'https://{api}/api/v1/public/supplier/search/job/posts'
    if tenant == 'usds':
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        h.update({'Referer': origin + '/usds/position', 'Portal-Channel': 'office', 'Portal-Platform': 'pc'})
        st, _, b = fetch(f'https://{api}/api/v1/csrf/token', b'{}', h, opener=op)
        try:
            h['x-csrf-token'] = json.loads(b)['data']['token'] if st == 200 else ''
        except (ValueError, KeyError, TypeError):
            return []
        url = f'https://{api}/api/v1/search/job/posts'
    out = []
    for off in (0, 100, 200):
        body = {'limit': 100, 'offset': off, 'keyword': q, 'category_id_list': [], 'subject_id_list': [],
                'location_code_list': [], 'job_function_id_list': [], **({'portal_entrance': 1} if tenant == 'usds' else {})}
        st, _, b = fetch(url, json.dumps(body).encode(), h, opener=op)
        try:
            d = json.loads(b) if st == 200 else {}
        except ValueError:
            d = {}
        got = parse_throne(d, tenant)
        out += got
        if len(got) < 100 or len(out) >= ((d.get('data') or {}).get('count') or 0):
            break
    return out


def _tiktok(i, ident, q):
    return _throne(i, q)


def _bytedance(i, ident, q):
    return _throne('bytedance', q)


def csod_session(page):
    """Pure. A Cornerstone career-site page → (token, API origin): the anonymous `csod.context.token` JWT the page
    hands its own search script (fallback: a `"token":"…"` field) and the regional `https://<x>.api.csod.com`
    (default https://na.api.csod.com); (None, None) without a token."""
    m = re.search(r'csod\.context\.token\s*=\s*[\'"]([^\'"]+)', page or '') or re.search(r'"token"\s*:\s*"([^"]+)"', page or '')
    if not m:
        return None, None
    a = re.search(r'(https://[a-z0-9-]+\.api\.csod\.com)', page or '')
    return m.group(1), a.group(1) if a else 'https://na.api.csod.com'


def parse_csod(d, host, site, slug):
    """Pure. `rec-job-search/external/jobs` JSON → postings; location = first location's city, state, country;
    url = https://<host>/ux/ats/careersite/<site>/job/<requisitionId>?c=<slug>."""
    out = []
    for r in ((d or {}).get('data') or {}).get('requisitions') or []:
        rid, t = r.get('requisitionId'), (r.get('displayJobTitle') or '').strip()
        if not rid or not t:
            continue
        locs = r.get('locations') or []
        l0 = locs[0] if locs and isinstance(locs[0], dict) else {}
        loc = ', '.join(str(l0[k]).strip() for k in ('city', 'state', 'country') if isinstance(l0.get(k), str) and l0[k].strip())
        out.append(P(t, loc, f'https://{host}/ux/ats/careersite/{site}/job/{rid}?c={slug}'))
    return out


def _cornerstone(i, ident, q):
    """Career-site page → its anonymous token → keyword search (`searchText`), 50 per page, ≤ 2 pages."""
    host, site = i.split('/')
    slug = host.split('.')[0]
    st, _, page = fetch(f'https://{host}/ux/ats/careersite/{site}/home?c={slug}')
    tok, api = csod_session(page) if st == 200 else (None, None)
    if not tok:
        return []
    h = {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json', 'Origin': f'https://{host}', 'Referer': f'https://{host}/'}
    out = []
    for n in (1, 2):
        body = {'careerSiteId': int(site), 'careerSitePageId': int(site), 'pageNumber': n, 'pageSize': 50, 'cultureId': 1,
                'cultureName': 'en-US', 'searchText': q}
        st, _, b = fetch(f'{api}/rec-job-search/external/jobs', json.dumps(body).encode(), h)
        try:
            d = json.loads(b) if st == 200 else {}
        except ValueError:
            d = {}
        got = parse_csod(d, host, site, slug)
        out += got
        if len(got) < 50:
            break
    return out


GEM_Q = ('query JobBoardList($boardId: String!) { oatsExternalJobPostings(boardId: $boardId) { jobPostings '
         '{ id extId title locations { name city isoCountry isRemote } } } }')


def parse_gem(d, slug):
    """Pure. Gem GraphQL batch answer → postings; url = https://jobs.gem.com/<slug>/<extId>; location = the location
    names joined with '; ' (name, else city, else 'Remote' for a remote one)."""
    first = d[0] if isinstance(d, list) and d and isinstance(d[0], dict) else {}
    out = []
    for p in ((first.get('data') or {}).get('oatsExternalJobPostings') or {}).get('jobPostings') or []:
        x = p.get('extId') or p.get('id')
        if x and p.get('title'):
            locs = [(l.get('name') or l.get('city') or ('Remote' if l.get('isRemote') else ''))
                    for l in p.get('locations') or [] if isinstance(l, dict)]
            out.append(P(p['title'], '; '.join(x2 for x2 in locs if x2), f'https://jobs.gem.com/{slug}/{x}'))
    return out


def _gem(i, ident, q):
    body = json.dumps([{'operationName': 'JobBoardList', 'variables': {'boardId': i}, 'query': GEM_Q}]).encode()
    return parse_gem(get_json('https://jobs.gem.com/api/public/graphql/batch', body), i)


def parse_pageup(page, base):
    """Pure. A PageUp listing page → postings: `a.job-link` anchors to …/job/<id>/…, location from the row's
    `class="location"`; relative links joined to base."""
    out, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*class="[^"]*\bjob-link\b[^"]*"[^>]*href="([^"]*/job/(\d+)[^"]*)"[^>]*>(.*?)</a>(.*?)(?=class="[^"]*\bjob-link\b|$)',
                         page or '', re.S | re.I):
        if m.group(2) in seen:
            continue
        seen.add(m.group(2))
        loc = re.search(r'class="location"[^>]*>(.*?)</', m.group(4)[:3000], re.S)
        out.append(P(re.sub(r'<[^>]+>', ' ', m.group(3)), re.sub(r'<[^>]+>', ' ', loc.group(1)) if loc else '',
                     urllib.parse.urljoin(base, H.unescape(m.group(1)))))
    return out


def _pageup(i, ident, q):
    """The tenant's listing (careers.pageuppeople.com/<client>/<channel>/<locale>/listing/), following the
    'more' link ≤ 3 pages. Tenants that moved to their own domain redirect there; the same markup is read."""
    st, fu, page = fetch(f'https://careers.pageuppeople.com/{i}/listing/')
    out = []
    for _ in range(3):
        if st != 200:
            break
        got = [p for p in parse_pageup(page, fu) if p['url'] not in {x['url'] for x in out}]
        out += got
        more = re.search(r'<a\b[^>]*class="[^"]*\bmore-link\b[^"]*"[^>]*href="([^"]+)"', page)
        if not got or not more:
            break
        st, fu, page = fetch(urllib.parse.urljoin(fu, H.unescape(more.group(1))))
    return out


def parse_personio(d, host):
    """Pure. Personio `search.json` list → postings; url = https://<host>/job/<id>; location = `office` (else the
    `offices` joined)."""
    out = []
    for j in d if isinstance(d, list) else []:
        if isinstance(j, dict) and j.get('id') and j.get('name'):
            out.append(P(j['name'], j.get('office') or '; '.join(j.get('offices') or []), f"https://{host}/job/{j['id']}"))
    return out


def _personio(i, ident, q):
    return parse_personio(get_json(f'https://{i}/search.json'), i)


def parse_recruiterbox(d):
    """Pure. jsapi.recruiterbox.com `/v1/openings` → postings; url = `hosted_url`; location = city, state, country."""
    out = []
    for j in (d or {}).get('objects') or []:
        l = j.get('location') or {}
        loc = ', '.join(str(l[k]).strip() for k in ('city', 'state', 'country') if l.get(k) and str(l[k]).strip())
        if j.get('title') and str(j.get('hosted_url') or '').startswith('https://'):
            out.append(P(j['title'], loc or ('Remote' if j.get('allows_remote') else ''), j['hosted_url']))
    return out


def _recruiterbox(i, ident, q):
    out = []
    for off in (0, 50, 100, 150):                       # 50 a page: a 100-row answer comes back cut off (2026-11-04)
        d = get_json(f'https://jsapi.recruiterbox.com/v1/openings?client_name={i}&offset={off}&limit=50')
        got = parse_recruiterbox(d)
        out += got
        if len(got) < 50:
            break
    return out


def schema_location(loc):
    """Pure. schema.org jobLocation (a Place or a list of them) → 'City, Region, Country' per place, joined '; '."""
    out = []
    for p in loc if isinstance(loc, list) else [loc]:
        a = (p or {}).get('address') if isinstance(p, dict) else None
        if isinstance(a, dict):
            s = ', '.join(str(a[k]).strip() for k in ('addressLocality', 'addressRegion', 'addressCountry')
                          if isinstance(a.get(k), str) and a[k].strip())
            if s:
                out.append(s)
    return '; '.join(dict.fromkeys(out))


def parse_softgarden(d):
    """Pure. Softgarden `jobs.feed.json` (schema.org DataFeed) → postings from `dataFeedElement[].item`."""
    out = []
    for e in (d or {}).get('dataFeedElement') or []:
        it = (e or {}).get('item') or {}
        if it.get('title') and str(it.get('url') or '').startswith('https://'):
            out.append(P(it['title'], schema_location(it.get('jobLocation')), it['url']))
    return out


def _softgarden(i, ident, q):
    return parse_softgarden(get_json(f'https://{i}/jobs.feed.json'))


def join_company_id(page):
    """Pure. A join.com company page → its numeric company id ('"company":{"id":N' or '"companyId":N'), or None."""
    m = re.search(r'"company"\s*:\s*\{\s*"id"\s*:\s*"?(\d+)', page or '') or re.search(r'"companyId"\s*:\s*"?(\d+)', page or '')
    return m.group(1) if m else None


def parse_join(d, slug):
    """Pure. join.com `/api/public/companies/<id>/jobs` → postings; url = `url`, else
    https://join.com/companies/<slug>/jobs/<idParam or id>; location = city name, region, country."""
    out = []
    for j in (d or {}).get('items') or []:
        if not j.get('title') or not j.get('id'):
            continue
        c = j.get('city') if isinstance(j.get('city'), dict) else {}
        loc = ', '.join(x for x in (c.get('cityName'), c.get('regionName'), c.get('countryName')) if x)
        out.append(P(j['title'], loc, j.get('url') or f"https://join.com/companies/{slug}/jobs/{j.get('idParam') or j['id']}"))
    return out


def _join(i, ident, q):
    st, _, page = fetch(f'https://join.com/companies/{i}')
    cid = join_company_id(page) if st == 200 else None
    out = []
    for n in range(1, 11):                               # pageSize > 5 answers 422 now (2026-11-04): ≤ 10 pages of 5
        d = get_json(f'https://join.com/api/public/companies/{cid}/jobs?locale=en-us&page={n}&pageSize=5') if cid else None
        out += parse_join(d, i)
        pg = (d or {}).get('pagination') or {}
        if not d or n >= (pg.get('pageCount') or pg.get('totalPages') or 1):
            break
    return out


def keka_identifier(page):
    """Pure. A Keka careers page → its portal identifier (a GUID in '/ats/documents/<id>/careerportal/' or
    '/careers/api/embedjobs/js/<id>'), lower-cased; None when absent."""
    m = re.search(r'/ats/documents/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/careerportal/', page or '', re.I) \
        or re.search(r'/careers/api/embedjobs/js/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', page or '', re.I)
    return m.group(1).lower() if m else None


def parse_keka(d, host):
    """Pure. Keka `embedjobs/<portal>/active/<id>` list → postings; url = https://<host>/careers/jobdetails/<id>;
    location = each `jobLocations` city, state, countryName, joined '; '."""
    out = []
    for j in d if isinstance(d, list) else []:
        if not isinstance(j, dict) or not j.get('id') or not j.get('title'):
            continue
        locs = [', '.join(x for x in (l.get('city'), l.get('state'), l.get('countryName')) if isinstance(x, str) and x)
                for l in j.get('jobLocations') or [] if isinstance(l, dict)]
        out.append(P(j['title'], '; '.join(x for x in locs if x), f"https://{host}/careers/jobdetails/{j['id']}"))
    return out


def _keka(i, ident, q):
    host, _, portal = i.partition('/')
    portal = portal or 'default'
    st, _, page = fetch(f'https://{host}/careers' + ('' if portal == 'default' else f'/{portal}'))
    kid = keka_identifier(page) if st == 200 else None
    return parse_keka(get_json(f'https://{host}/careers/api/embedjobs/{portal}/active/{kid}'), host) if kid else []


def parse_gupy(page, host):
    """Pure. A Gupy board page → postings from the Next.js `__NEXT_DATA__` `props.pageProps.jobs`; url =
    https://<host>/jobs/<id>; location = workplace address city, state short name, country."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page or '', re.S)
    try:
        jobs = json.loads(m.group(1))['props']['pageProps'].get('jobs') or [] if m else []
    except (ValueError, KeyError, TypeError, AttributeError):
        jobs = []
    out = []
    for j in jobs:
        if isinstance(j, dict) and j.get('id') and j.get('title'):
            a = ((j.get('workplace') or {}).get('address') or {}) if isinstance(j.get('workplace'), dict) else {}
            loc = ', '.join(x for x in (a.get('city'), a.get('stateShortName') or a.get('state'), a.get('country')) if x)
            out.append(P(j['title'], loc, f"https://{host}/jobs/{j['id']}"))
    return out


def _gupy(i, ident, q):
    st, _, page = fetch(f'https://{i}/')
    return parse_gupy(page, i) if st == 200 else []


def parse_hrmos(page):
    """Pure. An HRMOS jobs page → postings: each `pg-list-cassette` card's link to /pages/<tenant>/jobs/<id>, its
    <h2> title and `sg-tag-location`."""
    out = []
    for card in re.split(r'<li class="pg-list-cassette\b', page or '')[1:]:
        a = re.search(r'href="(https://hrmos\.co/pages/[\w-]+/jobs/[\w.-]+)"', card)
        t = re.search(r'<h2[^>]*>(.*?)</h2>', card, re.S)
        if a and t:
            loc = re.search(r'class="sg-tag-location"[^>]*>(.*?)</li>', card, re.S)
            out.append(P(re.sub(r'<[^>]+>', ' ', t.group(1)), re.sub(r'<[^>]+>', ' ', loc.group(1)) if loc else '', a.group(1)))
    return out


def _hrmos(i, ident, q):
    out = []
    for n in (1, 2, 3):
        st, _, page = fetch(f'https://hrmos.co/pages/{i}/jobs' + (f'?page={n}' if n > 1 else ''))
        got = [p for p in parse_hrmos(page) if p['url'] not in {x['url'] for x in out}] if st == 200 else []
        out += got
        if len(got) < 100:
            break
    return out


def parse_herp(page, slug):
    """Pure. A HERP Hire board (herp.careers/v1/<slug>) → postings: `requisition-list-card__header-anchor` links to
    /v1/<slug>/<id> with their <h2> title; location '' (on the posting page only)."""
    out, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*requisition-list-card__header-anchor[^>]*href="(/v1/' + re.escape(slug) + r'/[^"/?#]+)"[^>]*>\s*<h2[^>]*>(.*?)</h2>',
                         page or '', re.S):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(P(re.sub(r'<[^>]+>', ' ', m.group(2)), '', 'https://herp.careers' + m.group(1)))
    return out


def _herp(i, ident, q):
    st, _, page = fetch(f'https://herp.careers/v1/{i}')
    return parse_herp(page, i) if st == 200 else []


def beisen_portal(page):
    """Pure. Beisen `portal/registerSystemInfo` page → the `PortalId` of its inline `var BSGlobal = {…}`, or None."""
    m = re.search(r'var\s+BSGlobal\s*=\s*(\{)', page or '')
    try:
        cfg, _ = json.JSONDecoder().raw_decode(page, m.start(1)) if m else ({}, 0)
    except ValueError:
        return None
    pid = cfg.get('PortalId') if isinstance(cfg, dict) else None
    return str(pid).strip() if pid not in (None, '') else None


def parse_beisen(d, host):
    """Pure. Beisen `GetJobAdPageList` JSON → postings: `Data[]` JobAdName / JobAdId / LocNames; url =
    https://<host>/portal/jobs/<JobAdId>."""
    out = []
    for j in (d or {}).get('Data') or []:
        if isinstance(j, dict) and j.get('JobAdId') and j.get('JobAdName'):
            out.append(P(j['JobAdName'], '; '.join(j.get('LocNames') or []), f"https://{host}/portal/jobs/{j['JobAdId']}"))
    return out


def _beisen(i, ident, q):
    st, _, page = fetch(f'https://{i}/portal/registerSystemInfo', headers={'Accept': 'text/html'})
    pid = beisen_portal(page) if st == 200 else None
    if not pid:
        return []
    body = {'PageIndex': 0, 'PageSize': 50, 'KeyWords': q, 'SpecialType': 0, 'PortalId': pid, 'DisplayFields': ['Category', 'LocId', 'Org']}
    return parse_beisen(get_json(f'https://{i}/api/Jobad/GetJobAdPageList', json.dumps(body).encode(),
                                 {'Accept': 'application/json', 'Referer': f'https://{i}/social/jobs'}), i)


ADAPTERS = {'icims': _icims, 'oraclecloud': _oracle, 'successfactors': _sf, 'taleo': _taleo, 'smartrecruiters': _smartrecruiters,
            'workable': _workable, 'jobvite': _jobvite, 'bamboohr': _bamboohr, 'ultipro': _ultipro, 'eightfold': _eightfold,
            'phenom': _phenom, 'avature': _avature, 'jazzhr': _jazzhr, 'rippling': _rippling, 'breezy': _breezy, 'applicantpro': _applicantpro,
            'recruitee': _recruitee, 'teamtailor': _teamtailor, 'pinpoint': _pinpoint, 'adp': _adp, 'paycom': _paycom,
            'paylocity': _paylocity, 'dayforce': _dayforce, 'brassring': _brassring, 'clearcompany': _clearcompany,
            'dover': _dover, 'amazon': _amazon, 'apple': _apple, 'google': _google,
            'tiktok': _tiktok, 'bytedance': _bytedance, 'cornerstone': _cornerstone, 'gem': _gem, 'pageup': _pageup,
            'personio': _personio, 'recruiterbox': _recruiterbox, 'softgarden': _softgarden, 'join': _join, 'keka': _keka,
            'gupy': _gupy, 'hrmos': _hrmos, 'herp': _herp, 'beisen': _beisen}
assert set(ADAPTERS) == set(SYSTEMS)


def note_for(systems):
    """The first security-check note recorded for any of these (system, ident) boards, or ''."""
    for s, i in systems:
        if s in SYSTEMS and isinstance(i, str):
            c = clean_ident(s, i)
            n = c and NOTES.get((s, c if s not in NEEDS_SITE else f'{c}@{site_of(i)}'))
            if n:
                return n
    return ''


def postings(system, ident, query):
    """[{title, location, url}] for the posting search (or whole board, for the list systems) of one company board.
    Cached per (system, board, query); a list system ignores query (Avature searches when it can, so its query counts).
    Never raises."""
    if system not in SYSTEMS or not isinstance(ident, str):
        return []
    i = clean_ident(system, ident)
    if not i:
        return []
    key = (system, i if system not in NEEDS_SITE else f'{i}@{site_of(ident)}',
           '' if system in LISTS and system != 'avature' else (query or '').lower())
    with _clock:
        if key in _cache:
            return _cache[key]
        if (system, key[1]) in NOTES:
            return []
    try:
        out = ADAPTERS[system](i, ident, query or '') if (query or system in LISTS) else []
    except Blocked as e:
        NOTES[(system, key[1])] = str(e)
        out = []
    except Exception:
        out = []
    out = [p for p in out if p['title'] and p['url']]
    with _clock:
        _cache[key] = out
    return out


def live(system, ident):
    """JSA-119. True when this board lists at least one posting now: the whole list for a list system, an empty-keyword
    search for a search system (every search endpoint here answers '' with its newest postings). Cached; a security
    check → False (recorded in NOTES, never bypassed)."""
    if system not in SYSTEMS or not isinstance(ident, str):
        return False
    i = clean_ident(system, ident)
    if not i:
        return False
    if system in LISTS:
        return bool(postings(system, ident, ''))
    key = (system, i if system not in NEEDS_SITE else f'{i}@{site_of(ident)}', '\0live')
    with _clock:
        if key in _cache:
            return _cache[key]
        if (system, key[1]) in NOTES:
            return False
    try:
        ok = any(p['title'] and p['url'] for p in ADAPTERS[system](i, ident, ''))
    except Blocked as e:
        NOTES[(system, key[1])] = str(e)
        ok = False
    except Exception:
        ok = False
    with _clock:
        _cache[key] = ok
    return ok


if __name__ == '__main__':
    import sys
    for p in postings(sys.argv[1], sys.argv[2], ' '.join(sys.argv[3:])):
        print(f"{p['title']} | {p['location']} | {p['url']}")
