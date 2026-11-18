#!/usr/bin/env python3
"""Where is each Wellfound row really applied to? (JSA-171, 2026-11-05)

200 可投 rows (11-05) have `url` = a Wellfound job page (`source` wellfound_search, JSA-108) and no `ats_url`. Many are
jobs Wellfound imports from the company's own site (Celestica, Skyworks …), so the Apply control leads to the company
ATS, where the existing runners can apply; the rest are applied to inside Wellfound (its own modal, Joey signed in).

Runs in the job Chrome only (CDP 9222; Joey's weekly full refresh or a session — never a LaunchAgent): one new tab,
each row's Wellfound page in turn, 8–14 s apart. The page is only read: every link (href + label), every button label,
the URLs inside the page's own JSON (`__NEXT_DATA__` / ld+json) under apply-like keys. Nothing is submitted. With
--peek, a page whose only apply control is a button without a link gets that one button clicked (exact label "Apply" /
"Apply now" / "Easy apply" / "Apply on company site" …, never "Send" / "Submit"): a new tab or a navigation is recorded
and closed / gone back from, an in-site dialog is read and closed with Escape — no field is filled, nothing is sent.
A sign-in page, CAPTCHA or "verify you are human" page stops the run and is reported — never solved or worked around.

Result per row (`classify`, pure): apply_via = external | wellfound | closed | unknown, plus a reason; for external the
best apply link (`pick_external`: tracking parameters and redirect wrappers removed) → `apply_url`, and when it is a
posting (not a board / careers home page) also `ats_url` + ats_resolved + ats_resolved_on, so the 08:45 gate re-reads the
real JD there and the platform runners can apply. Never changes url, elig or any other field; a row that already has an
ats_url keeps it. Writes only with --write, through store.py.

    python3 wellfound_apply.py [--limit N | --ids J1,J2,…] [--peek [--click-out]] [--all-elig] [--redo] [--save pages.json] [--write]
--click-out (JSA-171 method B, Joey 2026-11-05 「两个方法都试试」): when the peeked dialog says the company website takes the
application, its "Apply on website" button (exact label) is clicked too — Wellfound warns "Your job status will change"
in the candidate's account — and the new tab's / navigation's final URL (after redirects, ~10 s) goes to `opened`; the tab
is closed (or gone back from) and the dialog Escaped. Nothing on the company site is filled or sent; a challenge or a
sign-in page there (a visible password field) stops the run.
    python3 wellfound_apply.py --json pages.json [--write]       # saved page records (from --save), no browser
    python3 wellfound_apply.py --html <dir of saved job pages>   # <job id>*.html files, no browser
Without --write: counts (and one line per row) only. Selectors unverified until the first live run (see SKILL.md).
Spec + DeepSeek-written cases: scripts/test_cases/wellfound_apply_*; harness scripts/test_wellfound_apply.py.
"""
import html as H, json, os, random, re, sys, datetime as dt
from collections import Counter
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urljoin, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from wellfound_search import job_id  # noqa: E402
from indeed_search import BLOCK  # noqa: E402  (verify you are human / captcha / just a moment …)
from platform_counts import platform_of  # noqa: E402  (known ATS host → name)

WF_HOSTS = ('wellfound.com', 'angel.co', 'angellist.com')
NOT_APPLY_HOSTS = ('linkedin.com', 'twitter.com', 'x.com', 'facebook.com', 'instagram.com', 'youtube.com', 'github.com',
                   'crunchbase.com', 'glassdoor.com', 'medium.com', 'apple.com', 'google.com', 'goo.gl', 'bit.ly',
                   'apps.apple.com', 'play.google.com')
APPLY_LABEL = re.compile(r'\bapply\b', re.I)
APPLY_BUTTON = re.compile(r'^\s*(?:easy\s+)?apply(?:\s+now)?(?:\s+(?:on|at|via)\s+(?:the\s+)?(?:company|employer)(?:\'s)?\s+(?:site|website))?'
                          r'(?:\s+externally)?\s*$', re.I)
