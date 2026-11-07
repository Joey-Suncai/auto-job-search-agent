#!/usr/bin/env python3
"""Build map/index.html - an interactive, self-contained view of how this agent works.

    python3 scripts/map/build_map.py            # rebuild map/index.html (+ map/data.json)
    python3 scripts/map/build_map.py --check    # exit 0 if up to date, 1 if a rebuild is needed

Not part of the agent: it only reads the repo. The page reloads itself every 60 s, so an open tab follows the
files. Rebuild triggers: git HEAD / dirty state / file counts / key mtimes (see fingerprint()).
"""
import glob, argparse, hashlib, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
TPL_DIR = os.path.join(ROOT, "map")                     # template.html is code (in the repo)
OUT_DIR = jpaths.at("map")                               # the built page is output (data home, ADR-0008)
STAMP = os.path.join(OUT_DIR, ".fingerprint")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import backlog  # noqa: E402 - scripts/backlog.py, the BACKLOG.md parser
except ImportError:  # the public export has no backlog (JSA-085): the map shows no queue
    backlog = None

WATCH = ["data/store", "CLAUDE.md", "ARCHITECTURE.md", "PLAN-git-source-of-truth.md", "BACKLOG.md", "ROADMAP.md", "docs",
         "skills", "data/runner", "applications",
         "scripts", "phase2-prompts", "skills/job-hunt-pipeline/scripts", "skills/auto-apply/runner"]


def sh(*args):
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def fingerprint():
    h = hashlib.sha256()
    h.update(sh("git", "rev-parse", "HEAD").encode())
    h.update(sh("git", "status", "--porcelain").encode())
    for rel in WATCH:
        p = os.path.join(jpaths.home() if rel.split('/')[0] in ('data', 'applications') else ROOT, rel)   # data lives in the data home (ADR-0008)
        if os.path.isdir(p):
            names = sorted(os.listdir(p))[:400]
            h.update((rel + str(len(names)) + ",".join(names)).encode())
        elif os.path.exists(p):
            h.update((rel + str(os.path.getmtime(p))).encode())
    return h.hexdigest()[:16]


def count(path, pattern=None, dirs=False):
    p = os.path.join(ROOT, path)
    if not os.path.isdir(p):
        return 0
    items = [x for x in os.listdir(p) if not x.startswith(".")]
    if dirs:
        items = [x for x in items if os.path.isdir(os.path.join(p, x))]
    if pattern:
        items = [x for x in items if re.search(pattern, x)]
    return len(items)

def latest_log():
    """Name of the newest session log — the map keeps it next to the backlog for orientation."""
    d = os.path.join(ROOT, "skills/job-search-agent/references")
    logs = sorted([x for x in os.listdir(d) if x.startswith("session-log-")]) if os.path.isdir(d) else []
    return logs[-1] if logs else ""


def backlog_state():
    """The live queue from BACKLOG.md (scripts/backlog.py). Empty when the file is unreadable mid-edit."""
    empty = {"next": [], "counts": {s: 0 for s in (backlog.STATUSES if backlog else ())}, "doing": [], "blocked": []}
    if backlog is None:
        return empty
    try:
        rows, counts, _errors, _warnings = backlog.check(ROOT)
    except Exception:
        return empty
    brief = lambda r: {k: r[k] for k in ("id", "pri", "area", "item", "status")}
    return {
        "next": [brief(r) for r in backlog.next_items(rows, 3)],
        "counts": counts,
        "doing": [brief(r) for r in rows if r["status"] == "doing"],
        "blocked": [brief(r) for r in rows if r["status"] == "blocked"],
    }


def parse_tasks():
    p = os.path.join(ROOT, "CLAUDE.md")
    out = []
    if not os.path.exists(p):
        return out
    for line in open(p, encoding="utf-8"):
        if not line.startswith("| ") or "trig_" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        ids = re.findall(r"trig_[A-Za-z0-9]+", cells[0])
        name = re.sub(r"\(.*?\)", "", cells[0]).replace("`", "").strip()
        what = re.sub(r"\*\*|`", "", cells[2])
        out.append({"name": name, "when": cells[1], "what": what[:280], "id": ids[0] if ids else ""})
    return out


