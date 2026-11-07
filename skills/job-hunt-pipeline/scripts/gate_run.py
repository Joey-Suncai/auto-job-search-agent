#!/usr/bin/env python3
"""Eligibility gate, one command: pick the rows that need a check, fetch their JDs, classify, merge, dedupe.

Usage: python3 -I gate_run.py dash_jobs_prev.json dash_jobs_gated.json [--all] [--days 7] [--workers 16] [--ds-max N]
  default: rows never checked, rows whose last check is older than --days, and rows whose last fetch failed transiently
  --all:   every row (weekly full refresh) + the weekly audit sample (gate_second_read.weekly_audit)
  --ds-max: new DeepSeek second reads this run (JSA-231 phase 2; default 400, 1000 with --all; 0 = rules only)
Writes the gated jobs file plus gate_summary.json next to it (counts + new 可投 internships), prints the summary.
Needs: python3, node, and network access to the job-board hosts (see SKILL.md §5). Exits 2 if the boards are blocked.
"""
import datetime, importlib.util, json, os, re, subprocess, sys, time
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))


def mod(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m



def read(j, load):
    """Pure (tested, scripts/test_gate_read.py): the company's own posting first (ats_url, JSA-004 / JSA-046); when it
    cannot be read, the original link — a broken resolved link never costs a verdict the old link could still give."""
    x = load(j.get("ats_url") or j.get("url"))
    if x.get("status") == "unreadable" and j.get("ats_url") and j.get("url") and j["url"] != j["ats_url"]:
        y = load(j["url"])
        if y.get("status") != "unreadable":
            return y
    return x

def second_read(jds_p, res_p, ds_max, full, today, rows):
    """JSA-231 phase 2: DeepSeek re-reads the soft verdicts (gate_second_read.py) and, on the --all run, a sample of the
    hard ones (report in data/runner/daily/gate_audit_<date>.md). Never blocks the gate: any failure = rules only."""
    if ds_max <= 0:
        return {"skipped": "--ds-max 0"}
    try:
        sr = mod("gate_second_read")
        import paths as jpaths  # noqa: E402  (config/ is on sys.path after gate_second_read loads)
        jds = {}
        for line in open(jds_p, encoding="utf-8"):
            if line.strip():
                x = json.loads(line)
                if x.get("status") == "ok":
                    jds[x["id"]] = x
        res = json.load(open(res_p))
        reader = sr.default_reader()
        res, stats = sr.apply(res, jds, reader, ds_max=ds_max, score={i: j.get("score") for i, j in rows.items()})
        json.dump(res, open(res_p, "w"), ensure_ascii=False)
        if full:
            md = jpaths.data("runner", "daily", f"gate_audit_{today}.md")
            stats["audit"] = sr.weekly_audit(res, jds, reader, md, titles={i: j.get("title") for i, j in rows.items()})
            stats["audit_report"] = md
            stats["usage"] = dict(reader.usage)
        print("second read: " + json.dumps(stats, ensure_ascii=False), file=sys.stderr, flush=True)
        return stats
    except Exception as e:
        print(f"second read failed ({type(e).__name__}: {str(e)[:160]}) — rules-only verdicts", file=sys.stderr, flush=True)
        return {"error": f"{type(e).__name__}: {str(e)[:160]}"}


def main():
    a = sys.argv[1:]
    src, out = a[0], a[1]
    full = "--all" in a
    days = int(a[a.index("--days") + 1]) if "--days" in a else 7
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 16
    today = datetime.date.today().isoformat()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    ef, em = mod("eligibility_fetch"), mod("eligibility_merge")

    s, _, _ = ef.get("https://boards-api.greenhouse.io/v1/boards/anthropic/jobs", tries=1)
    if s == 0:
        print(json.dumps({"error": "job boards blocked: boards-api.greenhouse.io unreachable from this machine"}))
        sys.exit(2)

    jobs = json.load(open(src))
    before = {j["id"]: j.get("elig") for j in jobs}

    def due(j):
        if full or not j.get("elig_checked") or j["elig_checked"] < cutoff:
            return True
        if j.get("ats_url") and (j.get("ats_resolved_on") or "") >= j["elig_checked"]:  # JSA-046: link resolved since the last check
            return True
        # daily retry only for transient failures (rate limit, server error, network hiccup); sites the environment
        # can't reach, pages without JD data, logins and Jobright wait for the weekly re-check
        ev = j.get("elig_evidence") or ""
        unreadable = j.get("elig_base", j.get("elig")) == "待核实" and "UNREADABLE" in (j.get("elig_codes") or "")
        if unreadable and (j.get("elig_reader") or 1) < ef.READER_VERSION:  # a new site reader exists since the last try
            return True
        return unreadable and re.search(r"page (429|5\d\d)|Workday (429|5\d\d)|board (429|5\d\d)|error ", ev) is not None

    todo = [j for j in jobs if due(j)]
    print(f"{len(todo)} of {len(jobs)} roles to check", file=sys.stderr, flush=True)
    t0 = time.time()
    tmp = out + ".jds.jsonl"
    with cf.ThreadPoolExecutor(workers) as ex, open(tmp, "w") as fh:
        futs = {ex.submit(read, j, ef.load): j for j in todo}
        for f in cf.as_completed(futs):
            j = futs[f]
            try:
                x = f.result()
            except Exception as e:
                x = dict(status="unreadable", key="url:" + (j.get("ats_url") or j.get("url") or ""), why="error " + str(e)[:80])
            fh.write(json.dumps({"id": j["id"], "level": j.get("level"), **x}, ensure_ascii=False) + "\n")
    res_p = out + ".results.json"
    subprocess.run(["node", os.path.join(HERE, "eligibility_classify.js"), tmp, res_p], check=True, stdout=sys.stderr)
    ds_max = int(a[a.index("--ds-max") + 1]) if "--ds-max" in a else (1000 if full else 400)
    ds_stats = second_read(tmp, res_p, ds_max, full, today, {j["id"]: j for j in todo})
    manual_conflicts = em.main(src, res_p, out, today) or []
    done_ids = {j["id"] for j in todo}
    gated = json.load(open(out))
    for j in gated:
        if j["id"] in done_ids:
            j["elig_reader"] = ef.READER_VERSION
    json.dump(gated, open(out, "w"), ensure_ascii=False)

    new_ok = [j for j in gated if j["level"] == "Internship" and j["elig"] == "可投" and before.get(j["id"]) != "可投"]
    new_ok.sort(key=lambda j: -(j.get("score") or 0))
    from collections import Counter
    summary = {
        "date": today, "checked": len(todo), "seconds": round(time.time() - t0),
        "rows": len(gated), "verdicts": dict(Counter(j["elig"] for j in gated)),
        "internships": dict(Counter(j["elig"] for j in gated if j["level"] == "Internship")),
        "new_eligible_internships": [{k: j.get(k) for k in ("id", "score", "tier", "company", "title", "track", "location", "sponsorship", "referral", "url")} for j in new_ok[:15]],
        "new_eligible_internships_total": len(new_ok),
        "manual_conflicts": manual_conflicts,
        "second_read": ds_stats,
    }
    json.dump(summary, open(os.path.join(os.path.dirname(os.path.abspath(out)), "gate_summary.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "new_eligible_internships"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
