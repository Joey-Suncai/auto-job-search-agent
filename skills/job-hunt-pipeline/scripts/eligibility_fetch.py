#!/usr/bin/env python3
"""Eligibility gate, step 1: fetch the full job description of every dashboard role (no browser, no LLM).

Reads the dashboard jobs dataset, works out which job board each posting lives on from its URL, and downloads the
posting through that board's public endpoint. Writes one JSON line per row to jds.jsonl:
  {"id", "key", "level", "status": "ok"|"closed"|"unreadable", "title", "text", "loc", "why"}
`key` identifies the posting itself (same posting listed twice -> same key), used for dedupe.

Supported: Greenhouse (US + EU, incl. gh_jid company pages), Lever (US + EU), Ashby, Workday (cxs JSON),
iCIMS (?in_iframe=1 page), BambooHR (careers/<id>/detail JSON), ADP Workforce Now (public job-requisitions JSON),
ClearCompany (careers-api JSON),
SmartRecruiters, Built In / Jobright / any page with schema.org JobPosting JSON-LD, zapply.jobs redirects.
Not readable without a login: LinkedIn, Handshake -> "unreadable" (待核实, checked before applying).

Needs network access to the job-board hosts (cloud environment: Custom network access, see SKILL.md).
Usage: python3 eligibility_fetch.py jobs.json jds.jsonl [--only-new ids.txt] [--workers 16] [--retry earlier_jds.jsonl]
"""
import concurrent.futures as cf, html, http.client, json, os, re, sys, threading, time, urllib.error, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
READER_VERSION = 8  # bump when a new site reader is added: rows unreadable under an older version get re-checked
_lock = threading.Lock()
try:  # python.org builds on macOS ship without CA certs; use certifi when it is installed
    import ssl, certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _CTX = None
_cache = {}
_slow = {"builtin.com": threading.Semaphore(2),   # Built In rate-limits (429) above ~2 parallel requests
         "wellfound.com": threading.Semaphore(1)}  # Wellfound answers 429 after ~250 pages at 16 parallel (2026-11-03)
_gap = {"wellfound.com": 1.2}  # seconds between requests to that host (default 0.4)


def get(url, accept="application/json", tries=4, data=None, headers=None):
    """-> (status, text, final_url); status 0 = network error"""
    host = urllib.parse.urlparse(url).netloc.replace("www.", "")
    sem = _slow.get(host)
    if sem:
        with sem:
            time.sleep(_gap.get(host, 0.4))
            return _get(url, accept, tries, data, headers)
    return _get(url, accept, tries, data, headers)


def _get(url, accept, tries, data, headers=None):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, "Accept": accept, **(headers or {})}, data=data)
            with urllib.request.urlopen(req, timeout=25, context=_CTX) as r:
                try:
                    body = r.read()
                except http.client.IncompleteRead as e:  # some sites (TikTok) cut the stream short; the job text is already in
                    body = e.partial
                return r.status, body.decode("utf-8", "replace"), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and a < tries - 1:
                time.sleep(4 * (a + 1)); continue
            return e.code, "", url
        except Exception as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                sys.exit("SSL certificate error: run  open '/Applications/Python 3*/Install Certificates.command'  (or: pip3 install certifi) and retry")
            if a < tries - 1:
                time.sleep(1.5); continue
            return 0, "", url
    return 0, "", url


def cached(key, fn):
    with _lock:
        if key in _cache:
            return _cache[key]
    v = fn()
    with _lock:
        _cache[key] = v
    return v


def strip(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h or "", flags=re.S | re.I)
    h = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(h)))
    return re.sub(r"\s+", " ", h).strip()


# ---------------------------------------------------------------- board loaders
def greenhouse(boards, jid, strict):
    n404 = tries = 0
    for b in boards:
        for host in ("boards-api.greenhouse.io", "boards-api.eu.greenhouse.io"):
            tries += 1
            s, t, _ = get(f"https://{host}/v1/boards/{b}/jobs/{jid}")
            if s == 200:
                j = json.loads(t)
                return dict(status="ok", key=f"gh:{jid}", title=j.get("title"), text=strip(j.get("content")),
                            loc=(j.get("location") or {}).get("name", ""))
            if s == 404:
                n404 += 1
    if strict and n404 == tries:
        return dict(status="closed", key=f"gh:{jid}", why="Greenhouse 404 (posting removed)")
    return dict(status="unreadable", key=f"gh:{jid}", why="Greenhouse board not found")


def guess_boards(host):
    h = re.sub(r"^(www|careers|jobs|app)\.", "", host).split(".")[0]
    c = [h, h.replace("-", ""), re.sub(r"careers?$", "", h), re.sub(r"^(with|join|careers?|weare)", "", h)]
    return list(dict.fromkeys(x for x in c if x))


def lever(org, jid, eu):
    host = "api.eu.lever.co" if eu else "api.lever.co"
    s, t, _ = cached(f"lv:{host}:{org}", lambda: get(f"https://{host}/v0/postings/{org}?mode=json"))
    if s != 200:
        return dict(status="unreadable", key=f"lv:{jid}", why=f"Lever board {s}")
    j = next((x for x in json.loads(t) if x.get("id") == jid), None)
    if not j:
        return dict(status="closed", key=f"lv:{jid}", why="no longer on the Lever board")
    cat = j.get("categories") or {}
    text = " ".join([j.get("descriptionPlain") or ""] + [l.get("text", "") + ": " + strip(l.get("content")) for l in j.get("lists") or []]
                    + [j.get("additionalPlain") or ""])
    return dict(status="ok", key=f"lv:{jid}", title=j.get("text"), text=text,
                loc="; ".join(x for x in [cat.get("location")] + (cat.get("allLocations") or []) if x))


