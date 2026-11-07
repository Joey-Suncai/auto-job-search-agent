"""Local daily routines (ADR-0004, JSA-028) — replaces the claude.ai 08:15 / 08:45 scheduled tasks.

  refresh  (08:15)  append_new.py against the 13 curated GitHub lists — append only; then board_search.py adds new
                    Lever / Ashby internships from every board in the store + references/extra_boards.txt (JSA-076)
  gate     (08:45)  gate_run.py eligibility check (rows never checked / older than 7 days / transient fails; --all on Sundays)

Each stage works on a temp copy, checks the result, and only then saves data/store/jobs.jsonl, commits that path alone
and pushes. Any failure leaves the store untouched and pushes a "失败" message. Log: data/runner/daily/<date>.md.

usage: python3 scripts/daily/run_daily.py refresh|gate [--no-git] [--no-notify] [--all]
"""
import datetime, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
PIPE = os.path.join(ROOT, "skills", "job-hunt-pipeline", "scripts")
sys.path.insert(0, os.path.join(ROOT, "scripts", "store"))
sys.path.insert(0, HERE)
import store  # noqa: E402
from notify import notify  # noqa: E402

ENV = dict(os.environ, PATH=":".join([os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin",
                                      "/usr/bin", "/bin", os.environ.get("PATH", "")]))
TODAY = datetime.date.today().isoformat()
LOG = jpaths.data("runner", "daily", f"{TODAY}.md")


def log(line):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    stamp = time.strftime("%H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"- {stamp} {line}\n")
    print(f"{stamp} {line}", flush=True)


def run(cmd, timeout):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV, cwd=ROOT)
    if p.returncode:
        raise RuntimeError(f"{os.path.basename(cmd[2] if cmd[1] == '-I' else cmd[1])} exit {p.returncode}: "
                           f"{(p.stderr or p.stdout).strip()[-400:]}")
    return p.stdout


def append_only(prev, new):
    """The refresh must keep every old row exactly (rank aside) and only add rows."""
    old = {j["id"]: j for j in prev}
    got = {j["id"]: j for j in new}
    missing = [i for i in old if i not in got]
    changed = [i for i in old if i in got and {k: v for k, v in got[i].items() if k != "rank"}
               != {k: v for k, v in old[i].items() if k != "rank"}]
    return missing, changed


def stage_refresh(work):
    prev = store.load("jobs")
    os.makedirs(f"{work}/prev"); os.makedirs(f"{work}/raw")
    json.dump(prev, open(f"{work}/prev/dash_jobs_prev.json", "w"), ensure_ascii=False)
    perm = jpaths.data("processed", "perm_ellis.txt")   # public PERM sponsor list (optional; JSA-079)
    if os.path.exists(perm):
        shutil.copy(perm, f"{work}/raw/perm_ellis.txt")
    run([sys.executable, "-I", os.path.join(PIPE, "append_new.py"), work], timeout=1800)
    new = json.load(open(f"{work}/out/dash_jobs.json"))
    s = json.load(open(f"{work}/out/refresh_summary.json"))
    missing, changed = append_only(prev, new)
    if missing or changed or len(new) < len(prev):   # (the old 3,000-row floor broke a new user's first run, JSA-079)
        raise RuntimeError(f"sanity: rows {len(prev)}→{len(new)}, missing {len(missing)}, changed {len(changed)}")
    added, board_line = board_rows(new)
    new = new + added
    RAN.update(github_ok=not s["clone_failures"], boards_ok=board_line != "failed")
    lines = [f"共 {len(new)} 个岗位，新增 {s['new_roles']} 个，其中 A/B 实习 {s['new_ab_internships']} 个。"]
    if added:
        lines.append(f"Lever / Ashby 招聘页新增实习 {len(added)} 个（08:45 核验）：")
        lines += [f"· {j['tier']} {j['company']} — {j['title'][:60]}" for j in added[:5]]
    for j in s["top_new"][:8]:
        lines.append(f"· {j['score']} {j['tier']} {j['company']} — {j['title'][:60]}（{j['sponsorship']}）")
    if s["clone_failures"]:
        lines.append("GitHub 列表抓取失败：" + ", ".join(s["clone_failures"]))
    return new, s["new_roles"] + len(added), f"+{s['new_roles']} rows, +{len(added)} boards", "\n".join(lines)


