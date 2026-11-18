#!/usr/bin/env python3
"""Closed postings are written back to the store (JSA-417; spec scripts/test_cases/job_closed_spec.md).

Until 2026-11-17 a posting found closed by the form prefetch / prepare / a runner stayed 可投 in data/store/jobs.jsonl (only the weekly
gate re-read changed it), so a batch picked from the store was mostly dead postings. This is the one place that

  - judges a Greenhouse / Lever / Ashby posting open | closed | unknown from the public job-board API (check_job),
  - marks the store row 已关闭 (mark_store / mark_many — the row stays; elig_closed {at, why, source}),
  - screens a batch list before it is prepared (screen): closed jobs are dropped and marked.

Only a 404 / 410 (Greenhouse) or a valid non-empty Lever / Ashby board that lacks the job counts as closed. A 403 (the sandbox
gets one from Ashby), 429, 5xx, a timeout, a bad body → "unknown": the job stays, nothing is marked.

    python3 scripts/store/job_closed.py --sweep [--mark] [--limit N]    every 可投 Greenhouse / Lever / Ashby row: still on its board?
    python3 scripts/store/job_closed.py --ids J001 J002 [--mark]         just these rows
Without --mark nothing is written. Tests (rule 13): scripts/store/test_job_closed.py.
"""
import datetime, json, os, re, sys, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

GH_HOSTS = ("boards-api.greenhouse.io", "boards-api.eu.greenhouse.io")
URLS = (("greenhouse", re.compile(r"greenhouse\.io/(?:embed/job_app\?for=([\w-]+)&token=(\d+)|([\w-]+)/jobs/(\d+))")),
        ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([\w.-]+)/([0-9a-f-]{36})")),
        ("ashby", re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})")))


def parse_url(url):
    """Pure. A posting link → (platform, org / board, job id) for Greenhouse / Lever / Ashby, else None."""
    from urllib.parse import unquote
    u = url or ""
    for plat, rx in URLS:
        m = rx.search(u)
        if m:
            g = [x for x in m.groups() if x]
            if plat == "lever" and "eu.lever.co" in u:
                plat = "lever_eu"
            return plat, unquote(g[0]), g[1]
    return None


def gh_verdict(statuses):
    """Pure. HTTP statuses of the Greenhouse job API on every host tried → open | closed | unknown."""
    if any(s == 200 for s in statuses):
        return "open"
    if statuses and all(s in (404, 410) for s in statuses):
        return "closed"
    return "unknown"


def board_verdict(status, body, job_id, platform):
    """Pure. A Lever / Ashby board response → open | closed | unknown (an unreadable or empty board says nothing)."""
    if status != 200:
        return "unknown"
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return "unknown"
    items = data.get("jobs") if platform == "ashby" and isinstance(data, dict) else data if platform != "ashby" else None
    if not isinstance(items, list) or not items:
        return "unknown"
    if any(isinstance(x, dict) and str(x.get("id")) == str(job_id) for x in items):
        return "open"
    return "closed"


ASHBY_Q = ("query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) { jobPosting("
           "organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) { id title } }")


def single_verdict(kind, plat, org, jid, get):
    """The posting's own public endpoint, asked after a board list lacked it → closed only on a clear "no such posting"
    (Lever single-posting API 404 / 410; Ashby's job-page GraphQL answering jobPosting null); else open / unknown."""
    if kind == "lever":
        host = "api.eu.lever.co" if plat == "lever_eu" else "api.lever.co"
        s = get(f"https://{host}/v0/postings/{org}/{jid}")[0]
        return "open" if s == 200 else "closed" if s in (404, 410) else "unknown"
    body = json.dumps({"operationName": "ApiJobPosting", "query": ASHBY_Q,
                       "variables": {"organizationHostedJobsPageName": org, "jobPostingId": jid}}).encode()
    s, t, _ = get("https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting", data=body, headers={"content-type": "application/json"})
    if s != 200:
        return "unknown"
    try:
        d = json.loads(t)
    except ValueError:
        return "unknown"
    if not isinstance(d, dict) or d.get("errors") or not isinstance(d.get("data"), dict) or "jobPosting" not in d["data"]:
        return "unknown"
    return "open" if d["data"]["jobPosting"] else "closed"


def mark_closed_row(row, why, source, today):
    """Pure-ish (mutates `row`). Mark one store row 已关闭; True when it changed. 已关闭 / 不可投 / 重复 rows stay as they are."""
    if row.get("elig") in ("已关闭", "不可投", "重复"):
        return False
    why = str(why or "")[:200]
    row.update(elig="已关闭", elig_base="已关闭", elig_checked=today,
               elig_reason=f"岗位已关闭（{today}，{source}）：{why}",
               elig_closed={"at": today, "why": why, "source": source})
    if "tier_orig" not in row:
        row["tier_orig"] = row.get("tier")
    row["tier"] = "Blocked"
    return True


def mark_many(items, source, today=None, store=None):
    """items: [(job_id, why)] → the store rows marked (one load / save). Returns the ids that changed."""
    if not items:
        return []
    if store is None:
        import store as _store  # noqa: E402
        store = _store
    today = today or datetime.date.today().isoformat()
    why = dict(items)
    rows = store.load("jobs")
    changed = [r["id"] for r in rows if r.get("id") in why and mark_closed_row(r, why[r["id"]], source, today)]
    if changed:
        store.save("jobs", rows)
    return changed