def ashby(org, jid):
    s, t, _ = cached(f"ab:{org}", lambda: get(f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(org)}?includeCompensation=true"))
    if s != 200:
        return dict(status="unreadable", key=f"ab:{jid}", why=f"Ashby board {s}")
    j = next((x for x in json.loads(t).get("jobs", []) if x.get("id") == jid), None)
    if not j:
        return dict(status="closed", key=f"ab:{jid}", why="no longer on the Ashby board")
    locs = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations") or []]
    pa = ((j.get("address") or {}).get("postalAddress") or {})
    loc = "; ".join(x for x in locs + [", ".join(x for x in [pa.get("addressRegion"), pa.get("addressCountry")] if x)] if x)
    return dict(status="ok", key=f"ab:{jid}", title=j.get("title"), text=j.get("descriptionPlain") or strip(j.get("descriptionHtml")),
                loc=loc + (" (remote)" if j.get("isRemote") else ""))


def wd_page_gone(html):
    """Pure (tested). A Workday job page (the public HTML shell) → True when it names no posting: the og:title meta is
    there but empty. A live posting's shell carries its title there (JSA-284, checked live 2026-11-10: 38 of 38)."""
    m = re.search(r'<meta[^>]*property="og:title"[^>]*>', html or "", flags=re.I)
    return bool(m) and not re.search(r'content="[^"]+"', m.group(0))


def workday(host, tenant, site, slug, page=None):
    key = f"wd:{tenant.lower()}:{slug.lower()}"
    s, t, _ = get(f"https://{host}/wday/cxs/{tenant}/{site}/job/x/{slug}")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"Workday {s} (posting removed)")
    if s == 403 and page:   # JSA-284: Workday refuses the JSON of a posting it took down; its page then has no title
        ps, pt, _ = get(page, accept="text/html", tries=2)
        if ps in (404, 410) or (ps == 200 and wd_page_gone(pt)):
            return dict(status="closed", key=key, why=f"Workday {s} and the job page names no posting (taken down)")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"Workday {s}")
    j = json.loads(t).get("jobPostingInfo") or {}
    if j.get("canApply") is False or j.get("postingAvailable") is False:
        return dict(status="closed", key=key, why="Workday: no longer accepting applications")
    loc = "; ".join(x for x in [j.get("location")] + (j.get("additionalLocations") or []) + [(j.get("country") or {}).get("descriptor")] if x)
    return dict(status="ok", key=key, title=j.get("title"), text=strip(j.get("jobDescription")), loc=loc)


def smartrecruiters(co, pid):
    key = f"sr:{pid}"
    s, t, _ = get(f"https://api.smartrecruiters.com/v1/companies/{co}/postings/{pid}")
    if s == 404:
        return dict(status="closed", key=key, why="SmartRecruiters 404")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"SmartRecruiters {s}")
    j = json.loads(t)
    if j.get("active") is False:
        return dict(status="closed", key=key, why="SmartRecruiters: inactive")
    sec = (j.get("jobAd") or {}).get("sections") or {}
    text = " ".join(strip((sec.get(k) or {}).get("text")) for k in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"))
    l = j.get("location") or {}
    return dict(status="ok", key=key, title=j.get("name"), text=text,
                loc=", ".join(x for x in [l.get("city"), l.get("region"), l.get("country")] if x) + (" (remote)" if l.get("remote") else ""))


def js_string_after(page, marker):
    """Pure (tested). The double-quoted JavaScript string right after `marker` in `page`, still escaped (backslash +
    next character kept as a pair), without its quotes; None when the marker is missing or the string never ends. The
    marker may end with the opening quote ('JSON.parse("') or stop just before it ('x = ')."""
    t = str(page or '')
    i = t.find(marker)
    if i < 0:
        return None
    i += len(marker); out = []
    if not marker.endswith('"') and t[i:i + 1] == '"':   # marker 'x = ' before '"…"': step over the opening quote
        i += 1
    while i < len(t):
        c = t[i]
        if c == '\\':
            if i + 1 >= len(t):
                return None
            out.append(t[i:i + 2]); i += 2; continue
        if c == '"':
            return ''.join(out)
        out.append(c); i += 1
    return None


def apple_parse(page):
    """Pure (tested). A jobs.apple.com details page → {'title', 'text', 'loc'} from the page's `JSON.parse("…")` loader data
    (loaderData.jobDetails.jobsData: localizations en_US (else en_UK, else any) → posting with postingTitle, jobSummary,
    description, minimumQualifications, preferredQualifications; text = those four joined, HTML removed; loc = the
    jobsData.locations names with their countryName, "; "-joined). {'closed': True} when the loader data parses but holds
    no `jobDetails` (Apple's "Page not found … no longer available" page; that sentence alone is not enough — every page
    carries it in its translations). None when nothing can be read (after ats-scrapers apple.py)."""
    t = str(page or '')
    enc = js_string_after(t, 'JSON.parse("')
    if enc is None:
        return None
    try:
        d = json.loads(json.loads('"' + enc + '"'))
    except ValueError:
        return None
    ld = (d.get('loaderData') or {}) if isinstance(d, dict) else {}
    if isinstance(ld, dict) and 'root' in ld and not ld.get('jobDetails'):
        return {'closed': True}
    jd = ((ld.get('jobDetails') or {}).get('jobsData') or {}) if isinstance(ld, dict) else {}
    locz = jd.get('localizations') or {}
    post = next((v.get('posting') for k in ('en_US', 'en_UK') for v in [locz.get(k)] if isinstance(v, dict) and v.get('posting')),
                None) or next((v.get('posting') for v in locz.values() if isinstance(v, dict) and v.get('posting')), None) or {}
    parts = [post.get(k) or '' for k in ('jobSummary', 'description', 'minimumQualifications', 'preferredQualifications')]
    text = strip(' '.join(p for p in parts if p))
    if not text:
        return None
    loc = '; '.join(', '.join(x for x in (l.get('name'), l.get('countryName')) if x) for l in jd.get('locations') or [] if isinstance(l, dict))
    return {'title': post.get('postingTitle') or '', 'text': text, 'loc': loc}


def apple_page(url, key):
    s, t, final = get(url, accept="text/html")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"page {s}")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"page {s}")
    x = apple_parse(t)
    if not x:
        return dict(status="unreadable", key=key, why="no Apple posting data on the page")
    if x.get('closed'):
        return dict(status="closed", key=key, why="Apple: the role is no longer available")
    return dict(status="ok", key=key, **x)