APPLIED = re.compile(r'^\s*(?:applied|already applied|you applied)\b', re.I)
APPLIED_NAV = re.compile(r'^/jobs/applications/?$', re.I)    # the site's own "Applied" tab, on every page (live 11-05)
APPLY_KEY = re.compile(r'apply|application|external|ats', re.I)
SIGNIN_PATH = re.compile(r'^/(?:login|signin|sign_in|signup|sign_up|join|onboarding)\b', re.I)
SIGNIN_TEXT = re.compile(r'\b(?:log ?in|sign ?in|sign ?up|create an account|join wellfound)\s+to\s+apply\b', re.I)
CLOSED = re.compile(r'no longer accepting applications|(?:job|position|posting|listing) (?:is )?no longer (?:available|active|open)|'
                    r'this (?:job|position|posting|listing|role) (?:has been|is|was) (?:closed|filled|removed|archived)|'
                    r'position has been filled|(?:job|posting|listing) has expired|\bjob not found\b|\bpage not found\b', re.I)
MODAL_INSITE = re.compile(r'send application|submit application|write a note|note to|cover letter|apply to|'
                          r'your application|why (?:are you|do you)', re.I)
MODAL_OUTSIDE = re.compile(r'managed outside (?:of )?wellfound|apply on (?:the )?(?:company(?:\'s)? )?website', re.I)   # live 11-05
CLICK_OUT = re.compile(r'^\s*apply on (?:the )?(?:company(?:\'s)? )?website\s*$', re.I)   # the dialog's own button (--click-out)
MODAL_PROFILE = re.compile(r'cannot apply to this job because your profile is missing[^\n]*\n((?:.+\n?){1,4}?)\s*please apply again', re.I)
WRAP_KEYS = ('url', 'u', 'q', 'target', 'redirect', 'redirect_url', 'redirecturl', 'dest', 'destination', 'to', 'link', 'goto', 'out')
TRACKING = re.compile(r'^(?:utm_[a-z_]+|gh_src|source|src|ref|referrer|ref_src|fbclid|gclid|msclkid|mc_cid|mc_eid|iisn|iis|trk|'
                      r'lever-source|lever-via|_hs[a-z]+)$', re.I)
# iCIMS page-mode parameters (JSA-284): mode=apply opens the application form instead of the posting, in_iframe / mobile /
# needsRedirect / width / height / bga / jan1offset / jun1offset / hub only size the embed — none names the posting
ICIMS_DROP = re.compile(r'^(?:mode|in_iframe|mobile|needsredirect|width|height|bga|jan1offset|jun1offset|hub|hashed)$', re.I)
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
SLEEP = (8, 14)


def _path(u):
    try:
        return urlsplit(str(u or '')).path or ''
    except ValueError:
        return ''


def _host(url):
    try:
        return (urlsplit(str(url or '').strip()).hostname or '').lower().strip('.')
    except ValueError:
        return ''


def _on(host, names):
    return any(host == n or host.endswith('.' + n) for n in names)


def is_wellfound(url):
    """Pure. A wellfound.com / angel.co URL (any subdomain)."""
    return _on(_host(url), WF_HOSTS)


def wf_job_page(url):
    """Pure. A Wellfound URL whose path has /jobs/<digits> (/jobs/123-x, /company/acme/jobs/123-x)."""
    return is_wellfound(url) and bool(re.search(r'/jobs/\d+', urlsplit(str(url)).path))