RAN = {}   # what the refresh ran successfully today → Sources table (JSA-095)


def save_sources(jobs):
    """Sources table: in_dashboard counts, last_run for the lists / boards that ran, rows for new labels. True = changed."""
    sys.path.insert(0, os.path.join(ROOT, "scripts", "store"))
    import complete_jobs
    old = store.load("sources")
    new = complete_jobs.update_sources(old, jobs, TODAY, RAN.get("github_ok", False), RAN.get("boards_ok", False))
    if new == sorted(old, key=lambda r: r["source"]):
        return False
    store.save("sources", new)
    log(f"sources: {len(new)} rows updated")
    return True


def board_rows(rows):
    """JSA-076 (Joey 2026-11-02 「加进去」): new Lever / Ashby internships from their public board APIs, appended after
    the append-only check. Only adds rows (ids after the last one); a failure is logged and never blocks the refresh."""
    try:
        sys.path.insert(0, PIPE)
        import board_search
        added, line = board_search.search(rows, os.path.join(ROOT, "skills", "job-hunt-pipeline", "references", "extra_boards.txt"))
        ids = {j["id"] for j in rows}
        if any(j["id"] in ids for j in added):
            raise RuntimeError("board rows reuse an existing id")
        log("board_search: " + line)
        return added, line
    except Exception as e:
        log(f"board_search failed ({type(e).__name__}: {str(e)[:120]}) — refresh keeps the GitHub rows only")
        return [], "failed"


def stage_gate(work, full):
    try:  # JSA-046: new aggregator rows → the company's own posting before the gate reads them; never blocks the gate
        out = run([sys.executable, "-I", os.path.join(PIPE, "resolve_aggregator.py"), "--all", "--write"], timeout=900)
        log("resolve_aggregator: " + (out.strip().splitlines() or ["nothing to resolve"])[-1])
    except Exception as e:
        log(f"resolve_aggregator failed ({type(e).__name__}: {str(e)[:120]}) — gate runs on the old links")
    prev = store.load("jobs")
    src, out = f"{work}/prev.json", f"{work}/dash_jobs_gated.json"
    json.dump(prev, open(src, "w"), ensure_ascii=False)
    run([sys.executable, "-I", os.path.join(PIPE, "gate_run.py"), src, out] + (["--all"] if full else []), timeout=3600)
    new = json.load(open(out))
    s = json.load(open(f"{work}/gate_summary.json"))
    if {j["id"] for j in new} != {j["id"] for j in prev}:
        raise RuntimeError(f"sanity: gate changed the row set ({len(prev)}→{len(new)})")
    keep_jds(f"{out}.jds.jsonl")
    v = s["verdicts"]
    lines = [f"核验 {s['checked']} 行（{s['seconds']} 秒）。可投 {v.get('可投', 0)} · 待核实 {v.get('待核实', 0)} · "
             f"不可投 {v.get('不可投', 0)} · 已关闭 {v.get('已关闭', 0)} · 重复 {v.get('重复', 0)}",
             f"新的可投实习 {s['new_eligible_internships_total']} 个："]
    for j in s["new_eligible_internships"][:8]:
        lines.append(f"· {j['score']} {j['company']} — {j['title'][:60]}（{j['location']}）")
    sr = s.get("second_read") or {}   # JSA-231 phase 2: DeepSeek re-read of soft verdicts (+ Sunday audit sample)
    if sr.get("read") is not None:
        lines.append(f"DeepSeek 复读 {sr['read']} 行：软理由不可投 → 待核实 {sr['to_review']}，确认 {sr['confirmed']}"
                     + (f"，超出上限待下次 {sr['skipped_cap']}" if sr.get("skipped_cap") else ""))
    if sr.get("audit_report"):
        n = sum(v["disagree"] for v in sr.get("audit", {}).values())
        lines.append(f"每周抽查：硬理由样本 {sum(v['sampled'] for v in sr['audit'].values())} 行，DeepSeek 不同意 {n} 行 → {sr['audit_report']}")
    elif sr.get("error"):
        lines.append(f"DeepSeek 复读失败（{sr['error'][:80]}），本次只用规则")
    return new, s["checked"], f"{s['checked']} checked", "\n".join(lines)