def google_parse(page):
    """Pure (tested). A Google Careers posting page → {'title', 'text', 'loc'} or None. title = og:title; the JD = the title, then
    the lines from the first "Minimum qualifications" or "Minimum qualifications:" (else "About the job[:]") up to (not including) the first line that
    starts with "Information collected and processed" or "Google is proud to be an equal opportunity" (else the end),
    script / style removed, tags → line breaks, entities decoded, blank lines dropped, joined with spaces; loc = the
    line after the first line exactly "place" (Material icon name) before the JD, else ''. None when no JD line is found."""
    t = str(page or '')
    m = re.search(r'<meta property="og:title" content="([^"]*)"', t)
    title = html.unescape(m.group(1)).strip() if m else ''
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    lines = [html.unescape(x).strip() for x in re.sub(r'<[^>]+>', '\n', body).split('\n')]
    lines = [x for x in lines if x]
    start = next((i for i, x in enumerate(lines) if re.fullmatch(r'Minimum qualifications:?', x)), None)   # "Minimum qualifications:" (colon) on the live page
    if start is None:
        start = next((i for i, x in enumerate(lines) if re.fullmatch(r'About the job:?', x)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if re.match(r'(Information collected and processed|Google is proud to be an equal opportunity)', lines[i])), len(lines))
    text = re.sub(r'\s+', ' ', ' '.join(([title] if title else []) + lines[start:end])).strip()   # the title says "PhD" / "BS/MS" too
    p = next((i for i in range(start) if lines[i] == 'place'), None)
    loc = lines[p + 1] if p is not None and p + 1 < start else ''
    return {'title': title, 'text': text, 'loc': loc} if text else None


def google_page(url, key):
    s, t, final = get(url.split('?')[0] + '?hl=en_US', accept="text/html")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"page {s}")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"page {s}")
    x = google_parse(t)
    if not x:
        return dict(status="unreadable", key=key, why="no job description on the Google Careers page")
    return dict(status="ok", key=key, **x)


def usajobs_jd(d):
    """Pure (tested). One USAJOBS API MatchedObjectDescriptor → {'title', 'text', 'loc'} or None (no title). text =
    "Who may apply: <UserArea.Details.WhoMayApply.Name>." (when present), then QualificationSummary, UserArea.Details
    JobSummary, MajorDuties (a list, joined), Requirements, Education, and "Security clearance: <SecurityClearance>."
    (when present) — HTML removed, whitespace collapsed; loc = PositionLocationDisplay (else the PositionLocation
    names "; "-joined). No space is left before . , ; : ! ? once tags are removed."""
    if not isinstance(d, dict) or not (d.get('PositionTitle') or '').strip():
        return None
    det = ((d.get('UserArea') or {}).get('Details') or {}) if isinstance(d.get('UserArea'), dict) else {}
    who = (det.get('WhoMayApply') or {}).get('Name') if isinstance(det.get('WhoMayApply'), dict) else ''
    duties = det.get('MajorDuties')
    parts = ([f"Who may apply: {who}."] if who else []) + [d.get('QualificationSummary') or '', det.get('JobSummary') or '',
             ' '.join(duties) if isinstance(duties, list) else (duties or ''), det.get('Requirements') or '', det.get('Education') or '']
    if det.get('SecurityClearance'):
        parts.append(f"Security clearance: {det['SecurityClearance']}.")
    loc = d.get('PositionLocationDisplay') or '; '.join(l.get('LocationName') for l in d.get('PositionLocation') or []
                                                        if isinstance(l, dict) and l.get('LocationName'))
    text = re.sub(r'\s+([.,;:!?])', r'\1', strip(' '.join(p for p in parts if p)))   # "<b>data</b>." → "data." not "data ."
    return {'title': d['PositionTitle'].strip(), 'text': text, 'loc': loc or ''}


def usajobs(num, key):
    """The posting through the official API (ControlNumber); needs the free key (USAJOBS_API_KEY / Keychain jobagent-usajobs)."""
    sys.path.insert(0, HERE)
    import usajobs_search as U
    k, ua = U.creds()
    if not k:
        return dict(status="unreadable", key=key, why="no USAJOBS API key (USAJOBS_API_KEY / Keychain jobagent-usajobs)")
    s, t, _ = get(f"https://data.usajobs.gov/api/Search?ControlNumber={num}", headers={'Authorization-Key': k, 'User-Agent': ua, 'Host': 'data.usajobs.gov'})
    if s != 200:
        return dict(status="unreadable", key=key, why=f"USAJOBS API {s}")
    try:
        its = (json.loads(t).get('SearchResult') or {}).get('SearchResultItems') or []
    except ValueError:
        its = []
    if not its:
        return dict(status="closed", key=key, why="USAJOBS: the announcement is no longer listed")
    x = usajobs_jd(its[0].get('MatchedObjectDescriptor'))
    return dict(status="ok", key=key, **x) if x else dict(status="unreadable", key=key, why="USAJOBS: no posting data")