def clean_url(url):
    """Pure (tested). An apply link as read from the page → the link itself: redirect wrappers unwrapped (a query
    parameter in WRAP_KEYS holding an absolute http(s) URL, on a host that is not a known ATS; up to 3 levels, also
    percent-encoded), tracking parameters dropped (utm_*, gh_src, source, src, ref, …; gh_jid and every other one kept),
    an empty query removed, surrounding spaces trimmed. On *.icims.com the page-mode parameters (ICIMS_DROP: mode=apply,
    in_iframe, mobile, needsRedirect, sizes) are dropped too, so the link opens the posting (JSA-284). '' for anything that is not an http(s) URL."""
    u = H.unescape(str(url or '')).strip().replace('\\/', '/').replace('\\u002F', '/').replace('\\u0026', '&')
    for _ in range(4):
        if not re.match(r'https?://', u, re.I):
            return ''
        try:
            p = urlsplit(u)
        except ValueError:
            return ''
        if platform_of(u):
            break
        vals = [unquote(v) if re.match(r'https?%3A', v, re.I) else v
                for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() in WRAP_KEYS]
        inner = next((v for v in vals if re.match(r'https?://', v, re.I)), None)
        if not inner:
            break
        u = inner.strip()
    try:
        p = urlsplit(u)
    except ValueError:
        return ''
    if not p.hostname:
        return ''
    # kept parameters stay byte for byte as the page wrote them (no re-encoding: an ATS may care about + vs %20)
    q = [x for x in p.query.split('&') if x and not TRACKING.match(unquote(x.split('=', 1)[0]))]
    if (p.hostname or '').lower().endswith('.icims.com'):
        q = [x for x in q if not ICIMS_DROP.match(unquote(x.split('=', 1)[0]))]
    return urlunsplit((p.scheme.lower(), p.netloc, p.path, '&'.join(q), p.fragment))


def posting_like(url):
    """Pure (tested). True when the URL names one posting, not a board or careers home page: Workday /job/ or /details/;
    Greenhouse /jobs/<digits> or gh_jid=<digits>; Workable /j/<code>; anywhere: a UUID, or 5+ digits in a row in a path
    segment or a query value."""
    try:
        p = urlsplit(str(url or ''))
    except ValueError:
        return False
    plat, path = platform_of(url), p.path or ''
    q = parse_qsl(p.query, keep_blank_values=True)
    if plat == 'workday':
        return bool(re.search(r'/(?:job|details)/', path))
    if plat == 'greenhouse' and (re.search(r'/jobs/\d+', path) or any(k == 'gh_jid' and v.isdigit() for k, v in q)):
        return True
    if plat == 'workable' and re.search(r'/j/[0-9A-Za-z]{6,}', path):
        return True
    if UUID.search(path) or any(UUID.search(v) for _, v in q):
        return True
    return bool(re.search(r'\d{5,}', path) or any(re.search(r'\d{5,}', v) for _, v in q))


def pick_external(page):
    """Pure (tested). page {'opened', 'links', 'data_urls', …} → the best external apply URL (cleaned), or ''.
    Candidates, in source order: (a) `opened` — URLs a peek click opened; (b) links whose label contains "apply";
    (c) `data_urls` whose key looks like apply / application / external / ats; (d) any other link or data URL on a known
    ATS host that is posting_like. Wellfound / angel.co hosts and social / app-store / short-link hosts are never
    candidates. Best = known ATS and posting_like, then known ATS, then posting_like, then the rest; ties → source
    order, then page order."""
    cands = []
    for u in page.get('opened') or []:
        cands.append((0, u))
    for l in (page.get('modal_links') or []) + (page.get('links') or []):   # modal_links: the peeked dialog's links
        if APPLY_LABEL.search(str(l.get('text') or '')):
            cands.append((1, l.get('href')))
    for d in page.get('data_urls') or []:
        if APPLY_KEY.search(str(d.get('key') or '')):
            cands.append((2, d.get('url')))
    for u in [l.get('href') for l in page.get('links') or []] + [d.get('url') for d in page.get('data_urls') or []]:
        c = clean_url(u)
        if c and platform_of(c) and posting_like(c):
            cands.append((3, u))
    best, seen = None, set()
    for i, (src, raw) in enumerate(cands):
        c = clean_url(raw)
        h = _host(c)
        if not c or c in seen or _on(h, WF_HOSTS) or _on(h, NOT_APPLY_HOSTS):
            continue
        seen.add(c)
        ats, post = bool(platform_of(c)), posting_like(c)
        rank = (0 if ats and post else 1 if ats else 2 if post else 3, src, i)
        if best is None or rank < best[0]:
            best = (rank, c)
    return best[1] if best else ''


def click_out_index(labels):
    """Pure (tested). The peeked dialog's control labels → the index of the first one that is exactly "Apply on website"
    (also "Apply on the website" / "Apply on company website" / "Apply on the company website" / "Apply on the
    company's website"; whole label, any case, surrounding spaces ignored), or None. Never "Send application", "Submit",
    "Apply", "Apply now"."""
    for i, l in enumerate(labels or []):
        if CLICK_OUT.match(str(l or '')):
            return i
    return None