def store_state():
    """Row counts straight from data/store (ADR-0004: the store is the data; nothing has to be reported any more)."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts", "store"))
    try:
        import store
        report, bad = store.check()
        apps = store.load("applications")
    except Exception as e:
        return {"error": str(e)}
    newest = max((os.path.getmtime(store.path(n)) for n in store.DATASETS if os.path.exists(store.path(n))), default=0)
    logs = sorted(glob.glob(jpaths.data("runner/daily/*.md")))
    last = open(logs[-1], encoding="utf-8").read().strip().splitlines()[-3:] if logs else []
    return {"counts": report, "problems": len(bad), "applied": sum(a.get("status") == "Applied" for a in apps),
            "in_motion": sum(a.get("status") in ("Applied", "Applied (unconfirmed)", "Assessment", "Interview", "Offer") for a in apps),
            "updated_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(newest)) if newest else "",
            "daily_log": os.path.basename(logs[-1]) if logs else "", "daily_tail": last}


def documented_versions():
    p = os.path.join(ROOT, "ARCHITECTURE.md")
    got = {}
    if not os.path.exists(p):
        return got
    txt = open(p, encoding="utf-8").read()
    for name in ("applications", "jobs", "emails"):
        m = re.search(name + r"\s*v(\d+)", txt)
        if m:
            got[name] = int(m.group(1))
    return got

STAGES = [
    {"id": "pick", "name": "1 Pick", "who": "Claude (judgement)", "tool": "dashboard + prefilter.py",
     "in": "data/store/jobs.jsonl (eligible rows) · skip_companies.txt · data/store/applications.jsonl", "out": "a candidate list in chat",
     "pass": "only 可投 roles; AI/PM first, then Data Analyst", "fail": "nothing to apply to -> report it, do not improvise",
     "ex": "a tier-A AI-track internship picked as the next one (score 74.9)"},
    {"id": "referral", "name": "2 Referral check", "who": "Claude", "tool": "data/store/jobs.jsonl referral/contacts/warm_path · data/store/contacts.jsonl",
     "in": "the role row + his network", "out": "proceed, or stop and tell Joey",
     "pass": "nobody in his network could refer him", "fail": "a referral exists -> do not apply, message Joey first",
     "ex": "role 1 = Cold; role 2 at the same company = School alumni -> would stop for Joey"},
    {"id": "jd", "name": "3 Read the live JD", "who": "Claude", "tool": "prep_wd.py / prep_batch.py fetch, then a human read",
     "in": "the posting URL", "out": "jd.md + a go/no-go judgement",
     "pass": "class year, length, graduation window, sponsorship, still open", "fail": "any doubt -> skip and say why (the gate rules miss wording)",
     "ex": "JD: Master or PhD in CS/EE or related -> his MS ADS counts; no sponsorship clause"},
    {"id": "prep", "name": "4 Folder + platform facts", "who": "script", "tool": "prep_wd.py (CXS API) / prep_batch.py (Greenhouse API)",
     "in": "batch json (id, company, title, url, track)", "out": "applications/<date>_<Co>/ with jd.md, wd_job.json or gh_api.json, questions.json",
     "pass": "posting resolves and CXS returns the job", "fail": "404 -> mark 已关闭; unreadable -> 待核实, no materials wasted",
     "ex": "prep_wd.py found req 2641921 open and wrote jd.md"},
    {"id": "probe", "name": "5 Probe the form", "who": "script", "tool": "materials_probe.py -> requirements.json",
     "in": "gh_api.json (Greenhouse) or the live page over CDP", "out": "requirements.json: one entry per material, each with evidence",
     "pass": "every requirement carries a label + selector", "fail": "unknown control -> list it, never guess (feeds decide.py)",
     "ex": "Greenhouse exposes Resume/CV and Cover Letter file slots in the API; Workday reveals them mid-wizard"},
    {"id": "materials", "name": "6 Materials", "who": "DeepSeek + scripts", "tool": "resume-updater + ds_materials.py · cover-letter-writer + cover.js -> materials_manifest.json",
     "in": "jd.md, bullet-bank, story-bank, candidate-profile", "out": "1-page A-Classic PDF + (only if asked) a cover letter + manifest with hashes",
     "pass": "check_resume ok, bottom 730-756, exact bank wording, fact check passed", "fail": "rewrite and rebuild; never invent a bullet or a story",
     "ex": "ML/Python headline, letter 292 words, both hashes in the manifest"},
    {"id": "fill", "name": "7 Fill the form", "who": "runner (Playwright over CDP 9222)", "tool": "plan_build.py + answer_rules.js -> run.py / run_wd.py",
     "in": "plan.json + wd_profile.json + the manifest", "out": "a filled form; Workday stops at Review",
     "pass": "every required field reads back correctly", "fail": "unfillable field -> L2 DeepSeek -> L3 an agent over CDP -> L4 Joey",
     "ex": "Workday: 5 steps in 58 s, 0 needs; the sex field needed an answer_rules fix first"},
    {"id": "ladder", "name": "8 Escalate", "who": "script -> DeepSeek -> Claude -> Joey", "tool": "ladder.py (field level) · decide.py (what to do next)",
     "in": "the failing field or the structured event", "out": "one action, logged to decisions.jsonl",
     "pass": "the action is in the menu and obeys the rules", "fail": "out-of-menu or rule violation -> pause_for_joey; max 3 decisions",
     "ex": "an 83-option group fixed by DeepSeek in one try; a Workday draft needed Continue Application (code fix)"},
    {"id": "gates", "name": "9 Gates", "who": "scripts", "tool": "verify.js · canon.py · materials_check.py · approved_batches.json",
     "in": "the live page + plan + facts + manifest", "out": "verify.json, canon.json, a problem list",
     "pass": "page = plan, plan = facts, materials complete, batch approved + ds-ok", "fail": "any mismatch blocks the submit; a model never judges its own work",
     "ex": "today canon flagged three things that were correct - the rules, not the answers, were wrong"},
    {"id": "submit", "name": "10 Submit", "who": "Joey (Workday) / runner (Greenhouse, approved batch)", "tool": "save_confirmation.py",
     "in": "a clean Review page", "out": "submitted_confirmation.png + confirmation.txt",
     "pass": "confirmation URL or text that was not there before the click", "fail": "no evidence -> not Applied, keep it pending",
     "ex": "Candidate Home: Under Review, October 29, 2026"},
    {"id": "record", "name": "11 Record", "who": "Claude (any surface with the folder)", "tool": "application_record.md · data/store/applications.jsonl via store.py · commit + push",
     "in": "the confirmation + the run log", "out": "local ledger row (Applied), dashboard row, next_step",
     "pass": "row added or updated with applied_on = today; applied_on never rewritten later", "fail": "store.py refuses a row without job_id / status or a duplicate id; nothing is written",
     "ex": "local row Applied 51/110; the dashboard row (v28 -> v29) is still pending"},
]
ARTIFACTS = [
    {"f": "applications/<date>_<Co>/jd.md", "by": "prep_wd.py / prep_batch.py", "to": "Claude, ds_materials.py",
     "what": "the posting text as fetched, plus location/time type", "life": "kept forever (evidence of what was read)"},
    {"f": "gh_api.json / wd_job.json", "by": "prep_batch.py / prep_wd.py", "to": "materials_probe.py, run.py / run_wd.py",
     "what": "platform metadata: questions + file slots (Greenhouse) or req/location (Workday)", "life": "per application"},
    {"f": "requirements.json", "by": "materials_probe.py", "to": "materials_check.py, decide.py",
     "what": "what the form asks for, each entry with label + selector evidence", "life": "rewritten on each probe (Workday: every page)"},
    {"f": "paper trail: resume .docx/.pdf, cover letter .pdf", "by": "ds_materials.py + cover.js", "to": "the runner upload, the human review",
     "what": "1-page A-Classic resume and (only if asked) a letter, approved wording only", "life": "archived with the application"},
    {"f": "materials_manifest.json", "by": "ds_materials.py", "to": "materials_check.py, verify.json (context)",
     "what": "file names + sha256 + letter decision + fact-check result + track", "life": "regenerated whenever materials are"},
    {"f": "plan.json", "by": "plan_build.py (answers.json -> answer_rules.js)", "to": "run.py / run_wd.py",
     "what": "the intended answer for every field, with its source", "life": "rebuilt after answers change"},
    {"f": "verify.json", "by": "verify.js (in-page)", "to": "the submit gate, the ladder",
     "what": "per-field L1 (DOM) / L2 (React) comparison + visible L3 errors", "life": "written per run"},
    {"f": "canon.json", "by": "canon.py + canon_probe.js", "to": "the submit gate",
     "what": "the 13 irreversible fields compared against his facts, with the evidence line", "life": "written per run; empty = clean"},
    {"f": "wd_answered.json / decisions.jsonl", "by": "run_wd.py / decide.py", "to": "Claude spot-check, audit later",
     "what": "what was actually answered, and which action a model chose when something failed", "life": "append-only"},
    {"f": "handoff.json", "by": "the runner when a field cannot be fixed", "to": "L3 agent, then renamed handoff_done_<ts>.json",
     "what": "the stuck fields with selector, intended answer, page value, React value", "life": "one-shot; kept as evidence"},
    {"f": "status.txt", "by": "the runner", "to": "whoever waits on it (one grep loop)",
     "what": "one line: running | signin | needs-user | handoff | review | done | captcha", "life": "overwritten each state change"},
    {"f": "submitted_confirmation.png / confirmation.txt", "by": "save_confirmation.py", "to": "application_record.md, human audit",
     "what": "the confirmation page (Candidate Home or /confirmation) + its text", "life": "kept forever; it is the proof"},
    {"f": "application_record.md", "by": "Claude after submit", "to": "a human reading the folder later",
     "what": "role, URL, files, answers, submit time, follow-up date, what went wrong", "life": "appended over time"},
    {"f": "data/store/applications.jsonl -> dashboard/index.html", "by": "store.py writes; com.jobagent.dash rebuilds within 60 s", "to": "the local dashboard page",
     "what": "the tracker row (status, applied_on, next_step) with if_version", "life": "the local file is the ledger; the dashboard is a published copy"},
]

FAILURES = [
    {"sym": "not on a Workday application page (no progress bar)", "why": "a saved draft turns Apply into Continue Application",
     "who": "run_wd.py", "fix": "clicks Continue Application (2026-10-29); manual: click it, then run with --attach <req id>"},
    {"sym": "Execution context was destroyed", "why": "Workday navigated while the runner was reading the page",
     "who": "run_wd.py js()", "fix": "retries up to 3 times after waiting for domcontentloaded"},
    {"sym": "needs-user N question(s) in wd_needs.json", "why": "a required question with no rule and no saved fact",
     "who": "Joey", "fix": "write answers.json on the Mac (exact option text); the runner continues in place, no restart"},
    {"sym": "handoff · failed N", "why": "a field could not be fixed in 3 DeepSeek tries, or page errors",
     "who": "L3 agent (DSH / Claude Code over CDP)", "fix": "handoff_show.py, change only those fields, then run.py --resume --attach"},
    {"sym": "captcha", "why": "the tenant challenged the browser", "who": "Joey", "fix": "solve it in the tab; never bypassed by automation"},
    {"sym": "signin-timeout", "why": "the sign-in page waited 20 min without a login", "who": "Joey",
     "fix": "log in in the job Chrome, rerun with --attach (sessions are per tenant)"},
    {"sym": "canonical mismatch: X = 'Y' (want Z)", "why": "the page holds a value that contradicts his facts",
     "who": "blocks the submit", "fix": "first check whether the RULE is wrong (2026-10-29: three false alarms); only then fix the answer"},
    {"sym": "verify failed: bad=[field] errors=[...]", "why": "the page does not match the plan, or a visible validation error exists",
     "who": "the ladder: DeepSeek per field, then L3, then Joey", "fix": "never submit on a model's self-report"},
    {"sym": "materials missing: cover_letter (required by ...)", "why": "the form asks for something the manifest does not have",
     "who": "materials_check.py", "fix": "generate it (cover-letter-writer), or record why it is impossible, then re-check"},
    {"sym": "sha mismatch - the file changed after the manifest was written", "why": "materials were rebuilt after the manifest",
     "who": "materials_check.py", "fix": "rerun ds_materials.py so manifest and files agree before uploading"},
    {"sym": "option '<X>' not offered", "why": "the tenant list lacks the planned answer",
     "who": "the runner, then DeepSeek pick, then Joey", "fix": "never invent an option; Joey's own answer is never overruled, he is asked again"},
    {"sym": "403 routine_bind_update_proof_required", "why": "a device-bound routine can only be edited from that Mac",
     "who": "Joey on the Mac", "fix": "edit in the desktop app; a cloud session cannot change it"},
    {"sym": "task stops with a clone/read error", "why": "the routine could not get its code",
     "who": "the routine itself", "fix": "stops WITHOUT writing; check the git remote / App attachment before rerunning"},
    {"sym": "if_version conflict on a dataset write", "why": "something else wrote in between (task vs manual)",
     "who": "the writer", "fix": "re-read the current version, append only, retry once; never full-overwrite"},
    {"sym": "08:15 produced nothing", "why": "the Mac was asleep or the desktop app was offline at 08:15",
     "who": "Joey", "fix": "keep the Mac awake (caffeinate) or accept the missed day; the run stops clean, no partial write"},
]

SKILLS = [
    {"name": "job-search-agent", "role": "router", "when": "start of any session"},
    {"name": "job-hunt-pipeline", "role": "collect + gate", "when": "08:15 / 08:45, rule changes"},
    {"name": "daily-job-refresh", "role": "08:15 operations", "when": "when that task fails"},
    {"name": "auto-apply", "role": "batch orchestration", "when": "picking a batch / materials"},
    {"name": "ats-greenhouse", "role": "platform manual", "when": "before a Greenhouse run"},
    {"name": "ats-workday", "role": "platform manual (49 pitfalls)", "when": "before a Workday run"},
    {"name": "resume-updater", "role": "resume content rules", "when": "building materials"},
    {"name": "cover-letter-writer", "role": "letter rules", "when": "form has a slot"},
    {"name": "_shared", "role": "facts / stories / decisions", "when": "everyone"},
]

GATES = [
    {"name": "verify.js", "q": "page = plan?", "layers": "DOM value · React state · visible errors"},
    {"name": "canon.py", "q": "plan = facts?", "layers": "13 irreversible fields + evidence line"},
    {"name": "approved_batches", "q": "batch yes + ds-ok?", "layers": "Joey yes + Claude spot-check"},
    {"name": "materials_check", "q": "materials complete?", "layers": "requirements vs manifest · sha256"},
]

LAYERS = [
    {"id": "local", "name": "Local repo", "detail": "the only master: skills · applications · resume · data · runner"},
    {"id": "git", "name": "Private GitHub", "detail": "history + rollback; code source for 08:45 / 10:00"},
    {"id": "tasks", "name": "Cloud tasks", "detail": "08:15 · 08:45 · 10:00 (+ Sunday reminder)"},
    {"id": "dash", "name": "Dashboard", "detail": "local page dashboard/index.html, rebuilt from data/store within 60 s; read-only (change the store, not the page)"},
]


def build_data():
    log_name = latest_log()
    commits = []
    for line in sh("git", "log", "--pretty=%h|%ad|%s", "--date=format:%m-%d %H:%M", "-8").splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({"hash": parts[0], "when": parts[1], "subject": parts[2][:110]})
    return {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "branch": sh("git", "rev-parse", "--abbrev-ref", "HEAD") or "?",
        "head": sh("git", "rev-parse", "--short", "HEAD") or "?",
        "dirty": len([x for x in sh("git", "status", "--porcelain").splitlines() if x.strip()]),
        "remote": sh("git", "remote", "get-url", "origin").replace("https://github.com/", ""),
        "commits": commits,
        "counts": {
            "applications": count("applications", dirs=True),
            "skills": count("skills", dirs=True),
            "scripts": count("skills/auto-apply/runner", r"\.py$") + count("skills/job-hunt-pipeline/scripts", r"\.(py|js)$"),
            "tracked": len(sh("git", "ls-files").splitlines()),
        },
        "tasks": parse_tasks(),
        "store": store_state(),
        "versions": documented_versions(),
        "log": {"file": log_name},
        "backlog": backlog_state(),
        "stages": STAGES, "skills": SKILLS, "gates": GATES, "layers": LAYERS,
        "artifacts": ARTIFACTS, "failures": FAILURES,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    fp = fingerprint()
    if a.check:
        old = open(STAMP).read().strip() if os.path.exists(STAMP) else ""
        raise SystemExit(0 if old == fp else 1)
    data = build_data()
    tpl = open(os.path.join(TPL_DIR, "template.html"), encoding="utf-8").read()
    html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__BUILT__", data["built"])
    os.makedirs(OUT_DIR, exist_ok=True)
    open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(html)
    json.dump(data, open(os.path.join(OUT_DIR, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(STAMP, "w").write(fp)
    print("built map/index.html at", data["built"], "| head", data["head"], "| dirty", data["dirty"])