def wellfound_parse(page):
    """Pure (tested). A Wellfound job page → {'title', 'text', 'loc'} or None. The JD is the block between "About the job" and
    "About the company" (or the page end); the title is the <title> text before " at <Company> • …"; loc = the line after
    "Job Location". Wellfound's own "Visa Sponsorship" flag is per company and is not part of the JD text."""
    t = str(page or '')
    m = re.search(r'<title[^>]*>(.*?)</title>', t, flags=re.S | re.I)
    title = html.unescape(m.group(1)).strip() if m else ''
    m = re.match(r'(.*) at [^•|]+? [•|]', title, flags=re.S)   # the LAST " at <Company> •" (a job title may contain " at ")
    title = (m.group(1) if m else title).split(' | Wellfound')[0].strip()
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    lines = [html.unescape(x).strip() for x in re.sub(r'<[^>]+>', '\n', body).split('\n')]
    lines = [x for x in lines if x]
    if 'About the job' not in lines:
        return None
    i = lines.index('About the job')
    j = next((k for k in range(i + 1, len(lines)) if lines[k] == 'About the company'), len(lines))
    jd = lines[i + 1:j]
    if jd and jd[-1] == 'Apply Now':
        jd = jd[:-1]
    text = re.sub(r'\s+', ' ', ' '.join(jd)).strip()
    if not text:
        return None
    loc = lines[lines.index('Job Location') + 1] if 'Job Location' in lines[:i] and lines.index('Job Location') + 1 < i else ''
    return {'title': title, 'text': text, 'loc': loc}


def wellfound_page(url, key):
    s, t, final = get(url, accept="text/html")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"page {s}")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"page {s}")
    x = wellfound_parse(t)
    if not x:
        return dict(status="unreadable", key=key, why="no 'About the job' block on the Wellfound page")
    return dict(status="ok", key=key, **x)


def jsonld_page(url, key):
    s, t, final = get(url, accept="text/html")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"page {s}")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"page {s}")
    for blob in re.findall(r'<script[^>]+application/ld(?:\+|&#x2B;|&#43;|&plus;)json[^>]*>(.*?)</script>', t, flags=re.S | re.I):
        try:
            d = json.loads(blob.strip())
        except Exception:
            continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if isinstance(x, dict) and x.get("@type") in ("JobPosting", ["JobPosting"]):
                locs = x.get("jobLocation") or []
                locs = locs if isinstance(locs, list) else [locs]
                loc = "; ".join(", ".join(v for v in [(l.get("address") or {}).get(k) for k in ("addressLocality", "addressRegion", "addressCountry")] if isinstance(v, str))
                                for l in locs if isinstance(l, dict))
                if x.get("jobLocationType") == "TELECOMMUTE":
                    loc += " (remote)"
                if x.get("validThrough") and x["validThrough"][:10] < time.strftime("%Y-%m-%d"):
                    return dict(status="closed", key=key, why="JobPosting validThrough passed")
                return dict(status="ok", key=key, title=x.get("title"), text=strip(x.get("description")), loc=loc)
    # Next.js pages (e.g. Jobright) carry the posting in __NEXT_DATA__
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, flags=re.S)
    if m:
        try:
            nd = json.loads(m.group(1))
            strs = []
            def walk(o):
                if isinstance(o, dict):
                    for v in o.values(): walk(v)
                elif isinstance(o, list):
                    for v in o: walk(v)
                elif isinstance(o, str) and len(o) > 40:
                    strs.append(o)
            walk(nd.get("props", {}))
            text = strip(" ".join(strs))
            if len(text) > 400:
                title = re.search(r"<title>(.*?)</title>", t, flags=re.S)
                return dict(status="ok", key=key, title=strip(title.group(1)) if title else "", text=text[:60000], loc="")
        except Exception:
            pass
    return dict(status="unreadable", key=key, why="no JobPosting data on the page")


def tiktok_page(url, key):
    """lifeattiktok.com / joinbytedance.com job pages are server-rendered: Location ... Responsibilities ... Apply to this job"""
    s, t, final = get(url, accept="text/html")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"page {s}")
    if s != 200 or not t:
        return dict(status="unreadable", key=key, why=f"page {s}")
    txt = strip(re.sub(r"<[^>]+>", " | ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S)))
    txt = re.sub(r"(\s*\|\s*)+", " | ", txt)
    title = re.search(r"<title>(.*?)</title>", t, flags=re.S)
    a = txt.find("| Responsibilities |")
    if a < 0:
        return dict(status="closed" if re.search(r"no longer|not found|expired", txt[:3000], re.I) else "unreadable", key=key, why="no job text on the page")
    b = txt.find("Apply to this job", a)
    loc = re.search(r"\| Location \| : \| (.*?) \| (?:Employment Type|Job Code)", txt)
    return dict(status="ok", key=key, title=strip(title.group(1)) if title else "", text=txt[a:b if b > a else None].replace(" | ", " "),
                loc=loc.group(1).replace(" | ", ", ") if loc else "")


def bytedance(pid):
    key = f"bd:{pid}"
    s, t, _ = get(f"https://jobs.bytedance.com/api/v1/job/posts/{pid}?portal_type=2&with_recommend=false",
                  headers={"portal-channel": "official", "portal-platform": "pc", "website-path": "en"})
    if s == 404:
        return dict(status="closed", key=key, why="ByteDance 404")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"ByteDance API {s}")
    d = json.loads(t)
    j = (d.get("data") or {}).get("job_post_detail") or {}
    if d.get("code") not in (0, None) or not j:
        return dict(status="closed", key=key, why=f"ByteDance: {d.get('message') or 'posting not found'}")
    if j.get("channel_online_status") not in (None, 1):
        return dict(status="closed", key=key, why="ByteDance: posting offline")
    loc = "; ".join(c.get("en_name") or "" for c in (j.get("city_list") or [j.get("city_info") or {}]) if c)
    return dict(status="ok", key=key, title=j.get("title"), text=(j.get("description") or "") + " " + (j.get("requirement") or ""), loc=loc)


def amazon(jid, url):
    key = f"az:{jid}"
    s, t, _ = get(url, accept="text/html")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"Amazon {s}")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"Amazon {s}")
    title = re.search(r'<h1 class="title"[^>]*>(.*?)</h1>', t, flags=re.S)
    a = t.find("<h2>Description</h2>")
    if a < 0:
        return dict(status="closed" if re.search(r"no longer available|job is not available", t, re.I) else "unreadable", key=key, why="no description on the Amazon page")
    b = t.find("Job details", a)
    loc = re.search(r'location-icon.*?<ul class="association-content">(.*?)</ul>', t, flags=re.S)
    return dict(status="ok", key=key, title=strip(title.group(1)) if title else "", text=strip(t[a:b if b > a else a + 20000]),
                loc="; ".join(strip(x) for x in re.findall(r"<li>(.*?)</li>", loc.group(1), flags=re.S)) if loc else "")