def opened_stop(info):
    """Pure (tested). What the click-out opened, {'url', 'title', 'text', 'password'} → 'blocked' (a challenge: BLOCK in
    the title, or in a text shorter than 1500 characters) | 'signin' (a Wellfound sign-in path, or a visible password
    field on any site) | '' (fine: the URL is only recorded, nothing on the page is touched)."""
    i = info or {}
    title, text, url = str(i.get('title') or ''), str(i.get('text') or ''), str(i.get('url') or '')
    if BLOCK.search(title) or (len(text) < 1500 and BLOCK.search(text)):
        return 'blocked'
    if (is_wellfound(url) and SIGNIN_PATH.match(_path(url))) or i.get('password') is True:
        return 'signin'
    return ''


def classify(page):
    """Pure (tested). One page record → {'via', 'ats_url', 'apply_url', 'reason'}; via is one of
    blocked | signin | closed | external | wellfound | unknown (blocked / signin stop the run and are never written)."""
    url, title, text = str(page.get('url') or ''), str(page.get('title') or ''), str(page.get('text') or '')
    out = lambda via, reason, apply_url='', ats_url='': {'via': via, 'ats_url': ats_url, 'apply_url': apply_url, 'reason': reason}
    if BLOCK.search(title) or (len(text) < 1500 and BLOCK.search(text)):
        return out('blocked', 'challenge page (CAPTCHA / verify you are human) — nothing solved')
    stop = page.get('click_out_stop')
    if stop == 'blocked':
        return out('blocked', 'Apply on website opened a challenge page — nothing solved')
    if stop == 'signin':
        return out('signin', 'Apply on website opened a sign-in page — nothing typed')
    path = urlsplit(url).path if url else ''
    if is_wellfound(url) and SIGNIN_PATH.match(path):
        return out('signin', f'sent to the sign-in page {path}')
    if any(is_wellfound(u) and SIGNIN_PATH.match(urlsplit(str(u)).path) for u in page.get('opened') or []):
        return out('signin', 'Apply sent to the Wellfound sign-in page (Joey not signed in)')
    if is_wellfound(url) and not wf_job_page(url):
        return out('closed', f'job page redirected to {path or "/"}')
    m = CLOSED.search(title) or CLOSED.search(text)
    if m:
        return out('closed', f'page says "{m.group(0)}"')
    ext = pick_external(page)
    if ext:
        if posting_like(ext):
            return out('external', f'apply link → {platform_of(ext) or _host(ext)}', ext, ext)
        return out('external', f'apply link is a board / careers page, not one posting ({_host(ext)})', ext)
    modal = str(page.get('modal') or '')
    if modal and MODAL_OUTSIDE.search(modal):
        return out('external', 'Wellfound says the company website takes the application; its link was not readable')
    m = MODAL_PROFILE.search(modal)
    if m:
        items = re.sub(r'\s+', ' ', m.group(1)).strip()[:80]
        return out('wellfound', f'Apply opens the Wellfound apply dialog — blocked: Wellfound profile is missing {items}')
    if modal and MODAL_INSITE.search(modal):
        return out('wellfound', 'Apply opens the Wellfound apply dialog')
    if SIGNIN_TEXT.search(text):
        return out('signin', 'page asks to sign in to apply (Joey not signed in to Wellfound)')
    labels = [str(b) for b in page.get('buttons') or []] + [str(l.get('text') or '') for l in page.get('links') or []
                                                            if not APPLIED_NAV.match(_path(l.get('href')))]
    if any(APPLIED.match(b) for b in labels):
        return out('wellfound', 'already applied on Wellfound')
    if any(APPLY_BUTTON.match(str(l.get('text') or '')) and is_wellfound(l.get('href')) for l in page.get('links') or []):
        return out('wellfound', 'Apply link stays on Wellfound')
    if any(APPLY_BUTTON.match(b) for b in page.get('buttons') or []):
        if page.get('peeked'):
            snip = re.sub(r'\s+', ' ', modal).strip()[:60]
            return out('unknown', 'peek: the Apply button opened nothing readable' + (f' (dialog: "{snip}")' if snip else ''))
        return out('unknown', 'Apply button without a link (needs --peek)')
    return out('unknown', 'no Apply control on the page')