def keep_jds(path, days=21):
    """Keep the JD text the gate just fetched (data/processed/jds_gate_<date>.jsonl, git-ignored) so prefilter.py ranks
    new rows on fresh text instead of a stale cache (JSA-033 follow-up, 2026-10-30); drop gate copies older than `days`."""
    if not os.path.exists(path) or not os.path.getsize(path):
        return
    d = jpaths.data("processed")
    os.makedirs(d, exist_ok=True)
    shutil.copyfile(path, os.path.join(d, f"jds_gate_{TODAY}.jsonl"))
    cut = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    for f in os.listdir(d):
        if f.startswith("jds_gate_") and f[9:19] < cut:
            os.remove(os.path.join(d, f))


def git_publish(subject):
    g = lambda *a: subprocess.run(["git", "-C", jpaths.home(), *a], capture_output=True, text=True, env=ENV)   # the data home's git (= this repo until JSA_HOME is set)
    if not g("status", "--porcelain", "--", "data/store").stdout.strip():
        return "nothing to commit"
    c = g("commit", "-q", "-m", subject, "--", "data/store")
    if c.returncode:
        raise RuntimeError("git commit: " + c.stderr.strip()[-300:])
    if g("push", "-q").returncode == 0:
        return "pushed"
    # remote moved (a worktree session pushed): rebase only when the tree is clean, never touch open work
    if not g("status", "--porcelain").stdout.strip() and g("pull", "-q", "--rebase").returncode == 0 \
            and g("push", "-q").returncode == 0:
        return "rebased and pushed"
    return "committed locally; push pending (remote ahead and the working tree is not clean)"


def main(a):
    stage = a[0] if a and a[0] in ("refresh", "gate") else None
    if not stage:
        print(__doc__); return 2
    full = "--all" in a or (stage == "gate" and datetime.date.today().weekday() == 6)
    title = {"refresh": "每日岗位刷新", "gate": "可投核验"}[stage]
    t0 = time.time()
    log(f"{stage} start (code {subprocess.run(['git', '-C', ROOT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()})")
    work = tempfile.mkdtemp(prefix=f"jobagent_{stage}_")
    try:
        new, n, short, report = stage_refresh(work) if stage == "refresh" else stage_gate(work, full)
        if n:
            store.save("jobs", new)
        src_changed = stage == "refresh" and save_sources(store.load("jobs"))
        pub = "skipped" if "--no-git" in a or not (n or src_changed) else git_publish(f"data: {stage} {TODAY} ({short})")
        log(f"{stage} ok in {round(time.time() - t0)} s · {short} · git: {pub}")
        if "--no-notify" not in a:
            notify(f"{title} {TODAY}", report + ("" if pub in ("pushed", "rebased and pushed", "skipped", "nothing to commit") else f"\n⚠ git: {pub}"))
        return 0
    except Exception as e:
        log(f"{stage} FAILED: {e}")
        if "--no-notify" not in a:
            notify(f"{title}失败 {TODAY}", f"{str(e)[:300]}\n数据未改动。日志：data/runner/daily/{TODAY}.md")
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