def oracle(host, site, rid):
    key = f"or:{host.split('.')[0]}:{rid}"
    q = urllib.parse.quote(f'ById;Id="{rid}",siteNumber={site}', safe=';=",')
    s, t, _ = get(f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder={q}")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"Oracle {s}")
    items = json.loads(t).get("items") or []
    if not items:
        return dict(status="closed", key=key, why="Oracle: requisition not found")
    j = items[0]
    end = (j.get("ExternalPostedEndDate") or "")[:10]
    if end and end < time.strftime("%Y-%m-%d"):
        return dict(status="closed", key=key, why="Oracle posting end date passed (validThrough)")
    text = " ".join(strip(j.get(k)) for k in ("ShortDescriptionStr", "ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr"))
    loc = "; ".join(x for x in [j.get("PrimaryLocation")] + [l.get("Name") for l in j.get("secondaryLocations") or []] if x)
    return dict(status="ok", key=key, title=j.get("Title"), text=text, loc=loc)


def workable(acct, code):
    key = f"wk:{code}"
    s, t, _ = get(f"https://apply.workable.com/api/v2/accounts/{acct}/jobs/{code}")
    if s == 404:
        return dict(status="closed", key=key, why="Workable 404")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"Workable {s}")
    j = json.loads(t)
    if j.get("state") not in (None, "published"):
        return dict(status="closed", key=key, why=f"Workable: {j.get('state')}")
    locs = j.get("locations") or [j.get("location") or {}]
    loc = "; ".join(", ".join(x for x in [l.get("city"), l.get("region"), l.get("country")] if x) for l in locs if isinstance(l, dict))
    return dict(status="ok", key=key, title=j.get("title"), text=" ".join(strip(j.get(k)) for k in ("description", "requirements", "benefits")),
                loc=loc + (" (remote)" if j.get("remote") else ""))


def rippling(url):
    s, t, final = get(url, accept="text/html")
    uid = re.search(r"/jobs/([0-9a-f-]{36})", url)
    key = f"rp:{uid.group(1)}" if uid else "url:" + url.split("?")[0]
    if "job_not_found" in (final or "") or s in (404, 410):
        return dict(status="closed", key=key, why="Rippling: job not found")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t or "", flags=re.S)
    if s != 200 or not m:
        return dict(status="unreadable", key=key, why=f"Rippling page {s}")
    jp = ((json.loads(m.group(1)).get("props") or {}).get("pageProps") or {}).get("apiData", {}).get("jobPost") or {}
    if not jp:
        return dict(status="closed", key=key, why="Rippling: no job post")
    desc = jp.get("description") or {}
    text = " ".join(strip(v) for v in (desc.values() if isinstance(desc, dict) else [desc]) if isinstance(v, str))
    return dict(status="ok", key=key, title=jp.get("name"), text=text, loc="; ".join(jp.get("workLocations") or []))


SF_URL = re.compile(r"[?&]ats=successfactors|\.successfactors\.(com|eu)/|career\d*\.sapsf\.|jobs\.sap\.com/job/|/job/[^/?#]+/\d{7,}/?(?:[?#]|$)", re.I)


ICIMS = re.compile(r"https?://([\w-]+\.icims\.com)/jobs/(\d+)(/[^/?#]+)?", re.I)


def icims_read_url(u):
    """Pure (tested). An iCIMS link (any page mode: mode=apply, in_iframe, mobile, /login …) → the posting page that
    carries the JobPosting data: https://<host>/jobs/<id>[/<slug>]/job?in_iframe=1. The outer iCIMS page holds the
    job only inside an iframe, mode=apply opens the form (JSA-284). None when the link is not one iCIMS posting."""
    m = ICIMS.search(u or "")
    if not m:
        return None
    slug = m.group(3) if m.group(3) and m.group(3).lower() not in ("/job", "/login", "/candidate") else ""
    return f"https://{m.group(1).lower()}/jobs/{m.group(2)}{slug}/job?in_iframe=1"


def sf_route(u):
    """Pure (tested). True when a URL goes to the SuccessFactors reader: SF_URL matches and the host is not a job board
    whose links look alike (Built In, LinkedIn, Indeed, Glassdoor)."""
    return bool(SF_URL.search(u or "")) and not re.search(r"builtin\.com|linkedin\.com|indeed\.com|glassdoor\.", u or "", re.I)