def mark_store(job_id, why, source, today=None, store=None):
    """One job → 已关闭 in the store (form_prefetch / prepare / runner call this). True when a row changed; never raises."""
    try:
        return bool(mark_many([(job_id, why)], source, today, store))
    except Exception:  # noqa: BLE001 — a data write never fails the run that found the closed posting
        return False


# ---------------------------------------------------------------- the public APIs
_cache, _lock = {}, threading.Lock()


def _get(url, **kw):
    sys.path.insert(0, os.path.join(ROOT, "skills", "job-hunt-pipeline", "scripts"))
    import eligibility_fetch as EF
    return EF.get(url, **kw)


def check_job(job, get=None):
    """One store / batch row → (open | closed | unknown, why). Greenhouse / Lever / Ashby only; anything else is unknown."""
    get = get or _get
    p = parse_url(job.get("ats_url") or job.get("url"))
    if not p:
        return "unknown", "not a Greenhouse / Lever / Ashby link"
    plat, org, jid = p
    if plat == "greenhouse":
        st = [get(f"https://{GH_HOSTS[0]}/v1/boards/{org}/jobs/{jid}")[0]]
        # a board lives on one host: the US host knowing the board (200) and not the job (404) settles it — the EU host is
        # often unreachable (a network error must not turn a gone posting into "unknown")
        if st[0] in (404, 410) and get(f"https://{GH_HOSTS[0]}/v1/boards/{org}")[0] == 200:
            pass
        elif st[0] != 200:
            st.append(get(f"https://{GH_HOSTS[1]}/v1/boards/{org}/jobs/{jid}")[0])
        v = gh_verdict(st)
        return v, ("Greenhouse 404 (posting removed)" if v == "closed" else f"Greenhouse HTTP {st}" if v == "unknown" else "")
    if plat == "ashby":
        url, kind = f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=false", "ashby"
    else:
        url, kind = f"https://{'api.eu.lever.co' if plat == 'lever_eu' else 'api.lever.co'}/v0/postings/{org}?mode=json", "lever"
    with _lock:
        hit = _cache.get(url)
    if hit is None:
        hit = get(url)
        if hit[0] == 200:
            with _lock:
                _cache[url] = hit
    v = board_verdict(hit[0], hit[1], jid, kind)
    if v == "closed":               # absent from the LIST is not yet closed: an unlisted posting can still take applications
        v = single_verdict(kind, plat, org, jid, get)
    return v, (f"no longer on the {kind.title()} board" if v == "closed" else f"{kind.title()} board HTTP {hit[0]}" if v == "unknown" else "")


def confirm_mark(job, why, source, today=None, check=None, load=None):
    """A prefetch / prepare step suspects the posting is closed → ask the public API once more, mark the store only when it
    agrees. Greenhouse / Lever / Ashby: check_job must say closed (the form readers also raise on API errors). Other ATS:
    eligibility_fetch.load must say closed (404 / 410 / removed — the gate's own readers). Returns the marked text or ''."""
    check = check or check_job
    if parse_url(job.get("ats_url") or job.get("url")):
        v, w = check(job)
    else:
        try:
            if load is None:
                sys.path.insert(0, os.path.join(ROOT, "skills", "job-hunt-pipeline", "scripts"))
                import eligibility_fetch as EF
                load = EF.load
            d = load(job.get("ats_url") or job.get("url")) or {}
        except Exception:  # noqa: BLE001
            return ""
        v, w = ("closed", d.get("why") or why) if d.get("status") == "closed" else ("unknown", "")
    if v != "closed":
        return ""
    return w if mark_store(job["id"], w or why, source, today) else ""


def screen(jobs, today=None, source="prepare", check=None, mark=True, workers=8, log=print):
    """Before a batch is prepared: → (jobs still worth preparing, the closed ones as [{id, company, why}]). Closed jobs are
    marked 已关闭 in the store (mark=False: only reported). unknown (network error, 403 …) keeps the job."""
    check = check or check_job
    today = today or datetime.date.today().isoformat()

    def one(j):
        try:
            return check(j)
        except Exception as e:  # noqa: BLE001
            return "unknown", f"{type(e).__name__}: {str(e)[:80]}"
    with ThreadPoolExecutor(max(1, workers)) as ex:
        res = list(ex.map(one, jobs))
    keep, dropped = [], []
    for j, (v, why) in zip(jobs, res):
        if v == "closed":
            dropped.append({"id": j.get("id"), "company": j.get("company"), "why": why})
        else:
            keep.append(j)
    note = "" if mark else " (not marked)"
    if dropped and mark:
        try:
            mark_many([(d["id"], d["why"]) for d in dropped], source, today)
        except Exception as e:  # noqa: BLE001 — the closed jobs are still dropped from this batch
            note = f" (store not updated: {type(e).__name__}: {str(e)[:80]})"
    for d in dropped:
        log(f"  ✗ {d.get('company')} ({d['id']}): closed — {d['why']}{note}")
    return keep, dropped


def main(a):
    import store
    rows = [r for r in store.load("jobs") if parse_url(r.get("ats_url") or r.get("url"))]
    if "--ids" in a:
        want = set(x for x in a[a.index("--ids") + 1:] if not x.startswith("--"))
        rows = [r for r in rows if r["id"] in want]
    elif "--sweep" in a:
        rows = [r for r in rows if r.get("elig") == "可投"]
        if "--limit" in a:
            rows = rows[:int(a[a.index("--limit") + 1])]
    else:
        print(__doc__); return 2
    keep, dropped = screen(rows, source="sweep", mark="--mark" in a)
    print(f"checked {len(rows)} · closed {len(dropped)} · open or unknown {len(keep)}" + ("" if "--mark" in a else " · nothing written (--mark)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
