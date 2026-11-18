#!/usr/bin/env python3
"""Eligibility gate, fallback reader (JSA-284): the rendered text of a company job page, read in the job Chrome.

Some career sites load the job text by script (ADP Workforce Now, UltiPro, Avature, ClearCompany, BambooHR, Taleo,
SuccessFactors' new template, tiktokusds, Workday postings whose JSON is refused …), so the gate's plain download
(eligibility_fetch.load) finds no job text. For rows that have the company's own link (ats_url) and came back
unreadable, gate_run.py hands this script a short list; it opens each page in ONE tab of its own in the job Chrome
(CDP 9222), waits for the page to settle, reads document.body.innerText and judges it with page_verdict() — the
eligibility rules then read that text like any other JD.

Safety (Joey 2026-11-10): pages are only loaded — nothing is clicked, typed, signed in or solved. A
CAPTCHA or a security check stops the whole run at once (the rest stay unreadable); a sign-in page leaves only that row
unreadable ("needs a login"). Only the tab this script opened
is closed; other sessions' tabs are never touched. It takes the job-Chrome lock (chrome_lock.py) with a short wait and
gives up when a runner holds it. A cap (--max) and a pause between pages keep it polite; a time budget ends the run.
No Chrome / no Playwright / no lock → exit code 3 and an empty result: the gate goes on without it.

  ~/.job-agent-venv/bin/python gate_render.py in.json out.json [--max 40] [--pause 3 6] [--budget 600] [--cdp URL]
  in.json = [{"id", "url"}, …]   out.json = {id: {"status", "why", "title", "text", "final_url"}, "_stopped": why?}
"""
import json, os, random, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))

CHECK = re.compile(r"verify (that )?you are (a )?human|are you a robot|captcha|security check|unusual (activity|traffic)|"
                   r"press (and|&) hold|checking your browser|just a moment\.\.\.|access denied|request blocked|"
                   r"attention required|bot detection|pardon our interruption", re.I)
SIGNIN_URL = re.compile(r"/(login|signin|sign-in|sso|auth|oauth2?|saml|account/login)(\b|/|\?)|accounts\.google\.com|"
                        r"login\.microsoftonline\.com|okta\.com", re.I)
SIGNIN_TXT = re.compile(r"^\s*(sign in|log ?in)\b|please (sign|log) ?in to (view|continue|apply)|you must (sign|log) ?in", re.I | re.M)
CLOSED = re.compile(r"no longer (available|accepting|active|open|posted)|(position|job|requisition|posting) (has been|was) "
                    r"(filled|closed|removed|cancel+ed)|job (is )?not found|job (posting )?(has )?expired|this (job|position|"
                    r"posting|opportunity) (is )?(closed|unavailable|no longer)|page (you are looking for|you requested) "
                    r"(doesn.t|does not|could not|cannot|can.t)|page (doesn.t|does not) exist|(404|page) not found|"
                    r"job (you are|you're) (looking for|trying to) .{0,40}(not|no longer)|"
                    r"opportunity (is )?no longer|not accepting applications|(job|position|posting|opportunity|requisition) is (currently )?"
                    r"(not available|unavailable)|(can.t|cannot) view this (job|position|posting|requisition) because", re.I)   # last: Seagate RMK, JSA-300
SITE_ERR = re.compile(r"problem with the service|(please )?try again (later|after some ?time)|trouble loading the (job|page|posting)|"
                      r"something went wrong|service (is )?(temporarily )?unavailable", re.I)   # JSA-300: the site failed, not a login / closed
JOBWORD = re.compile(r"responsibilit|qualification|requirement|what you.ll do|about (the|this) (role|job|position)|"
                     r"job description|duties|you will|skills|experience|degree", re.I)
CLOSED_ON = re.compile(r"(?:^|\n|\|)\s*(?:closed|closing date|close date|application deadline|apply by|已关闭|截止日期)\s*[:：]?\s*"
                       r"(?:on\s+)?([A-Z][a-z]{2,8}\.? \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", re.I)
MIN_TEXT = 600         # characters of page text below which a page is not a job description
MAX_TEXT = 40000