def sf_text(html):
    """Pure (tested). A SuccessFactors career-site job page (RMK) → {title, text, loc} or None: title from
    itemprop="title", location from class="jobGeoLocation", the text from itemprop="description" up to the page footer."""
    i = html.find('itemprop="description"')
    if i < 0:
        return None
    title = re.search(r'itemprop="title"[^>]*>(.*?)<', html, flags=re.S)
    loc = re.search(r'class="jobGeoLocation"[^>]*>(.*?)<', html, flags=re.S)
    ends = [j for j in (html.find('class="jobfooter"', i), html.find('id="footer"', i), html.find('<footer', i)) if j > i]
    end = min(ends) if ends else i + 30000
    if ends and html[end] != "<":
        end = html.rfind("<", 0, end)                             # cut at the start of the footer's tag, not inside it
    seg = html[html.find(">", i) + 1: end]
    text = strip(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", seg, flags=re.S)))
    return dict(title=strip(title.group(1)) if title else "", text=text, loc=strip(loc.group(1)) if loc else "") if text else None


def successfactors_page(url, key):
    """SuccessFactors career sites (careers.<company>.com/job/<slug>/<id>/, ?ats=successfactors) are server-rendered:
    the JD sits in itemprop="description". An error page / 404 / "no longer available" = closed (JSA-092, 2026-11-04)."""
    s, t, final = get(url, accept="text/html")
    if s in (404, 410) or "/errorpage" in (final or "") or (t and (re.search(r"job (is )?no longer (available|active)|position has been filled|job not found|page you are trying to (reach|access|view) is (no longer|for employees)|for employees\. please log ?in", t, re.I) and 'itemprop="description"' not in t)):
        return dict(status="closed", key=key, why=f"SuccessFactors page {s} {'errorpage' if '/errorpage' in (final or '') else ''}".strip())
    if s != 200 or not t:
        return dict(status="unreadable", key=key, why=f"SuccessFactors page {s}")
    x = sf_text(t)
    return dict(status="ok", key=key, **x) if x else dict(status="unreadable", key=key, why="no itemprop=description on the SuccessFactors page")


# ---------------------------------------------------------------- JSA-300: BambooHR, ADP Workforce Now, gh_jid boards named on the page
BAMBOO = re.compile(r"https?://([\w-]+)\.bamboohr\.com/(?:careers/|jobs/view\.php\?id=)(\d+)", re.I)
ADP_WFN = re.compile(r"https?://(workforcenow(?:\.cloud)?\.adp\.com)/mascsr/default/mdf/recruitment/recruitment\.html\?", re.I)
GH_BOARD = re.compile(r"(?:boards\.greenhouse\.io/embed/job_board(?:/js)?\?for=|job-boards(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?|"
                      r"boards(?:\.eu)?\.greenhouse\.io/|boards-api(?:\.eu)?\.greenhouse\.io/v1/boards/)([\w-]+)", re.I)


def bamboohr(co, jid):
    """BambooHR career pages load the job by script; the same site's JSON (careers/<id>/detail) has it. 404 = removed."""
    co = co.lower()
    key = f"bh:{co}:{jid}"
    s, t, _ = get(f"https://{co}.bamboohr.com/careers/{jid}/detail")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"BambooHR {s} (posting removed)")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"BambooHR {s}")
    jo = ((json.loads(t).get("result") or {}).get("jobOpening")) or {}
    if not jo:
        return dict(status="closed", key=key, why="BambooHR: no job opening")
    st = str(jo.get("jobOpeningStatus") or "Open")
    if st.lower() != "open":
        return dict(status="closed", key=key, why=f"BambooHR: {st}")
    l = jo.get("location") or {}
    loc = ", ".join(str(x) for x in (l.get("city"), l.get("state"), l.get("addressCountry")) if x)
    if str(jo.get("locationType") or "") == "1":
        loc = (loc + " (remote)").strip()
    return dict(status="ok", key=key, title=jo.get("jobOpeningName"), text=strip(jo.get("description")), loc=loc)


def adp_wfn_api(u):
    """Pure (tested). An ADP Workforce Now career-center link (…/mascsr/default/mdf/recruitment/recruitment.html?cid=…&jobId=…)
    → (posting key, URL of its public job-requisitions JSON), or None when the link names no cid or no jobId (a job list)."""
    m = ADP_WFN.search(u or "")
    if not m:
        return None
    q = {k.lower(): v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(u).query).items() if v and v[0]}
    cid, jid = q.get("cid"), q.get("jobid")
    qv = lambda v: urllib.parse.quote(v, safe="")
    if not cid or not jid:
        return None
    api = (f"https://{m.group(1).lower()}/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions/"
           f"{qv(jid)}?cid={qv(cid)}&lang=en_US" + (f"&ccId={qv(q['ccid'])}" if q.get("ccid") else ""))
    return f"adp:{cid.lower()}:{jid.lower()}", api


def adp_wfn(u):
    key, api = adp_wfn_api(u)
    s, t, _ = get(api)
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"ADP {s} (requisition removed)")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"ADP {s}")
    j = json.loads(t)
    if not j.get("itemID") and not j.get("requisitionTitle"):   # an empty requisition = the posting was taken down (live 11-11)
        return dict(status="closed", key=key, why="ADP: requisition not found")
    locs = []
    for r in j.get("requisitionLocations") or []:
        a = r.get("address") or {}
        locs.append(", ".join(x for x in (a.get("cityName"), (a.get("countrySubdivisionLevel1") or {}).get("codeValue"),
                                           (a.get("country") or {}).get("codeValue") if isinstance(a.get("country"), dict) else a.get("countryCode")) if x))
    return dict(status="ok", key=key, title=j.get("requisitionTitle"), text=strip(j.get("requisitionDescription")),
                loc="; ".join(x for x in locs if x))


def gh_boards_in_page(page):
    """Pure (tested). The Greenhouse board names a company careers page embeds (embed/job_board?for=<b>, job-boards.greenhouse.io/<b>,
    boards-api …/boards/<b>), in page order, each once; generic path words (embed, v1, jobs) are not boards."""
    out = []
    for m in GH_BOARD.finditer(page or ""):
        b = m.group(1).lower()
        if b not in ("embed", "v1", "jobs", "job_app", "job_board") and b not in out:
            out.append(b)
    return out