def page_from_html(page_html, url=''):
    """Pure (tested). A saved job page's HTML → the same record the browser extractor returns: {'url', 'title', 'text',
    'links': [{'href' (absolute), 'text'}], 'buttons': [labels], 'data_urls': [{'key', 'url'}]}. Scripts and styles are
    not part of the text; data_urls come from JSON inside <script> tags ("<key>": "http…" where the key ends in url /
    link / href)."""
    t = str(page_html or '')
    m = re.search(r'<title[^>]*>(.*?)</title>', t, re.S | re.I)
    title = H.unescape(re.sub(r'\s+', ' ', m.group(1))).strip() if m else ''
    data = []
    for blob in re.findall(r'<script[^>]*>(.*?)</script>', t, re.S | re.I):
        for k, v in re.findall(r'"([A-Za-z_]*(?:[Uu]rl|URL|[Ll]ink|[Hh]ref))"\s*:\s*"(https?:[^"]+)"', blob):
            data.append({'key': k, 'url': v.replace('\\/', '/').replace('\\u002F', '/').replace('\\u0026', '&')})
    body = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', t, flags=re.S | re.I)
    txt = lambda s: re.sub(r'\s+', ' ', H.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()
    links = []
    for attrs, inner in re.findall(r'<a\b([^>]*)>(.*?)</a>', body, re.S | re.I):
        h = re.search(r'href\s*=\s*["\']([^"\']*)["\']', attrs, re.I)
        raw = H.unescape(h.group(1).strip()) if h else ''
        if not raw or re.match(r'#|mailto:|javascript:|tel:', raw, re.I):
            continue
        href = urljoin(url, raw) if url else raw
        if re.match(r'https?://', href, re.I):
            lab = txt(inner) or H.unescape((re.search(r'aria-label\s*=\s*["\']([^"\']*)["\']', attrs, re.I) or [None, ''])[1])
            links.append({'href': href, 'text': lab})
    buttons = [x for x in (txt(b) for b in re.findall(r'<button\b[^>]*>(.*?)</button>', body, re.S | re.I)) if x]
    text = '\n'.join(x for x in (txt(s) for s in re.split(r'<(?:br|/?p|/?div|/?h\d|/?li|/?section|/?main|/?button|/?a)\b[^>]*>', body, flags=re.I)) if x)
    return {'url': url, 'title': title, 'text': text[:6000], 'links': links, 'buttons': buttons, 'data_urls': data}


def targets(rows, all_elig=False, redo=False):
    """Pure. Store rows → the rows to read (score high → low): url a Wellfound job page, 可投 (or 待核实 too), no ats_url,
    not done before (--redo: again)."""
    ok = ('可投', '待核实') if all_elig else ('可投',)
    rows = [r for r in rows if wf_job_page(r.get('url')) and r.get('elig') in ok
            and not r.get('ats_url') and (redo or not r.get('apply_via'))]
    return sorted(rows, key=lambda r: (-(r.get('score') or 0), str(r.get('id'))))     # best rows first (--limit)


def apply_result(row, res, today):
    """Pure. Write one classify() result onto a store row (blocked / signin → unchanged). Returns the row."""
    if res['via'] in ('blocked', 'signin'):
        return row
    row.update(apply_via=res['via'], apply_via_reason=res['reason'], apply_via_on=today)
    if res.get('apply_url'):
        row['apply_url'] = res['apply_url']
    if res.get('ats_url') and not row.get('ats_url'):
        row.update(ats_url=res['ats_url'], ats_resolved='wellfound apply link (JSA-171)', ats_resolved_on=today)
        row.pop('ats_unresolved', None)
    return row


# ---------- browser (job Chrome over CDP; not part of the pure step) ----------
EXTRACT_JS = r"""() => {
  const abs = h => { try { return new URL(h, location.href).href } catch (e) { return '' } };
  const lab = e => ((e.innerText || e.value || e.getAttribute('aria-label') || '') + '').trim().replace(/\s+/g, ' ').slice(0, 100);
  const links = [...document.querySelectorAll('a[href]')].map(a => ({href: abs(a.getAttribute('href')), text: lab(a)}))
    .filter(l => /^https?:/i.test(l.href));
  const buttons = [...document.querySelectorAll('button, [role=button], input[type=submit], input[type=button]')].map(lab).filter(Boolean);
  const data = [], rx = /"([A-Za-z_]*(?:[Uu]rl|URL|[Ll]ink|[Hh]ref))"\s*:\s*"(https?:[^"]+)"/g;
  for (const s of document.querySelectorAll('script#__NEXT_DATA__, script[type="application/json"], script[type="application/ld+json"]')) {
    const t = s.textContent || ''; let m; rx.lastIndex = 0;
    while ((m = rx.exec(t)) && data.length < 80) data.push({key: m[1], url: m[2].replace(/\\u002F/g, '/').replace(/\\\//g, '/').replace(/\\u0026/g, '&')});
  }
  return {url: location.href, title: document.title, text: (document.body ? document.body.innerText : '').slice(0, 6000),
          links: links.slice(0, 400), buttons: buttons.slice(0, 120), data_urls: data};
}"""
DIALOG = '[role=dialog], [aria-modal=true], .ReactModal__Content'
MODAL_JS = """() => { const d = [...document.querySelectorAll('%s')].find(e => e.offsetParent !== null || e.getClientRects().length);
  return d ? {text: d.innerText.slice(0, 3000), links: [...d.querySelectorAll('a[href]')].map(a => ({href: a.href, text: a.innerText.trim()}))} : {text: '', links: []} }""" % DIALOG
OPENED_JS = """() => ({url: location.href, title: document.title, text: (document.body ? document.body.innerText : '').slice(0, 3000),
  password: [...document.querySelectorAll('input[type=password]')].some(e => e.offsetParent !== null)})"""


def _say(s):
    print(s, flush=True)


def _settle(p, secs=10):
    """Wait until a page's URL has not changed for 2.5 s (redirect chains), at most `secs`; → the URLs seen, in order."""
    seen, last, still = [], None, 0
    for _ in range(int(secs * 2)):
        try:
            u = p.url
        except Exception:
            break
        if u != last:
            seen.append(u); last, still = u, 0
        else:
            still += 1
            if still >= 5 and u and not u.startswith('about:'):
                break
        p.wait_for_timeout(500)
    return [u for u in seen if u and not u.startswith('about:')]


def _click_out(pg, ctx):
    """--click-out: in the open dialog, click exactly its "Apply on website" control (click_out_index), wait for the new tab
    or the navigation to settle (~10 s), read only its URL / title / text / whether a password field shows, close it (or go
    back), and read what the dialog says afterwards. Nothing on either site is typed, ticked or sent."""
    rec = {'clicked': False}
    ctrls, labels = [], []
    for c in pg.locator(DIALOG).locator('button, [role=button], a').all():
        try:
            if c.is_visible():
                ctrls.append(c); labels.append(c.inner_text().strip())
        except Exception:
            continue
    rec['labels'] = labels[:20]
    i = click_out_index(labels)
    if i is None:
        return rec
    pops, before, t0 = [], pg.url, dt.datetime.now()
    def cb(p):
        pops.append(p)
    ctx.on('page', cb)
    try:
        ctrls[i].click(timeout=8000); rec['clicked'] = True
        for _ in range(20):                                  # a new tab or a navigation, up to 10 s
            if pops or pg.url != before:
                break
            pg.wait_for_timeout(500)
    finally:
        ctx.remove_listener('page', cb)
    chain, infos = [], []
    try:
        for p in pops:
            try:
                p.wait_for_load_state('domcontentloaded', timeout=20000)
            except Exception:
                pass
            chain += _settle(p)
            try:
                infos.append(p.evaluate(OPENED_JS))
            except Exception:
                infos.append({'url': p.url})
    finally:                                                 # every tab the click opened is closed, whatever happened
        for p in pops:
            try:
                p.close()
            except Exception:
                pass
    if pg.url != before:
        chain += _settle(pg)
        try:
            infos.append(pg.evaluate(OPENED_JS))
        except Exception:
            infos.append({'url': pg.url})
        pg.go_back(wait_until='domcontentloaded'); pg.wait_for_timeout(2500)
    rec['chain'], rec['secs'] = chain, round((dt.datetime.now() - t0).total_seconds(), 1)
    rec['final'] = [x.get('url') for x in infos if x.get('url') and not str(x.get('url')).startswith('about:')]
    rec['final_title'] = [str(x.get('title') or '')[:150] for x in infos]
    rec['password'] = [bool(x.get('password')) for x in infos]
    stops = [opened_stop(x) for x in infos]
    rec['stop'] = 'blocked' if 'blocked' in stops else 'signin' if 'signin' in stops else ''
    pg.wait_for_timeout(1500)
    rec['modal_after'] = ((pg.evaluate(MODAL_JS) or {}).get('text') or '')[:1500]   # what Wellfound shows after the click
    return rec


def _peek(pg, ctx, click_out=False):
    """Click the one Apply button (exact label, no link) and record what happens; with click_out, an outside-Wellfound
    dialog's "Apply on website" is clicked too (_click_out). Never touches anything else inside."""
    btn = None
    for b in pg.locator('button, [role=button]').all():
        try:
            if b.is_visible() and APPLY_BUTTON.match(b.inner_text().strip()):
                btn = b; break
        except Exception:
            continue
    if btn is None:
        return {'opened': [], 'modal': '', 'modal_links': []}
    pops, before = [], pg.url
    def cb(p):                                               # a plain function: Playwright tags its handlers (list.append can't be)
        pops.append(p)
    ctx.on('page', cb)
    try:
        btn.click(timeout=8000); pg.wait_for_timeout(4000)
    finally:
        ctx.remove_listener('page', cb)
    opened = []
    for p in pops:
        try:
            p.wait_for_load_state('domcontentloaded', timeout=20000); p.wait_for_timeout(1500)
        except Exception:
            pass
        opened.append(p.url); p.close()
    if pg.url != before:
        opened.append(pg.url); pg.go_back(wait_until='domcontentloaded'); pg.wait_for_timeout(2000)
    m = pg.evaluate(MODAL_JS) or {}
    modal, links = m.get('text') or '', m.get('links') or []     # the dialog's links are read, never clicked
    out = {'opened': [u for u in opened if u and not u.startswith('about:')], 'modal': modal, 'modal_links': links}
    if click_out and modal and MODAL_OUTSIDE.search(modal):
        co = _click_out(pg, ctx)
        out['click_out'] = co
        out['opened'] += co.get('final') or []
        if co.get('stop'):
            out['click_out_stop'] = co['stop']
    if (pg.evaluate(MODAL_JS) or {}).get('text'):
        pg.keyboard.press('Escape'); pg.wait_for_timeout(800)
    try:                                                     # the page's apply / applied labels after the dialog closed
        out['buttons_after'] = [b for b in pg.evaluate(EXTRACT_JS).get('buttons', []) if APPLY_LABEL.search(b) or APPLIED.match(b)]
    except Exception:
        pass
    return out


def read_pages(rows, peek=False, click_out=False, cdp='http://127.0.0.1:9222', log=_say):
    """Network. One new tab in the job Chrome → [(row id, page record, classify result)]; stops at sign-in / challenge."""
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(cdp).contexts[0]
        pg = ctx.new_page(); pg.set_viewport_size({'width': 1300, 'height': 900})
        try:
            fails = 0
            for n, r in enumerate(rows):
                if n:
                    pg.wait_for_timeout(int(random.uniform(*SLEEP) * 1000))
                t0 = dt.datetime.now()
                try:
                    pg.goto(r['url'], wait_until='domcontentloaded', timeout=60000); pg.wait_for_timeout(4500)
                    rec = pg.evaluate(EXTRACT_JS)
                except Exception as e:
                    fails += 1; log(f"  {r['id']} page did not load ({type(e).__name__})")
                    if fails >= 3:
                        log('  3 pages in a row did not load — stopped'); break
                    continue
                fails = 0
                res = classify(rec)
                if peek and res['via'] == 'unknown' and 'needs --peek' in res['reason']:
                    try:
                        rec.update(_peek(pg, ctx, click_out))
                    except Exception as e:                   # recorded, the run goes on (the dialog is closed next page)
                        rec['peek_error'] = f'{type(e).__name__}: {str(e)[:200]}'
                    rec['peeked'] = True
                    res = classify(rec)
                rec['id'], rec['row_url'] = r['id'], r['url']
                rec['secs'] = round((dt.datetime.now() - t0).total_seconds(), 1)
                out.append((r['id'], rec, res))
                log(f"  {r['id']} {res['via']:<9} {r['company'][:22]:<22} | {res['reason'][:90]} | {rec['secs']} s")
                if res['via'] in ('blocked', 'signin'):
                    log(f"  stopped at {rec.get('url')} ({res['via']}) — nothing solved; sign in / clear it, then run again")
                    break
        finally:
            pg.close()
    return out


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    jobs = store.load('jobs')
    todo = targets(jobs, '--all-elig' in a, '--redo' in a)
    if '--ids' in a:                                         # exactly these rows, in this order (comparison runs)
        on_wf = {j['id']: j for j in jobs if wf_job_page(j.get('url'))}
        todo = [on_wf[x] for x in a[a.index('--ids') + 1].split(',') if x in on_wf]
    if '--click-out' in a and '--peek' not in a:
        print('--click-out works only together with --peek'); return 2
    if '--limit' in a:
        todo = todo[:int(a[a.index('--limit') + 1])]
    by_id = {j['id']: j for j in jobs}
    if '--json' in a or '--html' in a:
        if '--json' in a:
            recs = json.load(open(a[a.index('--json') + 1], encoding='utf-8'))
            recs = recs.get('pages', recs) if isinstance(recs, dict) else recs
        else:
            d = a[a.index('--html') + 1]
            recs = []
            for f in sorted(os.listdir(d)):
                if f.endswith('.html'):
                    jid = re.match(r'(\d+)', f)
                    row = next((r for r in todo if jid and job_id(r['url']) == jid.group(1)), None)
                    recs.append({**page_from_html(open(os.path.join(d, f), encoding='utf-8', errors='replace').read(),
                                                  row['url'] if row else ''), 'id': row['id'] if row else ''})
        wanted = {job_id(r['url']): r['id'] for r in todo}
        results = []
        for rec in recs:
            rid = rec.get('id') or wanted.get(job_id(rec.get('row_url') or rec.get('url')), '')
            if rid in by_id:
                results.append((rid, rec, classify(rec)))
        print(f'{len(recs)} saved pages · {len(results)} matched to store rows')
    else:
        print(f'{len(todo)} Wellfound rows to read (job Chrome, one tab, {SLEEP[0]}–{SLEEP[1]} s apart'
              f'{", --peek" if "--peek" in a else ""}{", --click-out" if "--click-out" in a else ""})', flush=True)
        results = read_pages(todo, peek='--peek' in a, click_out='--click-out' in a)
        if '--save' in a:
            json.dump({'pages': [rec for _, rec, _ in results]}, open(a[a.index('--save') + 1], 'w', encoding='utf-8'), indent=1)
    c = Counter(res['via'] for _, _, res in results)
    plats = Counter(platform_of(res['ats_url']) or 'company site' for _, _, res in results if res['ats_url'])
    print('apply_via: ' + ' · '.join(f'{k} {v}' for k, v in c.most_common()) + (
        '  |  ats_url by platform: ' + ' · '.join(f'{k} {v}' for k, v in plats.most_common()) if plats else ''))
    if '--write' not in a:
        if '--json' in a or '--html' in a:
            for rid, _, res in results:
                print(f"  {rid} {res['via']:<9} {by_id[rid]['company'][:22]:<22} | {res['reason'][:90]}")
        return 0
    today = dt.date.today().isoformat()
    n = sum(1 for rid, _, res in results if res['via'] not in ('blocked', 'signin') and apply_result(by_id[rid], res, today))
    store.save('jobs', jobs)
    print(f"written: {n} rows (apply_via), {sum(1 for _, _, r in results if r['ats_url'])} ats_url — the 08:45 gate re-reads them")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