def closed_on(text, today):
    """Pure (tested). The first "Closed: <date>" / "Closing date <date>" / "Application deadline: <date>" line (English or
    the Chinese labels the job Chrome's locale shows) → that date as YYYY-MM-DD, when it is before `today` (YYYY-MM-DD);
    else None. Dates: "November 5, 2026", "Nov 5 2026", "2026-11-05", "11/05/2026" (US month/day)."""
    import datetime as dt
    for m in CLOSED_ON.finditer((text or "")[:6000]):
        d, v = m.group(1).replace(".", "").replace(",", ""), None
        for f in ("%B %d %Y", "%b %d %Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                v = dt.datetime.strptime(d, f).date().isoformat(); break
            except ValueError:
                pass
        if v:
            return v if v < today else None
    return None


def page_verdict(url, final_url, title, text, http=200, today=None):
    """Pure (tested, scripts/test_gate_render.py). What one rendered page showed → {"status", "why", "text"?, "title"?}.
    "stop" (a security check / CAPTCHA: the run ends here, nothing is solved) · "login" (a sign-in page: this row
    stays unreadable as "needs a login", the run goes on; nothing is signed in) · "closed" (HTTP 404/410, a closed-posting
    notice near the top of a page that has little job text, or a "Closed: <date>" line with a past date — closed_on) · "unreadable" (too little text to be a job description,
    HTTP 4xx/5xx, or a short page whose notice says the site itself failed — "problem with the service", "try again later" —
    checked before the sign-in test because such pages keep a "Sign in" link at the top; JSA-300) · "ok" (the page text, cut to MAX_TEXT, with the page title)."""
    text = re.sub(r"[ \t\r\f\v]+", " ", text or "").strip()
    text = re.sub(r"\n\s*\n+", "\n", text)
    head, ttl = text[:2500], (title or "").strip()
    if CHECK.search(ttl) or (len(text) < 2500 and CHECK.search(head)):
        return dict(status="stop", why=f"security check / CAPTCHA at {(final_url or url)[:140]}")
    if SIGNIN_URL.search(final_url or "") and not SIGNIN_URL.search(url or ""):
        return dict(status="login", why=f"needs a login: sign-in page at {(final_url or '')[:140]}")
    if http in (404, 410):
        return dict(status="closed", why=f"rendered page {http}")
    jobby = len(JOBWORD.findall(text[:20000]))
    if CLOSED.search(head) and (len(text) < 3000 or jobby < 3):
        m = CLOSED.search(head)
        return dict(status="closed", why=f"rendered page: '{m.group(0)[:60]}'")
    if len(text) < 1500 and SITE_ERR.search(head):   # JSA-300: ADP myjobs shows a "Sign in" nav line above its error notice
        return dict(status="unreadable", why=f"rendered page: site error '{SITE_ERR.search(head).group(0)[:60]}'")
    if len(text) < 1500 and SIGNIN_TXT.search(head):
        return dict(status="login", why=f"needs a login: sign-in page at {(final_url or url)[:140]}")
    past = closed_on(text, today or time.strftime("%Y-%m-%d"))
    if past:
        return dict(status="closed", why=f"rendered page: closed on {past}")
    if http and http >= 400:
        return dict(status="unreadable", why=f"rendered page {http}")
    if len(text) < MIN_TEXT or jobby < 2:
        return dict(status="unreadable", why=f"rendered page has no job text ({len(text)} chars)")
    return dict(status="ok", why="rendered in the job Chrome (JSA-284)", title=ttl[:200], text=text[:MAX_TEXT])


def render(items, cdp="http://127.0.0.1:9222", cap=40, pause=(3, 6), budget=600, log=print):
    """items [{"id", "url"}] → {id: verdict + final_url}; "_stopped" holds the reason when a check / sign-in ended it."""
    from playwright.sync_api import sync_playwright
    out, t_end = {}, time.time() + budget
    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp(cdp, timeout=15000)
        ctx = br.contexts[0] if br.contexts else br.new_context()
        pg = ctx.new_page()                                   # our own tab: the only one this script ever closes
        try:   # the job Chrome runs in a Chinese locale; this tab alone reads pages in US English
            cs = ctx.new_cdp_session(pg)
            cs.send("Emulation.setLocaleOverride", {"locale": "en-US"})
            pg.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
        except Exception:
            pass
        try:
            for n, it in enumerate(items[:cap]):
                if time.time() > t_end:
                    out["_stopped"] = f"time budget {budget} s used after {n} pages"
                    break
                if n:
                    time.sleep(random.uniform(*pause))
                t0, http = time.time(), 0
                try:
                    r = pg.goto(it["url"], wait_until="domcontentloaded", timeout=45000)
                    http = r.status if r else 0
                    try:
                        pg.wait_for_load_state("networkidle", timeout=12000)
                    except Exception:
                        pass
                    pg.wait_for_timeout(2500)
                    text = pg.inner_text("body", timeout=10000)
                    if len(text) < MIN_TEXT:                  # late script: one more wait
                        pg.wait_for_timeout(5000)
                        text = pg.inner_text("body", timeout=10000)
                    v = page_verdict(it["url"], pg.url, pg.title(), text, http)
                except Exception as e:
                    v = dict(status="unreadable", why=f"rendered page error {type(e).__name__}: {str(e)[:80]}")
                v["final_url"] = pg.url[:300]
                log(f"  {it['id']} {v['status']:10} {round(time.time() - t0, 1):5}s | {v['why'][:80]} | {it['url'][:90]}", flush=True)
                if v["status"] == "stop":
                    out["_stopped"] = v["why"]
                    break
                if v["status"] == "login":
                    v["status"] = "unreadable"
                out[it["id"]] = v
        finally:
            try:
                pg.close()
            except Exception:
                pass
    return out


def main(a):
    src, dst = a[0], a[1]
    cap = int(a[a.index("--max") + 1]) if "--max" in a else 40
    pause = (float(a[a.index("--pause") + 1]), float(a[a.index("--pause") + 2])) if "--pause" in a else (3, 6)
    budget = float(a[a.index("--budget") + 1]) if "--budget" in a else 600
    cdp = a[a.index("--cdp") + 1] if "--cdp" in a else os.environ.get("CX_CDP", "http://127.0.0.1:9222")
    items = json.load(open(src))
    json.dump({}, open(dst, "w"))
    try:
        import urllib.request
        urllib.request.urlopen(cdp.rstrip("/") + "/json/version", timeout=4).read()
    except Exception as e:
        print(f"job Chrome not reachable at {cdp} ({type(e).__name__}) — skipped", flush=True)
        sys.exit(3)
    sys.path.insert(0, os.path.join(HERE, "..", "..", "auto-apply", "runner"))
    os.environ.setdefault("JSA_CHROME_LOCK_WAIT", "60")
    import chrome_lock
    chrome_lock.hold("gate_render.py (eligibility gate)")      # exits 3 (chrome-busy) when a runner holds the browser
    out = render(items, cdp, cap, pause, budget)
    json.dump(out, open(dst, "w"), ensure_ascii=False)
    from collections import Counter
    print("rendered", dict(Counter(v["status"] for k, v in out.items() if k != "_stopped")),
          ("STOPPED: " + out["_stopped"]) if "_stopped" in out else "", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