def gh_jid_page(u, jid):
    """A company page with ?gh_jid=: boards guessed from the host first; when none answers, the board the page itself embeds
    (SambaNova: sambanova.ai → board sambanovasystems). A board named on the page answering 404 = posting removed."""
    x = greenhouse(guess_boards(urllib.parse.urlparse(u).netloc), jid, strict=False)
    if x["status"] != "unreadable":
        return x
    s, t, _ = get(u, accept="text/html", tries=2)
    boards = gh_boards_in_page(t if s == 200 else "")
    return greenhouse(boards, jid, strict=True) if boards else x



GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def clearcompany_route(u):
    """Pure (tested). A ClearCompany posting link → (company short name lower-cased, job id lower-cased) or None:
    https://<co>.clearcompany.com/careers/jobs/<guid>[/apply …] and https://apply.clearcompany.com/<co>?jobId=<guid>
    (jobid / JOBID too). Other ClearCompany pages (the job list, app.clearcompany.com) → None."""
    m = re.search(rf"https?://([\w-]+)\.clearcompany\.com/careers/jobs/({GUID})", u or "", re.I)
    if m and m.group(1).lower() not in ("apply", "app", "www", "careers-api", "careers-content"):
        return m.group(1).lower(), m.group(2).lower()
    m = re.search(rf"https?://apply\.clearcompany\.com/([\w-]+)/?\?(?:[^#]*&)?jobid=({GUID})", u or "", re.I)
    if m:
        return m.group(1).lower(), m.group(2).lower()
    return None


def clearcompany_site_id(page):
    """Pure (tested). The careers-site id an apply.clearcompany.com page names (data-site-id="<guid>"), lower-cased; None."""
    m = re.search(rf'data-site-id\s*=\s*["\']({GUID})["\']', page or "", re.I)
    return m.group(1).lower() if m else None


def clearcompany(co, jid):
    """ClearCompany pages load the job by script. The hosted page apply.clearcompany.com/<co>?jobId=<id> names the site id;
    careers-api.clearcompany.com/v1/<site>/<JOB ID> is the posting's JSON (404 = removed; live 11-11, JSA-300)."""
    key = f"cc:{co}:{jid}"
    s, t, _ = get(f"https://apply.clearcompany.com/{co}?jobId={jid}", accept="text/html", tries=2)
    site = clearcompany_site_id(t if s == 200 else "")
    if not site:
        return dict(status="unreadable", key=key, why=f"ClearCompany: no site id on the hosted page ({s})")
    s, t, _ = get(f"https://careers-api.clearcompany.com/v1/{site}/{jid.upper()}?source=CJB-0")
    if s in (404, 410):
        return dict(status="closed", key=key, why=f"ClearCompany {s} (posting removed)")
    if s != 200:
        return dict(status="unreadable", key=key, why=f"ClearCompany {s}")
    j = json.loads(t)
    if not j.get("positionTitle") and not j.get("description"):
        return dict(status="closed", key=key, why="ClearCompany: empty posting")
    locs = [", ".join(x for x in (l.get("city"), l.get("subdivision"), l.get("country")) if x) for l in j.get("locations") or [] if isinstance(l, dict)]
    return dict(status="ok", key=key, title=j.get("positionTitle"), text=strip(j.get("description")),
                loc="; ".join(x for x in locs if x) or (j.get("location") or ""))

