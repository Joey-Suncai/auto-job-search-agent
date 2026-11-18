#!/usr/bin/env python3
"""Aggregator-only rows → the company's own careers system (JSA-055 ①, JSA-091; 2026-11-02).

jobright.ai, Handshake and LinkedIn rows carry no company link (a jobright page is never fetched — it answers scripts with a
security check; a Handshake page needs a login). resolve_aggregator.py (JSA-046) already tried the boards seen on other
rows and slug guesses; this script goes in through the company's own website instead:

  1. company name → candidate domains: references/company_domains.json (hand-kept brands / parents), other rows' own
     sites, Clearbit + Wikidata lookups (country-code sites dropped), a bracketed acronym, then guesses (acme.com,
     acmecorp.com, …). A guessed / Clearbit homepage counts only when its names (title, og tags, JSON-LD, copyright line)
     name the company (wrong-company guard: no parked page, no country-code host). A security check on the company's own
     domain stops the search there (never a fallback to a weaker guess). A 'company' that is a job title is skipped.
  2. homepage → links that say careers / jobs (search-jobs links and ATS links first; plus careers.<domain>,
     <domain>/careers) and the DNS names (CNAME) of careers. / jobs. → every page, redirect target and vendor host name is
     scanned for the ATS it links to: myworkdayjobs / greenhouse / lever / ashby (searchable) and icims,
     oraclecloud, successfactors, taleo, smartrecruiters, workable, jobvite, bamboohr, adp, ultipro, paylocity,
     eightfold, phenom, avature, dayforce, dover, … (searched through ats_search.py since JSA-112 / JSA-117; ADP
     myjobs.adp.com is still recorded by name only), and since JSA-137 tiktok / bytedance, cornerstone (csod), gem,
     pageup, personio, recruiterbox (Trakstar), softgarden, join.com, keka, gupy, hrmos, herp, beisen (moka, darwinbox:
     recorded only). page_systems: a page that is itself an SAP SuccessFactors RMK career site (rmk_site), an Eightfold
     site on the company's domain (window._EF_GROUP_ID — apply.careers.microsoft.com) or an Avature site on it
     (/careers/SearchJobs) counts as that system's hit on its own host. TikTok / ByteDance names go straight to their
     search (big_tech).
  3. searchable system → its public posting list (Greenhouse / Lever / Ashby APIs, Workday CXS search like
     wd_search.py) → the posting whose title matches (match_posting: normalised title, Jaccard ≥ 0.75; when several
     postings tie on title the row's city decides; still tied = no guess).

A page that answers with a security check (a Greenhouse employer challenge, captcha, 403 with a bot wall) → that company is
skipped, never bypassed. Only public pages are read.

Writes (only with --write, from the main checkout): ats_url + ats_resolved (how) + ats_resolved_on, or ats_unresolved
(why) + ats_system (the system found, or '' when none). Never touches url, elig or any other field. The 08:45 gate
re-reads a row whose ats_resolved_on ≥ elig_checked (gate_run.py), so the real JD decides 可投 / 不可投 / 重复.

    python3 resolve_careers.py --all [--limit N] [--company NAME] [--ids J1,J2] [--write] [--report out.json]
    Wellfound rows (JSA-171): the names the title states (title_companies) are searched too when the label finds nothing.
    python3 resolve_careers.py --all --render …        # + headless Chrome for A/B companies (venv python)
    python3 resolve_careers.py --all --render-all …    # + headless Chrome for every site with no searchable system
    python3 resolve_careers.py --apply out.json [--drop ID,ID]     # write a reviewed report (spot-check rejects dropped)
    python3 resolve_careers.py --all --other --report out.json     # only rows an earlier run left on a system ats_search.py reads
    python3 resolve_careers.py --all --systems adp,paycom --report out.json   # only rows left on these systems
    python3 resolve_careers.py --all --redo old.json [--codes no_system,no_match] --report new.json   # re-try those rows only
    python3 resolve_careers.py --all --redo old.json --codes … --inventory-only --report new.json     # inventory hints only
    A --report run keeps new.json.part.jsonl as it goes; the same command again resumes from it (--fresh = start over; JSA-129)
Spec + DeepSeek-written cases: scripts/test_cases/resolve_careers_*; harness scripts/test_resolve_careers.py.
"""
import html as H, json, os, re, sys, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
import resolve_builtin as RB  # noqa: E402
import resolve_aggregator as RA  # noqa: E402
import ats_search as AS  # noqa: E402  (JSA-112: posting search on the other systems)

SEARCHABLE = ('workday', 'greenhouse', 'lever', 'ashby')
# (system, regex on a URL; group 1 = the board token / host). Order = preference when a page links several.
ATS_RX = [
    ('workday', re.compile(r'https?://([\w-]+\.wd\d+\.myworkday(?:jobs|site)\.com/[^\s"\'<>?#]*)', re.I)),
    ('workday', re.compile(r'https?://(wd\d+\.myworkdaysite\.com/(?:[a-z]{2}-[A-Z]{2}/)?recruiting/[^\s"\'<>?#]*)', re.I)),
    ('greenhouse', re.compile(r'(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=|embed/job_app\?for=)?([\w-]+)', re.I)),
    ('greenhouse', re.compile(r'boards-api\.greenhouse\.io/v1/boards/([\w-]+)', re.I)),
    ('lever', re.compile(r'jobs\.(?:eu\.)?lever\.co/([\w.-]+)', re.I)),
    ('ashby', re.compile(r'jobs\.ashbyhq\.com/([^/?#"\'\s<>]+)', re.I)),
    ('icims', re.compile(r'([\w-]+\.icims\.com)', re.I)),
    ('oraclecloud', re.compile(r'([\w-]+\.fa\.[\w-]+\.oraclecloud\.com)', re.I)),
    ('successfactors', re.compile(r'(career\d*(?:preview)?\.(?:successfactors\.(?:com|eu)|sapsf\.(?:com|eu))/career\?[^\s"\'<>#]*?'
                                  r'company=[\w.-]+)', re.I)),                                  # JSA-117: keeps the company id
    ('successfactors', re.compile(r'([\w.-]*(?:successfactors\.(?:com|eu)|sapsf\.com|jobs\.sap\.com|jobs2web\.com))', re.I)),
    ('taleo', re.compile(r'([\w-]+\.tbe\.taleo\.net/[\w-]+/ats/careers/[^\s"\'<>#]*?org=[\w-]+(?:&(?:amp;)?cws=\d+)?)', re.I)),  # Business Edition
    ('taleo', re.compile(r'(?<![\w.-])((?!tbe\.)[\w-]+\.taleo\.net)', re.I)),
    ('smartrecruiters', re.compile(r'(?:jobs|careers|www)\.smartrecruiters\.com/(?!(?:company|customers|resources|blog|about|platform|'
                                   r'pricing|product|solutions|demo|legal|privacy|jobs|careers|integrations)\b)([A-Za-z][\w-]+)', re.I)),
    ('workable', re.compile(r'apply\.workable\.com/([\w-]+)', re.I)),
    ('jobvite', re.compile(r'jobs\.jobvite\.com/((?:careers/)?[\w-]+)', re.I)),     # 'careers/acme' form too (JSA-112)
    ('bamboohr', re.compile(r'([\w-]+\.bamboohr\.com)', re.I)),
    ('adp', re.compile(r'(workforcenow(?:\.cloud)?\.adp\.com/mascsr/default/mdf/recruitment/recruitment\.html\?[^\s"\'<>]+|'
                       r'workforcenow\.adp\.com|myjobs\.adp\.com/[\w-]+)', re.I)),           # full URL keeps cid / ccId (JSA-112)
    ('ultipro', re.compile(r'((?:recruiting\d*|n\d+)\.ultipro\.(?:com|ca)/[\w-]+(?:/JobBoard/[\w-]{36})?)', re.I)),   # .ca: ats-scrapers
    ('paylocity', re.compile(r'(recruiting\.paylocity\.com/recruiting/jobs/(?:all|list)/[0-9a-f-]{36}|recruiting\.paylocity\.com)', re.I)),
    ('eightfold', re.compile(r'([\w-]+\.eightfold\.ai)', re.I)),
    ('eightfold', re.compile(r'(?<![\w.-])(apply\.careers\.[\w-]+\.(?:com|net|org|io))', re.I)),     # custom domain (an employer; JSA-137)
    ('phenom', re.compile(r'(cdn\.phenompeople\.com|[\w-]+\.phenompeople\.com)', re.I)),
    ('avature', re.compile(r'([\w-]+\.avature\.net)', re.I)),
    ('avature', re.compile(r'https?://((?!www\.)[\w-]+(?:\.[\w-]+){2,}(?:/[a-z]{2}[_-][a-z]{2})?)/careers/(?:SearchJobs|JobDetail)\b', re.I)),  # own domain (IBM)
    ('dayforce', re.compile(r'(jobs\.dayforcehcm\.com/(?:[a-z]{2}-[a-z]{2}/)?[\w-]+(?:/[\w-]+)?)', re.I)),   # tenant / board (JSA-112)
    # JSA-137 (2026-11-04): the rest of ats-scrapers' company systems, searched through ats_search.py
    ('tiktok', re.compile(r'(?<![\w.-])((?:api\.)?lifeattiktok\.com|careers\.tiktokusds\.com)', re.I)),
    ('bytedance', re.compile(r'(?<![\w.-])((?:jobs\.bytedance|joinbytedance)\.com)', re.I)),
    ('cornerstone', re.compile(r'(?<![\w.-])([\w-]+\.csod\.com(?:/ux/ats/careersite/\d+)?)', re.I)),
    ('gem', re.compile(r'jobs\.gem\.com/([\w-]+)', re.I)),
    ('pageup', re.compile(r'careers\.pageuppeople\.com/((?:mob/)?\d+/[\w-]+/[a-z]{2}(?:-[a-z]{2})?)', re.I)),
    ('personio', re.compile(r'([\w-]+\.jobs\.personio\.(?:com|de))', re.I)),
    ('recruiterbox', re.compile(r'(?<![\w.-])([\w-]+)\.(?:recruiterbox\.com|hire\.trakstar\.com)', re.I)),   # Trakstar Hire
    ('softgarden', re.compile(r'([\w-]+\.career\.softgarden\.de)', re.I)),
    ('join', re.compile(r'(?<![\w.-])join\.com/companies/([\w.-]+)', re.I)),
    ('keka', re.compile(r'([\w-]+\.keka\.com/careers(?:/[\w-]+)?)', re.I)),
    ('gupy', re.compile(r'(?<![\w.-])([\w-]+\.gupy\.io)', re.I)),
    ('hrmos', re.compile(r'hrmos\.co/pages/([\w-]+)', re.I)),
    ('herp', re.compile(r'herp\.careers/v1/([\w-]+)', re.I)),
    ('beisen', re.compile(r'(?<![\w.-])([\w-]+\.zhiye\.com)', re.I)),
    # recorded by name only (2026-11-03 survey of "no system found" sites, JSA-055)
    ('brassring', re.compile(r'((?:s?jobs|ts)\.brassring\.com/[^\s"\'<>#]*?partnerid=[^\s"\'<>#]+|(?:s?jobs|ts)\.brassring\.com)', re.I)),
    ('jazzhr', re.compile(r'([\w-]+\.applytojob\.com|app\.jazz\.co)', re.I)),
    ('clearcompany', re.compile(r'(apply\.clearcompany\.com/[\w-]+|[\w-]+\.hrmdirect\.com|apply\.clearcompany\.com)', re.I)),
    ('paycom', re.compile(r'(paycomonline\.net/v4/ats/web\.php/(?:portal|jobs)/[0-9a-f]{32}|'
                          r'paycomonline\.net/v4/ats/web\.php/jobs\?(?:[^\s"\'<>#]*?&(?:amp;|#038;)?)?clientkey=[0-9a-f]{32}|paycomonline\.net)', re.I)),
    ('rippling', re.compile(r'ats\.rippling\.com/([\w-]+)', re.I)),
    ('breezy', re.compile(r'([\w-]+\.breezy\.hr)', re.I)),
    ('applicantpro', re.compile(r'(?<![\w.-])([\w-]+\.applicantpro\.com)', re.I)),   # public jobs JSON (JSA-149, Caselle 11-04)
    ('recruitee', re.compile(r'([\w-]+\.recruitee\.com)', re.I)),
    ('teamtailor', re.compile(r'([\w-]+\.teamtailor\.com)', re.I)),
    ('pinpoint', re.compile(r'([\w-]+\.pinpointhq\.com)', re.I)),
    ('dover', re.compile(r'app\.dover\.(?:io|com)/((?:apply/[^/\s"\'<>?#]+|[^/\s"\'<>?#]+/careers)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
                         r'[0-9a-f]{4}-[0-9a-f]{12})', re.I)),                    # job id or client id (JSA-117)
    ('dover', re.compile(r'app\.dover\.(?:io|com)/apply/([\w-]+)(?![\w%.-]*/[0-9a-f]{8}-)', re.I)),   # name only: recorded, not searched
    ('njoyn', re.compile(r'([\w-]+\.njoyn\.com)', re.I)),                 # CGI's own (2026-11-03, JSA-069)
    ('moka', re.compile(r'((?:app|hire-r1)\.mokahr\.com/(?:social|campus)-recruitment/[\w-]+/\d+)', re.I)),   # AES-wrapped list: recorded
    ('darwinbox', re.compile(r'(?<![\w.-])([\w-]+\.darwinbox\.(?:in|com))', re.I)),   # a Greenhouse employer wall (ats-scrapers impersonates): recorded
]
BAD_TOKENS = {'embed', 'jobs', 'v1', 'boards', 'job_board', 'job_app', 'api', 'www', 'static', 'assets', 'js', 'css', 'search'}
GENERIC = {'and', 'the', 'of', 'group', 'inc', 'llc', 'co', 'company', 'corporation', 'corp', 'services', 'solutions',
           'systems', 'international', 'global', 'national', 'american', 'america', 'partners', 'capital', 'management',
           'health', 'bank', 'financial', 'university', 'department', 'state', 'institute', 'team', 'securities', 'llp', 'lp',
           'limited', 'partnership', 'us', 'usa', 'north', 'south', 'new', 'first', 'general', 'united',
           'incorporated', 'companies', 'enterprises', 'plc'}
CITY_TAIL = re.compile(r'(?:\s*[-–]|,)\s*[A-Z][\w .\']+,\s*[A-Z]{2}\s*$')    # '… Intern - El Segundo, CA'
NOISE = re.compile(r'\((?:full[- ]time|part[- ]time|remote|hybrid|on[- ]?site|contract)\)|\b(?:full[- ]time|united states|usa|u\.s\.)\b'
                   r'|\s[-–|,]\s*(?:remote|hybrid|on[- ]?site|united states|us)\s*$', re.I)
CHALLENGE = re.compile(r'just a moment\.\.\.|cf-chl|challenge-platform|attention required|captcha|are you a robot|'
                       r'access denied|request unsuccessful\. incapsula|perimeterx|px-captcha|distil_r_captcha|_incapsula_', re.I)


# ---------- pure steps (tested) ----------
def company_words(company):
    """Distinctive lower-case words of the name (no suffixes / generic words); [] when nothing distinctive is left."""
    k = re.sub(r'[^a-z0-9 ]+', ' ', RB.company_key(re.sub(r'\(.*?\)', ' ', company or ''))).split()
    ws = [w for w in k if w not in GENERIC and len(w) > 1]
    return ws or [w for w in k if w not in ('the', 'and', 'of') and len(w) > 1]      # 'Bank of America' → bank, america


def domain_candidates(company):
    """'Booz Allen Hamilton' → ['boozallenhamilton.com', 'boozallen.com', 'booz.com', 'booz-allen-hamilton.com'] (≤ 5, no dupes)."""
    raw = re.sub(r'\(.*?\)', ' ', company or '')
    raw = re.split(r'\s+(?:and|&)\s+.*\b(?:securities|sons)\b', raw, flags=re.I)[0]   # 'Citadel and Citadel Securities' → 'Citadel'
    k = [w for w in re.sub(r'[^a-z0-9 ]+', ' ', RB.company_key(raw)).split() if w not in ('the', 'and')]
    if not k or not re.fullmatch(r'[a-z0-9 ]+', ' '.join(k)):
        return []
    out = [''.join(k), ''.join(k[:2]), k[0], '-'.join(k)]
    if len(k[0]) < 3 and len(k) > 1:
        out.remove(k[0])
    if len(k) >= 3:
        out.append(''.join(w[0] for w in k))                    # 'Tata Consultancy Services' → tcs.com
    doms = [d + '.com' for d in out if len(d) >= 2][:6] + [''.join(k) + '.org']   # NORC → norc.org (non-profits)
    return list(dict.fromkeys(doms))


FOREIGN_OK = {'com', 'org', 'net', 'edu', 'gov', 'mil', 'io', 'ai', 'co', 'us', 'app', 'dev', 'tech', 'health', 'bank',
              'inc', 'group', 'jobs', 'careers', 'coop', 'biz', 'info', 'energy', 'earth', 'me', 'tv', 'chat', 'so', 'xyz', 'cloud'}
PARKED = re.compile(r'domain (?:name )?(?:is|may be) for sale|buy this domain|this domain (?:name )?(?:is|has been) registered|'
                    r'parkingcrew|sedoparking|bodis\.com|above\.com/marketing|dan\.com|hugedomains|domain parking|'
                    r'parked (?:free|domain)|afternic', re.I)
DOMAIN_TOKEN = re.compile(r'\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|io|ai|co|us|edu|gov|biz|info)\b', re.I)


def reg_label(host):
    """'www.boozallen.com' → 'boozallen'; 'x.co.uk' → 'x'."""
    parts = (host or '').lower().split('.')
    return parts[-3] if len(parts) >= 3 and parts[-2] in ('co', 'com', 'org', 'ac') else parts[-2] if len(parts) >= 2 else parts[0]


def foreign_host(host):
    """A country-code site ('amway.my', 'lenovo.com.cn', 'regeneron.ie') — a U.S. posting's employer is looked up on its
    generic / U.S. site; the local subsidiary's site is another page (2026-11-03: 19 of 211 sites were such)."""
    tld = (host or '').lower().rstrip('.').split('.')[-1]
    return bool(tld) and tld not in FOREIGN_OK


def is_parked(final_url, page):
    """Domain-parking / for-sale page, or a 'ww38.' parking redirect."""
    host = (urllib.parse.urlsplit(final_url or '').hostname or '').lower()
    return bool(re.match(r'ww\d+\.', host)) or bool(PARKED.search((page or '')[:50000]))