# ---------------------------------------------------------------- dispatch by URL
def load(url, depth=0):
    u = url or ""
    m = re.search(r"greenhouse\.io/(?:embed/job_app\?for=([\w-]+)&token=(\d+)|([\w-]+)/jobs/(\d+))", u)
    if m:
        return greenhouse([m.group(1) or m.group(3)], m.group(2) or m.group(4), strict=True)
    m = re.search(r"jobs\.(eu\.)?lever\.co/([\w.-]+)/([0-9a-f-]{36})", u)
    if m:
        return lever(m.group(2), m.group(3), bool(m.group(1)))
    m = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})", u)
    if m:
        return ashby(urllib.parse.unquote(m.group(1)), m.group(2))
    m = re.search(r"[?&]gh_jid=(\d+)", u)
    if m:
        return gh_jid_page(u, m.group(1))
    m = re.search(r"https?://(([\w-]+)\.wd\d+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)/job/(?:.*/)?([^/?#]+)", u)
    if m:
        return workday(m.group(1), m.group(2), m.group(3), m.group(4), page=u)
    m = re.search(r"https?://(wd\d+\.myworkdaysite\.com)/(?:[a-z]{2}-[A-Z]{2}/)?recruiting/([\w-]+)/([\w-]+)/job/(?:.*/)?([^/?#]+)", u)
    if m:   # JSA-284: the same Workday reader on the myworkdaysite.com host (tenant in the path)
        return workday(m.group(1), m.group(2), m.group(3), m.group(4), page=u)
    m = ICIMS.search(u)
    if m:   # JSA-284
        return jsonld_page(icims_read_url(u), f"ic:{m.group(1).lower()}:{m.group(2)}")
    m = BAMBOO.search(u)
    if m:   # JSA-300
        return bamboohr(m.group(1), m.group(2))
    if adp_wfn_api(u):   # JSA-300
        return adp_wfn(u)
    cc = clearcompany_route(u)
    if cc:   # JSA-300
        return clearcompany(*cc)
    m = re.search(r"jobs\.smartrecruiters\.com/([\w-]+)/(\d+)", u)
    if m:
        return smartrecruiters(m.group(1), m.group(2))
    m = re.search(r"(?:lifeattiktok|joinbytedance)\.com/search/(\d+)", u)
    if m:
        return tiktok_page(u.split("?")[0], f"tt:{m.group(1)}")
    m = re.search(r"jobs\.bytedance\.com/.*position/(\d+)", u)
    if m:
        return bytedance(m.group(1))
    m = re.search(r"amazon\.jobs/(?:[a-z]{2}/)?jobs/(\d+)", u)
    if m:
        return amazon(m.group(1), u.split("?")[0])
    m = re.search(r"(\w[\w-]*\.fa\.[\w.]*oraclecloud\.com)/hcmUI/CandidateExperience/[a-z]{2}/sites/([\w-]+)/(?:job|requisitions/preview)/(\d+)", u)
    if m:
        return oracle(m.group(1), m.group(2), m.group(3))
    m = re.search(r"apply\.workable\.com/([\w-]+)/j/(\w+)", u)
    if m:
        return workable(m.group(1), m.group(2))
    if "ats.rippling.com/" in u:
        return rippling(u)
    m = re.search(r"usajobs\.gov(?::443)?/(?:job|GetJob/ViewDetails)/(\d+)", u, re.I)
    if m:
        return usajobs(m.group(1), f"usajobs:{m.group(1)}")
    m = re.search(r"jobs\.apple\.com/[a-z]{2}-[a-z]{2}/details/(\d+)", u)
    if m:
        return apple_page(u.split("?")[0], f"apple:{m.group(1)}")
    m = re.search(r"google\.com/about/careers/applications/jobs/results/(\d+)", u)
    if m:
        return google_page(u, f"google:{m.group(1)}")
    m = re.search(r"wellfound\.com/jobs/(\d+)", u)
    if m:
        return wellfound_page(u.split("?")[0], f"wf:{m.group(1)}")
    m = re.search(r"builtin\.com/job/[^/]+/(\d+)", u)
    if m:
        return jsonld_page(u.split("?")[0], f"bi:{m.group(1)}")
    m = re.search(r"jobright\.ai/jobs/info/(\w+)", u)
    if m:  # Jobright answers scripts with a "Security check" page; never try to get around it
        return dict(status="unreadable", key=f"jr:{m.group(1)}", why="Jobright security check - read the JD when applying")
    if re.search(r"zapply\.jobs/|go\.vansh\.nyc/", u) and depth == 0:  # link shorteners: follow to the real posting
        s, _, final = get(u, accept="text/html")
        host = urllib.parse.urlparse(final or "").netloc
        if final and host and not re.search(r"zapply\.jobs|vansh\.nyc", host):
            return load(final, 1)
        if re.search(r"zapply\.jobs/jobs/?$", final or ""):
            return dict(status="closed", key="url:" + u.split("?")[0], why="zapply link expired (lands on the job list)")
        return dict(status="unreadable", key="url:" + u.split("?")[0], why=f"link did not resolve ({s})")
    if re.search(r"linkedin\.com|joinhandshake\.com", u):
        return dict(status="unreadable", key="url:" + u.split("?")[0], why="needs a login (LinkedIn / Handshake)")
    if sf_route(u):   # after every known site (Built In's /job/<slug>/<id> looks alike)
        m = re.search(r"/(\d{7,})/?(?:[?#]|$)", u)
        return successfactors_page(u, f"sf:{urllib.parse.urlparse(u).netloc}:{m.group(1) if m else u.split('?')[0]}")
    if u.startswith("http") and depth <= 1:
        return jsonld_page(u, "url:" + u.split("?")[0].rstrip("/").lower())
    return dict(status="unreadable", key="url:" + u, why="no URL")


def main():
    args = sys.argv[1:]
    src, out = args[0], args[1]
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 16
    only = set(open(args[args.index("--only-new") + 1]).read().split()) if "--only-new" in args else None
    rows = [r for r in json.load(open(src)) if only is None or r["id"] in only]
    prev = {}
    if "--retry" in args:  # keep ok/closed rows from an earlier run, refetch the rest (429s, wrong-slug 404s, errors)
        for l in open(args[args.index("--retry") + 1]):
            x = json.loads(l)
            keep = x["status"] == "ok" or (x["status"] == "closed" and not x["key"].startswith("bi:")) \
                or re.search(r"needs a login|no URL", x.get("why", ""))
            if keep:
                prev[x["id"]] = x
    s, _, _ = get("https://boards-api.greenhouse.io/v1/boards/anthropic/jobs", tries=1)
    if s == 0:
        sys.exit("Cannot reach boards-api.greenhouse.io - this machine has no access to the job boards.")
    print(f"{len(rows)} roles, fetching with {workers} threads ...", file=sys.stderr, flush=True)
    t0, done, res = time.time(), 0, {}
    res.update({i: x for i, x in prev.items() if i in {r["id"] for r in rows}})
    todo = [r for r in rows if r["id"] not in res]
    print(f"kept {len(res)} from the earlier run, fetching {len(todo)}", file=sys.stderr, flush=True)
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(load, r.get("url")): r for r in todo}
        for f in cf.as_completed(futs):
            r = futs[f]
            try:
                x = f.result()
            except Exception as e:
                x = dict(status="unreadable", key="url:" + (r.get("url") or ""), why="error " + str(e)[:80])
            res[r["id"]] = {"id": r["id"], "level": r.get("level"), **x}
            done += 1
            if done % 250 == 0:
                print(f"{done}/{len(todo)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(res[r["id"]], ensure_ascii=False) + "\n")
    from collections import Counter
    print("status", dict(Counter(x["status"] for x in res.values())), f"{time.time() - t0:.0f}s")
    print("unreadable why", Counter(x.get("why", "")[:40] for x in res.values() if x["status"] == "unreadable").most_common(8))


if __name__ == "__main__":
    main()