def page_names(page):
    """The text where a site names its owner, lower-case: <title>, og:site_name, og:title, application-name, a JSON-LD
    "name", copyright lines (© / &copy; / Copyright + ≤ 60 characters) and logo alt text. Domain-like tokens
    ('nissan.com') are removed — a page that names only its own address is a parked or unrelated page."""
    p = page or ''
    bits = [m.group(1) for m in re.finditer(r'<title[^>]*>(.*?)</title>', p, re.S | re.I)][:1]
    for prop in ('og:site_name', 'og:title', 'application-name', 'apple-mobile-web-app-title'):
        bits += re.findall(r'(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]*content=["\']([^"\']+)', p, re.I)[:1]
        bits += re.findall(r'content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']' + re.escape(prop) + r'["\']', p, re.I)[:1]
    bits += re.findall(r'"@type"\s*:\s*"(?:Organization|Corporation|WebSite)"[^{}]{0,300}?"name"\s*:\s*"([^"]{1,80})"', p)[:2]
    bits += re.findall(r'(?:©|&copy;|&#169;|\(c\)|copyright)\s*(?:\d{4}\s*[-–]?\s*)*(?:\d{4})?\s*([^<"{}]{2,60})', p, re.I)[:3]
    bits += re.findall(r'<img\b[^>]*\balt=["\']([^"\']{2,80})["\'][^>]*class=["\'][^"\']*logo', p, re.I)[:1]
    bits += re.findall(r'<img\b[^>]*class=["\'][^"\']*logo[^"\']*["\'][^>]*\balt=["\']([^"\']{2,80})["\']', p, re.I)[:1]
    return DOMAIN_TOKEN.sub(' ', H.unescape(' '.join(bits))).lower()


LEAD_GENERIC = {'american', 'national', 'united', 'global', 'first', 'general', 'international', 'north', 'south', 'east', 'west',
                'central', 'pacific', 'atlantic', 'new', 'great', 'state', 'city', 'county', 'university', 'health', 'bank', 'capital',
                'financial', 'insurance', 'energy', 'data', 'digital', 'smart', 'tech', 'technology', 'technologies', 'systems', 'software',
                'consulting', 'partners', 'medical', 'care', 'home', 'life', 'team', 'business', 'precision', 'advanced', 'applied',
                'premier', 'quality', 'superior', 'summit', 'pioneer', 'liberty', 'apex', 'blue', 'green', 'red', 'black', 'white', 'gold'}


def lead_word(label, ws):
    """Pure (tested). The host label is exactly the name's first distinctive word, and that word can stand for the company:
    ≥ 4 letters and not a common word (LEAD_GENERIC) — 'idemia' for IDEMIA Public Security, 'americo' for Americo Financial
    Life and Annuity; never 'american' / 'global' / 'precision'. names_company also needs the word twice in the page names
    (title + og tag / copyright) and another word of the name (≥ 3 letters) somewhere in the page — nissan.com (Uzi
    Nissan's memorial page) names 'nissan' twice but never 'motor'."""
    return bool(ws) and len(ws) > 1 and label == ws[0] and len(ws[0]) >= 4 and ws[0] not in LEAD_GENERIC and not ws[0].isdigit()


def names_company(page, company, final_url=''):
    """Does the homepage belong to this company? (wrong-company guard)
    · the page's host (after redirects) must look like the company: its main label contains a distinctive word of the
      name (≥ 3 letters), the squashed name contains the label, or the label is the initials ('tcs') — a redirect to
      linkedin.com / a domain-parking site fails; a country-code host ('amway.my') or a parked page fails too;
    · the page's names (page_names: title, og tags, JSON-LD name, copyright line, logo alt) must contain the whole name
      squashed together ('an employer' vs 'JPMorgan Chase') or every one of the first two distinctive words ('Great
      Minds' needs both great and minds); when the host label IS the name (the distinctive words squashed — 'dematic',
      'erieinsurance') the first distinctive word in those names is enough, or the words as a phrase three times anywhere
      in the page (a homepage whose title is a slogan)."""
    text = page_names(page)
    squash = re.sub(r'[^a-z0-9]', '', text)
    ws = company_words(company)
    if not ws:
        return False
    strong = False
    if final_url:
        host = (urllib.parse.urlsplit(final_url).hostname or '').lower()
        if host and (foreign_host(host) or is_parked(final_url, page)):
            return False
        if host:
            label = reg_label(host)
            whole = re.sub(r'[^a-z0-9]', '', RB.company_key(company))
            initials = {''.join(w[0] for w in re.sub(r'[^a-z0-9 ]+', ' ', x).split())        # 'sig' = Susquehanna Int'l Group
                        for x in (RB.company_key(company), re.sub(r'\(.*?\)', ' ', company or '').lower(),
                                  ' '.join(w for w in re.sub(r'[^a-z0-9 ]+', ' ', RB.company_key(company)).split()
                                           if w not in ('of', 'the', 'and', 'for')))}   # 'bcbsm' = an employer (11-04)
            if not (any(w in label for w in ws if len(w) >= 3) or label in whole or label in initials):
                return False
            strong = label in (''.join(ws), whole)
            if strong and not text.strip():           # the whole name is the domain and the page names render by JS (Precision Castparts 11-04)
                return True
            body = re.sub(r'<[^>]+>', ' ', (page or '').lower())
            if lead_word(label, ws) and len(re.findall(r'\b' + re.escape(ws[0]) + r'\b', text)) >= 2 \
                    and any(re.search(r'\b' + re.escape(w) + r'\b', body) for w in ws[1:] if len(w) >= 3):   # and another word of the name in the page (not nissan.com's memorial)
                return True                           # the parent brand's own domain: idemia.com for "IDEMIA Public Security" (11-04)
    elif is_parked('', page):
        return False
    if ''.join(ws) in squash:
        return True
    if strong and (re.search(r'\b' + re.escape(ws[0]) + r'\b', text)
                   or len(re.findall(r'\b' + r'\W{0,3}'.join(map(re.escape, ws)) + r'\b', (page or '').lower())) >= 3):
        return True
    return all(re.search(r'\b' + re.escape(w) + r'\b', text) for w in ws[:2])


SEARCH_LINK = re.compile(r'search\W*(?:all\W*)?(?:jobs|roles|openings|positions|careers)|(?:open|current|all|view)\W*(?:jobs|roles|'
                         r'positions|openings|opportunities)|job\W*(?:search|openings|listings|board)|see\W*(?:all\W*)?(?:jobs|'
                         r'openings|roles)|find\W*(?:a\W*|your\W*)?(?:job|role)|apply\W*now|explore\W*(?:jobs|roles|opportunities)', re.I)


def career_links(page, base):
    """Absolute URLs of links whose href or text says careers / jobs / join us (same site or an ATS), ≤ 6, best first:
    a link into a known ATS, then a "search jobs / open positions" link or one to a careers. / jobs. host, then the rest
    in page order (EY's job search sat 7th behind six /careers/<topic> pages, 11-03). Links to an aggregator / social
    host (NOT_COMPANY: LinkedIn, jobright, Indeed, Glassdoor …) are dropped unless detect_ats recognises them."""
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', page or '', re.S | re.I):
        href, text = H.unescape(m.group(1)), re.sub(r'<[^>]+>', ' ', m.group(2))
        if re.search(r'career|/jobs?\b|join[- ]?(?:us|our)|work[- ]with[- ]us|opportunit', href + ' ' + text, re.I) \
                or SEARCH_LINK.search(text) or detect_ats(href):
            u = urllib.parse.urljoin(base, href)
            h = (urllib.parse.urlsplit(u).hostname or '').lower()
            if NOT_COMPANY.search(h) and not detect_ats(u):
                continue                                  # never fetch LinkedIn / jobright / Indeed … (Cook Medical, 11-03)
            if u.startswith('http') and u not in [x for x, _ in out]:
                out.append((u, text))
    bh = (urllib.parse.urlsplit(base or '').hostname or '').lower()
    def rank(x):
        u, text = x
        h = (urllib.parse.urlsplit(u).hostname or '').lower()
        if detect_ats(u):
            return 0
        if SEARCH_LINK.search(text) or SEARCH_LINK.search(u) or (h != bh and re.match(r'(?:careers?|jobs)\.', h)):
            return 1
        return 2
    return [u for u, _ in sorted(out, key=rank)][:6]


LONG_RUN = re.compile(r'[\w.-]{300,}')


def detect_ats(text):
    """[(system, ident)] in preference order, each once. ident = board token (greenhouse / lever / ashby), the
    (host, tenant, site) triple (workday) or the host / slug (others). A run of ≥ 300 letters / digits / _ . - (an
    inline base64 image, a minified blob) is blanked first: the '[\\w-]+\\.icims\\.com'-style patterns retry from every
    position inside such a run, which took minutes per page (JSA-171, 11-05); no host name or board token is that long."""
    out = []
    text = LONG_RUN.sub(' ', text or '')
    for system, rx in ATS_RX:
        for m in rx.finditer(text):
            g = m.group(1).rstrip('/.')
            if system == 'workday':
                t = RA_parse_tenant('https://' + g)
                if not t or re.search(r'internal|employee', t[2], re.I):     # employees-only site: not an outside application
                    continue
                ident = t
            elif system in ('greenhouse', 'lever', 'ashby'):
                g = urllib.parse.unquote(g)
                if g.lower() in BAD_TOKENS:
                    continue
                ident = g
            elif system == 'successfactors' and '?' in g:
                ident = g.split('/')[0].lower() + g[g.index('/'):]       # career?company=<id>: the id keeps its case
            else:
                ident = g.lower()
            if (system, ident) not in out:
                out.append((system, ident))
    return sorted(out, key=lambda x: [s for s, _ in ATS_RX].index(x[0]))


RMK_MARK = re.compile(r'(?:ssoCompanyId|j2w\.init|var j2w\b|jobs2web\.com|rmkcdn\.successfactors\.com)', re.I)


def rmk_site(url, page):
    """Pure (JSA-117). A page that is itself an SAP SuccessFactors Recruiting Marketing (RMK) career site — it carries
    at least two different markers, one of them 'ssoCompanyId' or 'j2w.init' (the others: 'var j2w', jobs2web.com,
    rmkcdn.successfactors.com) — → [('successfactors', <its host>)]; [] otherwise (also on any host site_hosts would
    not try: vendor hosts, which detect_ats already names, and vendor-label jobs2web hosts)."""
    h = (urllib.parse.urlsplit(url or '').hostname or '').lower()
    p = page or ''
    marks = {m.lower() for m in RMK_MARK.findall(p[:400000])}
    if not h or AS.site_hosts(h, '') != [h] or len(marks) < 2 or not marks & {'ssocompanyid', 'j2w.init'}:
        return []
    return [('successfactors', h)]


EF_MARK = re.compile(r'window\._EF_GROUP_ID\s*=|_EF_PRODUCT\b', re.I)
AVATURE_MARK = re.compile(r'avature', re.I)


def page_systems(url, page):
    """Pure (JSA-137). Systems a page shows by its own markup, on the company's domain (the URL names no vendor):
    rmk_site (SAP SuccessFactors RMK), an Eightfold career site ('window._EF_GROUP_ID = …' or '_EF_PRODUCT' together
    with the word 'eightfold' — apply.careers.microsoft.com), an Avature site (its URL path is /careers/SearchJobs or
    /careers/JobDetail, optionally after a locale such as /en_US, and the page names Avature). → [(system, ident)];
    the ident is ats_search.custom_host's form; nothing for a vendor host (detect_ats names those)."""
    out = rmk_site(url, page)
    u = urllib.parse.urlsplit(url or '')
    h, p = (u.hostname or '').lower(), (page or '')[:800000]
    if h and EF_MARK.search(p) and re.search(r'eightfold', p, re.I):
        i = AS.custom_host('eightfold', h)
        if i:
            out.append(('eightfold', i))
    m = re.match(r'(/[a-z]{2}[_-][a-z]{2})?/careers/(?:searchjobs|jobdetail)\b', u.path or '', re.I)
    if h and m and AVATURE_MARK.search(p):
        i = AS.custom_host('avature', h + (m.group(1) or '').lower())
        if i:
            out.append(('avature', i))
    return [x for i, x in enumerate(out) if x not in out[:i]]


def board_guesses(company):
    """Greenhouse / Lever / Ashby slugs from the whole name only ('acmerobotics', 'acme-robotics'); the first word alone
    ('acme') is left out for multi-word names — another company may own that board."""
    k = re.sub(r'[^a-z0-9 ]+', ' ', RB.company_key(company)).split()
    return [(ats, t) for t in dict.fromkeys(x for x in (''.join(k), '-'.join(k)) if len(x) >= 3) for ats in ('greenhouse', 'lever', 'ashby')]


def RA_parse_tenant(url):
    import wd_search
    return wd_search.parse_tenant(url)


def is_challenge(status, page):
    """A security check / bot wall → skip the company (never bypass)."""
    if status in (403, 429, 503) and CHALLENGE.search((page or '')[:20000]):
        return True
    if re.search(r'_Incapsula_Resource|Request unsuccessful\. Incapsula', (page or '')[:5000]):
        return True                                       # Imperva wall served with a 200 (airbus.com, 11-03)
    return bool(re.search(r'<title>\s*(just a moment|attention required|access denied|security check|captcha|'
                          r'pardon our interruption|are you a robot|human verification)', page or '', re.I))


ABBR = [(r'\bsr\b\.?', 'senior'), (r'\bjr\b\.?', 'junior'), (r'\bassoc\b\.?', 'associate'), (r'\bmgr\b\.?', 'manager'),
        (r'\beng\b\.?', 'engineer'), (r'\bmgmt\b\.?', 'management'), (r'\bquant\b', 'quantitative'), (r'\bml\b', 'machine learning'), (r'\bintl\b\.?', 'international')]


IN_CITY = re.compile(r'\s+in\s+[A-Z][\w .\']+,\s*[A-Z]{2}\.?\s*$')        # '… Data Scientist in Cupertino, CA.'
OPENINGS = re.compile(r'\((?:multiple|several|\d+)\s+(?:openings?|positions?|roles?)\)', re.I)


def norm_title(t):
    t = IN_CITY.sub(' ', OPENINGS.sub(' ', t or '').strip())
    t = CITY_TAIL.sub(' ', NOISE.sub(' ', t).strip())
    for rx, full in ABBR:
        t = re.sub(rx, full, t, flags=re.I)
    return re.sub(r'\s+', ' ', t).strip()


def city_of(location):
    """'New York, NY + 2' → 'new york'; 'Remote or Freeport, IL + 8' → 'freeport'; '' when none. A ';' ends the city
    too (Wellfound rows: 'New York; Recruiter recently active', 'Syracuse; Fairborn' → 'new york' / 'syracuse'; JSA-171)."""
    loc = re.sub(r'\+\s*\d+.*$', '', (location or '').lower())
    loc = re.sub(r'\bremote\b(?:\s+or\b)?', ' ', loc)
    first = re.split(r'[,;]', loc)[0].strip()
    return re.sub(r'\bcity\b', '', first).strip() if first else ''


CITY_FILLER = {'greater', 'area', 'metro', 'metropolitan', 'region', 'county', 'downtown'}


def match_posting(title, location, postings, floor=0.75):
    """postings = [(title, url, location)] → (score, title, url) or None. Equal best scores on different URLs: the
    one whose location names the row's city wins; none or several do → None (no guess). Postings with the same title and
    the same location text are clones of one opening (an employer posts one internship as 4 reqs, 11-03): the first is
    taken. The city counts as named when one of its words (≥ 4 letters, not greater / area / metro …) is in the location."""
    t = norm_title(title)
    # a campus-only posting ('… 2027 | Harvard', '… - MIT') is another opening: drop postings whose title adds a school
    school = lambda x: set(re.findall(r'\b(harvard|mit|stanford|princeton|yale|columbia|berkeley|cmu|carnegie|uchicago|chicago booth|'
                                      r'wharton|penn|cornell|caltech|waterloo|university|college)\b', (x or '').lower()))
    postings = [p for p in postings if not (school(p[0]) - school(title))]
    scored = sorted(((RB.similarity(t, norm_title(pt)), pt, pu, pl or '') for pt, pu, pl in postings), key=lambda x: -x[0])
    if not scored or scored[0][0] < floor:
        return None
    top = [s for s in scored if s[0] == scored[0][0]]
    c = city_of(location)
    cw = [w for w in re.findall(r'[a-z]+', c) if len(w) >= 4 and w not in CITY_FILLER] or ([c] if c else [])
    in_city = lambda pl: any(w in pl for w in cw)       # 'Greater Tampa Bay Area' ~ 'US - Tampa, FL (Lithia area)'
    if len({(s[1].lower(), s[3].lower()) for s in top}) == 1:   # one posting, or clones (same title + location, other req ids)
        pl = top[0][3].lower()
        wide = re.search(r'\d+\s+locations|remote|multiple|nationwide', pl) or \
            re.fullmatch(r'\s*(?:united states(?: of america)?|us|usa)\s*', pl)     # 'Phoenix, AZ, United States' is a city (JSA-112)
        if c and pl and not wide and not in_city(pl) \
                and not (c in (title or '').lower() and c in top[0][1].lower()):   # city in both titles (JSA-112)
            return None                                   # one posting, but in another city: a different opening
        return scored[0][:3]
    hit = [s for s in top if c and in_city(s[3].lower())]
    return hit[0][:3] if len({(s[1].lower(), s[3].lower()) for s in hit}) == 1 else None


def decide(row, systems, postings_of, floor=0.75):
    """Pure. systems = [(system, ident)] found for the company (searchable first is fine either way);
    postings_of(system, ident, title) → [(title, url, location)]. → dict(code, ats_url?, how?, why?, system)."""
    if row.get('ats_url'):
        return {'code': 'already', 'system': ''}
    title = (row.get('title') or '').strip()
    if not title:
        return {'code': 'no_title', 'why': 'row has no title to match', 'system': systems[0][0] if systems else ''}
    if not systems:
        return {'code': 'no_system', 'why': 'no careers system found on the company site', 'system': ''}
    searched = [s for s in systems if s[0] in SEARCHABLE or (s[0] in AS.SYSTEMS and AS.clean_ident(s[0], s[1]))]
    for system, ident in searched:
        hit = match_posting(title, row.get('location'), postings_of(system, ident, title), floor)
        if hit:
            name = '/'.join(ident[1:]) if system == 'workday' else ident
            return {'code': 'match', 'ats_url': hit[2], 'system': system,
                    'how': f'careers page → {system} "{name}" (title {hit[0]:.2f})'}
    if searched:
        return {'code': 'no_match', 'system': searched[0][0],
                'why': f'no matching posting on {", ".join(s for s, _ in searched)} for "{title}"'}
    return {'code': 'other_system', 'system': systems[0][0],
            'why': f'company uses {systems[0][0]} (no runner yet; match by hand)'}


# ---------- network ----------
UA = {**RB.UA, 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'en-US,en;q=0.9'}


def fetch(url, timeout=15):
    """→ (status, final_url, text ≤ 1.5 MB) ; (0, url, '') on a network error."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.status, r.geturl(), r.read(1_500_000).decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        try:
            body = e.read(200_000).decode('utf-8', 'replace')
        except Exception:
            body = ''
        return e.code, url, body
    except Exception:
        return curl_fetch(url, timeout)


def curl_fetch(url, timeout=15):
    """Plain curl (its own User-Agent) for a site that drops the browser-like request without an answer (pnc.com,
    mckinsey.com, 11-03) — a site that answers curl with a security check is still skipped by is_challenge."""
    import subprocess
    try:
        r = subprocess.run(['curl', '-sL', '--compressed', '--max-time', str(timeout), '--max-filesize', '3000000',
                            '-w', '\n@@%{http_code} %{url_effective}', url], capture_output=True, timeout=timeout + 5)
        body, _, tail = r.stdout.decode('utf-8', 'replace').rpartition('\n@@')
        code, _, final = tail.partition(' ')
        return (int(code), final.strip() or url, body[:1_500_000]) if code.isdigit() and int(code) else (0, url, '')
    except Exception:
        return 0, url, ''


NOT_COMPANY = re.compile(r'jobright|joinhandshake|linkedin|builtin|indeed|glassdoor|greenhouse\.io|lever\.co|ashbyhq|myworkday|'
                         r'icims|smartrecruiters|workable|github|simplify|zapply|vansh|ziprecruiter|wellfound|google\.|bit\.ly|'
                         r'instagram\.com|facebook\.com|twitter\.com|(?:^|\.)x\.com$|youtube\.com', re.I)   # social (JSA-137: Instagram's
                         # page config lists facebook.csod.com, read as a Cornerstone board for Louisiana Economic Development)
COMMON_PATHS = ['/careers', '/careers/jobs', '/about/careers', '/company/careers', '/about-us/careers', '/join-us', '/jobs']


def same_name(a, b):
    """Two company names are the same company: equal keys, or equal once spaces / punctuation are squashed out."""
    sq = lambda x: re.sub(r'[^a-z0-9]', '', RB.company_key(x))
    return bool(sq(a)) and (RB.company_key(a) == RB.company_key(b) or sq(a) == sq(b))


def pick_lookup(company, suggestions):
    """Clearbit-style [{name, domain}] → the domains whose name is this company (same_name), in order; [] when none."""
    return list(dict.fromkeys(x['domain'].lower() for x in suggestions or []
                              if isinstance(x, dict) and x.get('domain') and same_name(x.get('name', ''), company)))


ORGLIKE = re.compile(r'compan|corporation|business|firm|manufactur|bank|insur|retail|conglomerate|organi[sz]ation|universit|'
                     r'college|school|hospital|health|agency|developer|start-?up|provider|enterprise|brand|subsidiary|airline|'
                     r'group|fund|trading|consult|software|publisher|laborator|government|department|authority|nonprofit|'
                     r'non-profit|foundation|charity|chain|operator|carrier|maker|producer|studio|exchange|service', re.I)


def wikidata_pick(company, results):
    """wbsearchentities hits [{id, label, description, match: {text}}] → the ids (≤ 2) whose label or matched alias is
    this company (same_name, or the same distinctive words: 'Ingredion Incorporated' = 'Ingredion') and whose description
    says it is an organisation ('American multinational delivery services company'; a film or a person is skipped)."""
    sq = lambda x: ''.join(company_words(x))
    out = []
    for x in results or []:
        if not isinstance(x, dict) or not x.get('id') or not ORGLIKE.search(x.get('description') or ''):
            continue
        names = [x.get('label') or '', ((x.get('match') or {}).get('text') or '')] + list(x.get('aliases') or [])
        if any(n and (same_name(n, company) or (sq(n) and sq(n) == sq(company))) for n in names):
            out.append(x['id'])
    return out[:2]


def alias_domains(company, table):
    """Hand-kept company → domains (references/company_domains.json: brands on another domain — FedEx, Millennium →
    mlp.com — and parents whose careers site hires for the brand). Keys compare with same_name. → [] when none."""
    for k, v in (table or {}).items():
        if not k.startswith('_') and same_name(k, company):
            return [d.lower() for d in (v if isinstance(v, list) else [v])]
    return []


def looks_like_title(company):
    """A 'company' that is really a job title ('Intern, IT Analyst: Summer', 'Machine Learning Engineer Intern (…) - 2027
    Summer', 'Data Intern') — a scraping slip; looking it up only finds strangers' sites."""
    c = (company or '').lower()
    return bool(re.search(r'\b(?:intern(?:ship)?s?|summer\s+20\d\d|20\d\d\s+summer|co-?op)\b', c)) or \
        bool(re.search(r'\b(?:engineer|analyst|scientist|developer|manager|associate)\b', c) and re.search(r'\b(?:intern|summer|20\d\d)\b', c))


def paren_acronym(company):
    """'Washington Metropolitan Area Transit Authority (WMATA)' → 'wmata'; '' when the brackets hold no 2–8 letter acronym."""
    m = re.search(r'\(([A-Za-z]{2,8})\)', company or '')
    return m.group(1).lower() if m and m.group(1).isupper() else ''


def borrow_domains(company, jobs):
    """Hosts of other rows of the same company whose url / ats_url is the company's own site (no aggregator / ATS /
    social host) → registrable domains ('careers.acme.com' → 'acme.com'), in first-seen order."""
    out = []
    for j in jobs:
        if not same_name(j.get('company', ''), company):
            continue
        for u in (j.get('url'), j.get('ats_url')):
            h = (urllib.parse.urlsplit(u or '').hostname or '').lower()
            if h and not NOT_COMPANY.search(h):
                parts = h.split('.')
                d = '.'.join(parts[-3:]) if len(parts) >= 3 and parts[-2] in ('co', 'com', 'org', 'ac') else '.'.join(parts[-2:])
                if d not in out:
                    out.append(d)
    return out


def script_srcs(page, base, limit=4):
    """Same-site <script src> URLs (where JS-built careers pages keep their ATS address), ≤ limit."""
    host = '.'.join((urllib.parse.urlsplit(base).hostname or '').split('.')[-2:])
    out = []
    for m in re.finditer(r'<script\b[^>]*\bsrc=["\']([^"\']+)["\']', page or '', re.I):
        u = urllib.parse.urljoin(base, H.unescape(m.group(1)))
        if host and (urllib.parse.urlsplit(u).hostname or '').endswith(host) and u not in out:
            out.append(u)
    return out[:limit]


def sitemap_career_urls(xml, limit=4):
    """<loc> URLs of a sitemap that mention career / jobs, ≤ limit."""
    return [u for u in re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', xml or '') if re.search(r'career|/jobs?\b', u, re.I)][:limit]


# ---------- network ----------
_lookups, _llock, _trusted = {}, threading.Lock(), set()
ALIASES = os.path.join(HERE, '..', 'references', 'company_domains.json')


def aliases():
    try:
        return json.load(open(ALIASES))
    except Exception:
        return {}


def lookup_domains(company):
    """Public name → domain services: Clearbit's company autocomplete, then Wikidata's 'official website' (P856)."""
    with _llock:
        if company in _lookups:
            return _lookups[company]
    out = []
    q = urllib.parse.quote(re.sub(r'\(.*?\)', ' ', company).strip())
    try:
        with urllib.request.urlopen(urllib.request.Request(f'https://autocomplete.clearbit.com/v1/companies/suggest?query={q}',
                                                           headers=RB.UA), timeout=15) as r:
            out += [d for d in pick_lookup(company, json.loads(r.read())) if not foreign_host(d)]
    except Exception:
        pass
    if not out:
        try:
            wua = {'User-Agent': 'job-search-agent/1.0 (personal job search; one lookup per company)'}
            u = f'https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&limit=3&search={q}'
            with urllib.request.urlopen(urllib.request.Request(u, headers=wua), timeout=15) as r:
                ids = wikidata_pick(company, json.loads(r.read()).get('search', []))
            if ids:
                u = f'https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims&ids={"|".join(ids[:2])}'
                with urllib.request.urlopen(urllib.request.Request(u, headers=wua), timeout=15) as r:
                    ents = json.loads(r.read()).get('entities', {})
                for i in ids[:2]:
                    for c in ents.get(i, {}).get('claims', {}).get('P856', []):
                        v = (c.get('mainsnak', {}).get('datavalue') or {}).get('value', '')
                        h = (urllib.parse.urlsplit(v).hostname or '').lower()
                        if h and not foreign_host(h):
                            out.append(h[4:] if h.startswith('www.') else h)
                            _trusted.add((company, out[-1]))
        except Exception:
            pass
    out = list(dict.fromkeys(out))
    with _llock:
        _lookups[company] = out
    return out


def scan_site(site, page, final, found):
    """Careers links, common paths, careers./jobs. subdomains, the sitemap and same-site scripts → ATS hits added to found.
    Returns a security-check note or ''."""
    root = '.'.join(site.split('.')[-3:]) if site.split('.')[-2] in ('co', 'com', 'org', 'ac') else '.'.join(site.split('.')[-2:])
    done = lambda: any(s in SEARCHABLE for s, _ in found)
    pages = career_links(page, final) + [f'https://{site}{p}' for p in COMMON_PATHS] + [f'https://careers.{root}', f'https://jobs.{root}']
    seen, note, scripts = set(), '', script_srcs(page, final)
    found.extend(x for x in cname_systems(root) if x not in found)
    def look(u):
        nonlocal note
        seen.add(u)
        st, f, p = fetch(u)
        if is_challenge(st, p):
            note = note or f'security check on {urllib.parse.urlsplit(u).hostname}'; return None
        if st == 200:
            found.extend(x for x in detect_ats(f + ' ' + p) + page_systems(f, p) if x not in found)
            return f, p
        return None
    for u in pages:
        if done() or len(seen) >= 10:
            break
        if u in seen:
            continue
        got = look(u)
        if got and not done():
            scripts += [x for x in script_srcs(got[1], got[0]) if x not in scripts]
            for u2 in career_links(got[1], got[0])[:3]:        # one level deeper: a careers page's own "search jobs" link
                if u2 not in seen and not done():
                    look(u2)
    if not done():
        st, f, xml = fetch(f'https://{site}/sitemap.xml')
        for u in sitemap_career_urls(xml if st == 200 else ''):
            if u not in seen and not done():
                look(u)
    for u in scripts[:6]:                                       # JS-built pages: the ATS address sits in a bundle
        if done():
            break
        if u not in seen:
            look(u)
    return note


def cname_systems(root):
    """careers. / jobs. / career. of the company's domain → their DNS names (CNAME chain): a vendor-hosted careers site
    shows its vendor there ('careers.twosigma.com' → twosigma.avature.net, 'careers.ey.com' → ey.jobs2web.com,
    'careers.pnc.com' → pnc.phenompeople.com). → [(system, ident)] (detect_ats on those names)."""
    import socket
    names = []
    for sub in ('careers', 'jobs', 'career'):
        try:
            cn, al, _ = socket.gethostbyname_ex(f'{sub}.{root}')
            names += [cn] + al
        except Exception:
            pass
    return detect_ats(' '.join('https://' + n + '/' for n in names if not n.endswith(root)))


def probe_ats(company):
    """By-name probes of systems we only record (no runner yet): iCIMS careers-<slug>.icims.com, SmartRecruiters API
    (the posting's company name must match). → [(system, ident)]."""
    k = re.sub(r'[^a-z0-9]', '', RB.company_key(company))
    out = []
    if len(k) < 3:
        return out
    st, f, p = fetch(f'https://careers-{k}.icims.com/jobs/search?ss=1')
    if st == 200 and 'icims' in f and names_company(p, company):
        out.append(('icims', f'careers-{k}.icims.com'))
    st, f, p = fetch(f'https://api.smartrecruiters.com/v1/companies/{k}/postings?limit=1')
    try:
        d = json.loads(p) if st == 200 else {}
        if d.get('totalFound') and same_name(((d.get('content') or [{}])[0].get('company') or {}).get('name', ''), company):
            out.append(('smartrecruiters', k))
    except Exception:
        pass
    return out


def find_systems(company, borrowed=(), cache={}, lock=threading.Lock()):
    """Company → (systems, site, note, reason). note = a security check (company skipped); reason = why no site / no
    system was found (each candidate domain's outcome), for the report."""
    with lock:
        if company in cache:
            return cache[company]
    if looks_like_title(company):
        with lock:
            cache[company] = ([], '', '', 'company name is a job title (row data slip)')
        return cache[company]
    alias = alias_domains(company, aliases())
    acro = paren_acronym(company)
    cands = list(dict.fromkeys(alias + list(borrowed) + lookup_domains(company) + ([acro + '.com'] if acro else [])
                               + domain_candidates(company)))
    trusted = set(alias) | {d for c, d in _trusted if c == company}       # hand-kept / Wikidata: name check skipped
    ws = company_words(company)
    systems, site, note, why = [], '', '', []
    for dom in cands:
        st, final, page = fetch('https://www.' + dom)
        if st == 0:
            st, final, page = fetch('https://' + dom)
        if is_challenge(st, page):
            note = note or f'security check on {dom}'; why.append(f'{dom}: security check')
            if dom in trusted or reg_label(dom) in (''.join(ws), ws[0] if ws else '', acro):
                break                       # the company's own site is walled: skip it, never fall back to a weaker guess
            continue
        if st != 200:
            why.append(f'{dom}: {"no answer" if st == 0 else st}'); continue
        if dom in trusted:
            fh = (urllib.parse.urlsplit(final).hostname or '').lower()
            if is_parked(final, page) or (foreign_host(fh) and not foreign_host(dom)):
                why.append(f'{dom}: parked or foreign redirect'); continue
        elif not names_company(page, company, final):
            why.append(f'{dom}: not this company'); continue
        note, site, found = '', urllib.parse.urlsplit(final).hostname or dom, detect_ats(final + ' ' + page) + page_systems(final, page)
        note = scan_site(site, page, final, found)
        if not any(s in SEARCHABLE for s, _ in found):
            found += [x for x in probe_ats(company) if x not in found]
        systems = sorted(found, key=lambda x: (x[0] not in SEARCHABLE, [s for s, _ in ATS_RX].index(x[0])))
        why = [] if systems else [f'{site}: no careers system in the pages read']
        break
    if not site and not note:
        found = probe_ats(company)
        if found:
            systems, why = found, []
    with lock:
        cache[company] = (systems, site, note, '; '.join(why[:4]) if why else ('no candidate domain' if not cands else ''))
    return cache[company]


def render_systems(sites):
    """JS-built careers pages: open each site in a headless Chrome of its own (temporary profile — never the job
    Chrome on CDP 9222), follow up to 2 careers links, and scan the rendered HTML plus every network request URL (ATS
    iframes and API calls show up there). A security check → that site is skipped. {site: (systems, note)}.
    Needs Playwright (~/.job-agent-venv/bin/python)."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, channel='chrome')
        for site in sites:
            ctx = br.new_context(user_agent=RB.UA['User-Agent'])
            pg, reqs, found, note = ctx.new_page(), [], [], ''
            pg.on('request', lambda r: reqs.append(r.url))
            try:
                pg.goto(f'https://{site}', wait_until='domcontentloaded', timeout=30000); pg.wait_for_timeout(2500)
                html = pg.content()
                if is_challenge(200, html):
                    note = f'security check on {site}'
                else:
                    found += [x for x in detect_ats(pg.url + ' ' + html + ' ' + ' '.join(reqs)) + page_systems(pg.url, html) if x not in found]
                    for u in career_links(html, pg.url)[:2]:
                        if any(sy in SEARCHABLE for sy, _ in found):
                            break
                        reqs.clear()
                        pg.goto(u, wait_until='domcontentloaded', timeout=30000); pg.wait_for_timeout(3000)
                        h2 = pg.content()
                        if is_challenge(200, h2):
                            note = f'security check on {urllib.parse.urlsplit(u).hostname}'; break
                        found += [x for x in detect_ats(pg.url + ' ' + h2 + ' ' + ' '.join(reqs)) + page_systems(pg.url, h2) if x not in found]
            except Exception:
                pass
            ctx.close()
            out[site] = (sorted(found, key=lambda x: (x[0] not in SEARCHABLE, [sy for sy, _ in ATS_RX].index(x[0]))), note)
        br.close()
    return out


BIG_TECH = [(re.compile(r'^(amazon(\.com)?( web services)?|aws|amazon (development center|robotics|science|lab126)|lab126)\b', re.I), ('amazon', 'amazon')),
            (re.compile(r'^apple( inc\.?| computer)?$', re.I), ('apple', 'apple')),
            (re.compile(r'^google( llc| inc\.?)?$', re.I), ('google', 'google')),
            (re.compile(r'^tiktok\b.*\b(usds|u\.s\. data security)\b', re.I), ('tiktok', 'usds')),      # JSA-137: TikTok USDS JV
            (re.compile(r'^tiktok( inc\.?| shop| us| usa)?$', re.I), ('tiktok', 'tiktok')),
            (re.compile(r'^bytedance( inc\.?| ltd\.?)?$', re.I), ('bytedance', 'bytedance'))]


def big_tech(company):
    """Pure (tested). A company that hires through its own career site that ats_search reads (Amazon / AWS → amazon,
    Apple → apple, Google → google; JSA-133) → [(system, ident)], else []. Names are matched from the start, case-
    insensitive ("Amazon Web Services (AWS)" → amazon; "a Workday employer" / "Google DeepMind" → none)."""
    c = re.sub(r'\s+', ' ', str(company or '')).strip()
    return [h for rx, h in BIG_TECH if rx.match(c)][:1]


def inventory_hints(company):
    """ats-scrapers inventory (ats_inventory.py) → the hints confirmed live: a Greenhouse / Lever / Ashby board or a
    Workday site that lists postings now, a SmartRecruiters company whose postings name this company, or any other
    board ats_search reads whose live list has at least one posting (ats_search.live — iCIMS, Oracle, Taleo, UKG,
    SuccessFactors / Phenom career hosts, Eightfold, ADP, Paycom, …; JSA-119). Unconfirmed hints are dropped (JSA-069, 11-03)."""
    import ats_inventory
    out = []
    for system, ident in ats_inventory.lookup(company)[:8]:
        if system == 'workday':
            ok = bool(wd_search_text(ident, ''))
        elif system in SEARCHABLE:
            ok = bool(board_postings(system, ident))
        elif system == 'smartrecruiters':
            st, f, p = fetch(f'https://api.smartrecruiters.com/v1/companies/{ident}/postings?limit=1')
            try:
                d = json.loads(p) if st == 200 else {}
                ok = bool(d.get('totalFound')) and same_name(((d.get('content') or [{}])[0].get('company') or {}).get('name', ''), company)
            except Exception:
                ok = False
        elif system in AS.SYSTEMS and AS.clean_ident(system, ident):
            ok = AS.live(system, ident)                 # JSA-119: the live list (or an empty-keyword search) has postings
        else:
            ok = False                                  # no live check for it here
        if ok:
            out.append((system, ident))
    return out


_posts, _plock = {}, threading.Lock()


def wd_queries(title):
    """Pure (tested). Workday search texts to try in order: the normalised title, then its first three words when it is
    longer (a full title with extra words often finds nothing — U.S. Bank 11-03); ≤ 2, no duplicates."""
    t = norm_title(title)
    w = re.sub(r'[^\w&+ ]+', ' ', t).split()
    return list(dict.fromkeys(q for q in (t, ' '.join(w[:3]) if len(w) > 3 else '') if q))


def postings_of(system, ident, title):
    """[(title, url, location)] of a board (cached), or a Workday search for the title (shorter query if none)."""
    if system == 'workday':
        out = []
        for q in wd_queries(title):
            out = wd_search_text(ident, q)
            if out:
                break
        return out
    if system in AS.SYSTEMS:                             # JSA-112: ats_search.py (search systems: shorter query if none)
        for q in wd_queries(title) or ['']:
            out = [(p['title'], p['url'], p['location']) for p in AS.postings(system, ident, q)]
            if out:
                return out
        return []
    return board_postings(system, ident)


def wd_search_text(ident, q):
    """[(title, url, location)] from the Workday CXS search for q."""
    host, tenant, site = ident
    body = json.dumps({'appliedFacets': {}, 'limit': 20, 'offset': 0, 'searchText': q}).encode()
    req = urllib.request.Request(f'https://{host}/wday/cxs/{tenant}/{site}/jobs', data=body,
                                 headers={**RB.UA, 'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode('utf-8', 'replace'))
        base = f'https://{host}/{site}' if 'myworkdayjobs' in host else f'https://{host}/recruiting/{tenant}/{site}'
        return [(p['title'], base + p['externalPath'], p.get('locationsText', '')) for p in d.get('jobPostings', [])
                if p.get('externalPath')]
    except Exception:
        return []


def board_postings(system, ident):
    key = (system, ident)
    with _plock:
        if key in _posts:
            return _posts[key]
    out = []
    try:
        if system == 'greenhouse':
            d = json.loads(RB.get(f'https://boards-api.greenhouse.io/v1/boards/{ident}/jobs'))
            out = [(j['title'], f'https://job-boards.greenhouse.io/{ident}/jobs/{j["id"]}', (j.get('location') or {}).get('name', ''))
                   for j in d.get('jobs', [])]
        elif system == 'lever':
            d = json.loads(RB.get(f'https://api.lever.co/v0/postings/{ident}?mode=json'))
            out = [(j['text'], j['hostedUrl'], (j.get('categories') or {}).get('location', '')) for j in d] if isinstance(d, list) else []
        elif system == 'ashby':
            d = json.loads(RB.get(f'https://api.ashbyhq.com/posting-api/job-board/{ident}'))
            out = [(j['title'], j['jobUrl'], j.get('location', '')) for j in d.get('jobs', [])]
    except Exception:
        out = []
    with _plock:
        _posts[key] = out
    return out


def kind(url):
    """Aggregator rows this script resolves: jobright, Handshake, LinkedIn (JSA-055, 11-03 — a LinkedIn page is never
    fetched: only the row's company + title are used), Wellfound job pages (JSA-171 method A, 11-05 — never fetched
    either: Wellfound's Apply dialog gives no readable company link)."""
    u = (url or '').lower()
    return ('jobright' if 'jobright.ai/jobs/info/' in u else 'handshake' if 'joinhandshake.com' in u
            else 'linkedin' if re.search(r'linkedin\.com/(?:comm/)?jobs/view/', u)
            else 'wellfound' if re.search(r'(?:^|[/.])wellfound\.com/jobs/\d+', u) else None)


JOB_WORD = re.compile(r'\b(?:intern(?:ship)?s?|co-?op|summer|fall|spring|winter|20\d\d|program|engineer(?:ing)?|analyst|'
                      r'analytics|analysis|scientist|science|developer|manager|management|product|data|research|associate|'
                      r'student|graduate|college|junior|senior|business|finance|financial|marketing|sales|operations|strategy|'
                      r'technology|software|machine|learning|digital|investment|pricing|ai|ml|it|fellow(?:ship)?|'
                      r'apprentice(?:ship)?|trainee|remote|hybrid|on-?site|full-time|part-time|entry-level|new grad)\b', re.I)
ACRONYM_STOP = {'AI', 'ML', 'IT', 'PM', 'BI', 'US', 'USA', 'HR', 'UX', 'UI', 'QA', 'GTM', 'SWE', 'MBA', 'MS', 'BS', 'PHD',
                'IP', 'RF', 'ERP', 'CRM', 'GIS', 'FP', 'NLP', 'LLM', 'GEN', 'R&D', 'IOT', 'EV', 'HVAC', 'PRODUCT', 'DATA',
                'INTERN', 'INTERNSHIP', 'SUMMER', 'MARKETING', 'FINANCE', 'SALES', 'NEW', 'SR', 'JR'}
CAMEL_STOP = {'genai', 'devops', 'mlops', 'dataops', 'aiops', 'fintech', 'powerbi', 'saas', 'iot', 'ecommerce', 'javascript',
              'typescript', 'github', 'linkedin', 'youtube', 'chatgpt', 'openai'}     # words, not employers


def title_companies(title, company):
    """Pure (tested; JSA-171). Company names a Wellfound title states that differ from the row's label (Wellfound's
    label can be another company: 'Bounteous' on SAP's 'SAP iXp Intern …', 'Vh' on 'Georgia-Pacific Data Science
    Internship …'). In order, each once, ≤ 3: (a) the text after a final ' at ' ('… at McKinsey & Company'), ≤ 5 words,
    starting with a capital; (b) the part before the first ' - ' / ' – ' / ': ' / ' | ' when it has ≤ 4 words, no job word
    (JOB_WORD) and starts with a capital ('a Workday employer - AGI - …'); (c) the first word when it is CamelCase ('an employer',
    'PepsiCo'; not a word in CAMEL_STOP such as 'GenAI', 'DevOps'), capitalised words joined by a hyphen ('Georgia-Pacific') or all capitals of ≥ 3 letters not in
    ACRONYM_STOP whose next word is not a job word ('SAP iXp Intern' → 'SAP'; 'SAP Business Analyst Intern' → none).
    A name equal to the label (same_name) or that looks like a job title is dropped."""
    t = re.sub(r'\s+', ' ', (title or '')).strip()
    out = []
    m = re.search(r'\bat\s+([A-Z][\w&.\'’-]*(?:\s+[\w&.\'’-]+){0,4})\s*$', t)
    if m:
        out.append(m.group(1).strip(' .'))
    seg = re.split(r'\s+[-–]\s+|:\s+|\s+\|\s+', t, maxsplit=1)
    if len(seg) == 2:
        head = seg[0].strip()
        if head and head[0].isupper() and len(head.split()) <= 4 and not JOB_WORD.search(head):
            out.append(head)
    ws = t.split()
    if ws:
        w0 = ws[0].rstrip(',.:')
        nxt = ws[1] if len(ws) > 1 else ''
        if (re.fullmatch(r'[A-Z][a-z]+[A-Z][A-Za-z]+', w0) and w0.lower() not in CAMEL_STOP) \
                or (re.fullmatch(r'[A-Z][a-z]+(?:-[A-Z][a-z]+)+', w0) and not JOB_WORD.search(w0)):
            out.append(w0)
        elif re.fullmatch(r'[A-Z]{3,}', w0) and w0 not in ACRONYM_STOP and nxt and not JOB_WORD.search(nxt):
            out.append(w0)
    keep = []
    for n in out:
        if n and not same_name(n, company) and not looks_like_title(n) and not any(same_name(n, k) for k in keep):
            keep.append(n)
    return keep[:3]


def systems_back(systems):
    """[(system, ident)] read back from JSON: a Workday ident is a tuple again (it came back as a list)."""
    return [(sy, tuple(i) if isinstance(i, list) else i) for sy, i in systems]


class Checkpoint:
    """Resume file for a long --report run (JSA-129): one JSON line per finished company, rendered site and row, written
    as each one finishes. The first line holds the run's key (its arguments); a file with another key, a truncated last
    line or --fresh means those lines are not used. path None = no file (a run without --report)."""

    def __init__(self, path, key, fresh=False):
        self.path, self.key, self.lock = path, key, threading.Lock()
        self.comp, self.render, self.rows = {}, {}, {}
        lines = []
        if path and os.path.exists(path) and not fresh:
            for ln in open(path, encoding='utf-8'):
                try:
                    lines.append(json.loads(ln))
                except ValueError:                       # a line cut off when the run was killed
                    pass
        if lines and lines[0].get('key') == key:
            with open(path, 'w', encoding='utf-8') as f:     # rewrite without the cut-off line, so appends start clean
                f.writelines(json.dumps(d, ensure_ascii=False) + '\n' for d in lines)
            for d in lines[1:]:
                if d.get('t') == 'comp':
                    self.comp[d['c']] = (systems_back(d['s']), d['site'], d['note'], d.get('reason', ''))
                elif d.get('t') == 'render':
                    self.render[d['site']] = (systems_back(d['s']), d['note'])
                elif d.get('t') == 'row':
                    self.rows[d['id']] = d['r']
        elif path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(json.dumps({'key': key}) + '\n')

    def resumed(self):
        return len(self.comp) + len(self.render) + len(self.rows)

    def put(self, d):
        if self.path:
            with self.lock, open(self.path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(d, ensure_ascii=False) + '\n')

    def done(self):
        if self.path and os.path.exists(self.path):
            os.remove(self.path)


def run_key(a):
    """What makes two runs the same run: every argument except --fresh (and the report name, which names the file)."""
    return ' '.join(x for x in a if x != '--fresh')


def targets(jobs):
    """Rows still to resolve. A match dropped at review (--apply --drop → 'spot-check: …') is not tried again: the same
    wrong posting would come back (J12798, 11-04)."""
    return [j for j in jobs if kind(j.get('url')) and not j.get('ats_url') and j.get('elig') in ('可投', '待核实')
            and not (j.get('ats_unresolved') or '').startswith('spot-check:')]


def write(res):
    """res = {row id: decide() result}. Load right before saving (other writers share the store); a row that got an
    ats_url meanwhile is left alone; only ats_url / ats_resolved / ats_resolved_on / ats_system / ats_unresolved change."""
    import store, datetime
    today = datetime.date.today().isoformat()
    fresh = store.load('jobs')
    by = {j['id']: j for j in fresh}
    n = 0
    for i, r in res.items():
        j = by.get(i)
        if not j or j.get('ats_url'):
            continue
        if r.get('ats_url'):
            j.update(ats_url=r['ats_url'], ats_resolved=r['how'], ats_resolved_on=today, ats_system=r['system'])
            j.pop('ats_unresolved', None); n += 1
        elif r.get('why'):
            j['ats_unresolved'], j['ats_system'] = r['why'], r.get('system', '')
    store.save('jobs', fresh)
    print(f'written: {n} ats_url, {sum(1 for r in res.values() if not r.get("ats_url") and r.get("why"))} ats_unresolved')


def main(a):
    import store, collections
    if '--apply' in a:                                   # write a reviewed --report file (what was spot-checked is what lands)
        rep = json.load(open(a[a.index('--apply') + 1]))
        drop = set(a[a.index('--drop') + 1].split(',')) if '--drop' in a else set()
        write({i: (r if i not in drop else {**{k: v for k, v in r.items() if k not in ('ats_url', 'how')},
                                             'why': 'spot-check: not the same posting', 'code': 'rejected'})
               for i, r in rep['rows'].items()})
        return 0
    jobs = store.load('jobs')
    rows = targets(jobs)
    if '--company' in a:
        rows = [j for j in rows if j['company'] == a[a.index('--company') + 1]]
    if '--other' in a:                                   # rows an earlier run left as other_system on a system ats_search reads
        rows = [j for j in rows if j.get('ats_system') in AS.SYSTEMS]
    if '--systems' in a:                                 # only rows an earlier run left on these systems (JSA-112)
        rows = [j for j in rows if j.get('ats_system') in a[a.index('--systems') + 1].split(',')]
    if '--redo' in a:                                    # only the rows an earlier report ended with these codes (JSA-069)
        old = json.load(open(a[a.index('--redo') + 1]))['rows']
        codes = set(a[a.index('--codes') + 1].split(',')) if '--codes' in a else {'no_system', 'no_match'}
        rows = [j for j in rows if old.get(j['id'], {}).get('code') in codes]
    if '--ids' in a:                                     # only these rows (JSA-171: a comparison set)
        ids = set(a[a.index('--ids') + 1].split(','))
        rows = [j for j in rows if j['id'] in ids]
    companies = list(dict.fromkeys(j['company'] for j in rows))
    if '--limit' in a:
        companies = companies[:int(a[a.index('--limit') + 1])]
        rows = [j for j in rows if j['company'] in companies]
    # JSA-171: a Wellfound row's label can be another company — the names its title states are searched too
    alt = {j['id']: title_companies(j['title'], j['company']) for j in rows if kind(j.get('url')) == 'wellfound'}
    companies = list(dict.fromkeys(companies + [n for v in alt.values() for n in v]))
    known, tenants, reasons = RB.known_boards(jobs), RA.workday_tenants(jobs), {}
    ck = Checkpoint(a[a.index('--report') + 1] + '.part.jsonl' if '--report' in a else None, run_key(a), '--fresh' in a)
    if ck.resumed():
        print(f'resuming from {ck.path}: {len(ck.comp)} companies, {len(ck.render)} rendered sites, {len(ck.rows)} rows done')

    def per_company(c):
        if c in ck.comp:
            s0, site, note, reasons[c] = ck.comp[c]
            return c, s0, site, note
        c, s0, site, note = find_company(c)
        ck.put({'t': 'comp', 'c': c, 's': s0, 'site': site, 'note': note, 'reason': reasons.get(c, '')})
        return c, s0, site, note

    def find_company(c):
        if '--inventory-only' in a:                      # second pass: no site work, inventory hints only
            sysf, site, note, reason = [], '', '', 'inventory only'
        else:
            sysf, site, note, reason = find_systems(c, borrow_domains(c, jobs))
        reasons[c] = reason
        ck = RB.company_key(c)
        extra = [(ats, t) for ats, t in known.get(ck, [])] + [('workday', t) for t in tenants.get(ck, [])
                                                               if not re.search(r'internal|employee', t[2], re.I)]
        extra += [h for h in big_tech(c) if h not in extra]      # Amazon / Apple / Google career sites (JSA-133)
        if '--no-inventory' not in a:
            inv = [h for h in inventory_hints(c) if h not in sysf and h not in extra]
            extra += inv
            if inv:
                reasons[c] = (reasons.get(c) or '') + f'; inventory: {", ".join(h[0] for h in inv)}'
        extra += [g for g in board_guesses(c) if g not in extra and postings_of(g[0], g[1], '')]   # guessed boards that exist
        return c, AS.with_site([x for x in sysf if x not in extra] + extra if not note else extra, site), site, note
    t0 = time.time()
    with ThreadPoolExecutor(12) as ex:
        comp = {c: (s, site, note) for c, s, site, note in ex.map(per_company, companies)}
    if '--render' in a or '--render-all' in a:           # sites found but no searchable system read (A/B only, or all)
        ab = {j['company'] for j in rows if j.get('tier') in ('A', 'B') or '--render-all' in a}
        todo = [c for c in companies if c in ab and comp[c][1] and not comp[c][2] and not any(x[0] in SEARCHABLE for x in comp[c][0])]
        print(f'rendering {len(todo)} company sites in headless Chrome …')
        sites = list(dict.fromkeys(comp[c][1] for c in todo))
        rendered = {x: ck.render[x] for x in sites if x in ck.render}
        new = [x for x in sites if x not in rendered]
        for k in range(0, len(new), 10):                 # ten at a time, so a restart loses at most ten
            got = render_systems(new[k:k + 10])
            for x in new[k:k + 10]:
                rendered[x] = got.get(x, ([], ''))
                ck.put({'t': 'render', 'site': x, 's': rendered[x][0], 'note': rendered[x][1]})
        for c in todo:
            s0, site, _ = comp[c]
            sysr, note = rendered.get(site, ([], ''))
            sysr = AS.with_site(sysr, site)
            comp[c] = (sysr + [x for x in s0 if x not in sysr], site, note)
            reasons[c] = reasons.get(c, '') + f'; rendered: {", ".join(x[0] for x in sysr) or "nothing"}'

    def one(j):
        if j['id'] in ck.rows:
            return j['id'], ck.rows[j['id']]
        i, r = decide_row(j)
        ck.put({'t': 'row', 'id': i, 'r': r})
        return i, r

    def decide_row(j):
        s, site, note = comp[j['company']]
        r = decide(j, s, postings_of)
        for n in alt.get(j['id'], []) if r.get('code') != 'match' else []:
            s2, site2, note2 = comp[n]
            r2 = decide(j, s2, postings_of)
            if r2.get('code') == 'match':                # the company the title names has the posting (label was wrong)
                r2['how'] = f'title names "{n}": ' + r2['how']
                s, site, note, r = s2, site2, note2, r2
                break
        note = note or (AS.note_for(s) if r.get('code') == 'no_match' else '')
        if note and r.get('code') != 'match':
            r = {'code': 'security_check', 'why': note + ' (skipped, not bypassed)', 'system': r.get('system', '')}
        r.update(site=site, company=j['company'], title=j['title'], location=j.get('location', ''), agg=kind(j['url']),
                 tier=j.get('tier'), elig=j.get('elig'))
        if alt.get(j['id']):
            r['title_companies'] = alt[j['id']]
        return j['id'], r
    with ThreadPoolExecutor(8) as ex:
        res = dict(ex.map(one, rows))
    C = collections.Counter
    print(f'{len(rows)} rows · {len(companies)} companies · {time.time() - t0:.0f} s')
    print('by aggregator:', json.dumps(C(f"{r['agg']}:{r['code']}" for r in res.values()), indent=1))
    print('ats_url by system:', dict(C(r['system'] for r in res.values() if r.get('ats_url'))))
    print('A/B resolved:', dict(C(r['agg'] for r in res.values() if r.get('ats_url') and r['tier'] in ('A', 'B'))))
    print('companies by system:', dict(C((comp[c][0][0][0] if comp[c][0] else ('security check' if comp[c][2] else
                                         ('no site' if not comp[c][1] else 'none'))) for c in companies)))
    if '--report' in a:
        rep = {'rows': res, 'companies': {c: {'systems': [[s, i if isinstance(i, str) else '/'.join(i)] for s, i in v[0]],
                                              'site': v[1], 'note': v[2], 'reason': reasons.get(c, '')}
                          for c, v in comp.items()}}
        json.dump(rep, open(a[a.index('--report') + 1], 'w'), ensure_ascii=False, indent=1)
        ck.done()
    if '--write' in a:
        write(res)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
