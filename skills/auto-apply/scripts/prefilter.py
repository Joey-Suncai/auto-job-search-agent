#!/usr/bin/env python3
"""Batch pre-filter (2026-10-27): rank 可投 jobs for an application batch BEFORE any browser preflight.

Why: the 10-27 evening batch spent ~114k runner tokens preflighting 4 roles that were dropped
(login wall, clearance, wrong start window, posting removed). This script does that triage offline.

Reads (defaults = newest local copies; pass paths to override):
  --jobs  default data/store/jobs.jsonl            (rows with elig / elig_reason from gate_run.py)
  --jds   default all data/processed/jds_*.jsonl merged (cached JD text; the daily gate adds jds_gate_<date>.jsonl)
  --apps  default data/store/applications.jsonl  (tracker; the same job is skipped, other roles at an applied company stay — flag APPLIED)
Usage:
  python3 prefilter.py --track "Data Analyst" --level Internship --n 8
  python3 prefilter.py --track "Product Manager" --tier A B --login no
Columns: id score tier | login (no / YES / ?) ats | flags | company | title | location | posted | url
login: no = Greenhouse/Ashby/Lever form (no account); YES = Workday/iCIMS/Oracle/Taleo/SuccessFactors (Joey must sign in);
       ? = aggregator link (Built In, Jobright, Zapply...) — the runner resolves the real form first.
flags (from cached JD text — still re-read the live JD in preflight): CLEAR = clearance/export/US-person,
       NOSPON = no sponsorship, START = start date outside the target summer (incl. a dated range that skips June–August, e.g.
       "January - March 2027") / too early for full-time — both from config/profile.json → eligibility.intern_summer /
       fulltime_from (JSA-087; the author's: Summer 2027, full-time from Jan 2028),
       DEG = PhD/MBA only, STALE = cached JD unreadable/closed, DEF = defense company (clearance likely),
       OLD = posted before 2026-06-01, TRACK = company already shortlisted in the tracker (soft),
       APPLIED = he already applied to (or was rejected for) another role at this company (soft; ranked after new companies —
       Joey 2026-10-30: 「一个岗位被拒也可以申请别的岗位」).
TikTok / ByteDance slots (JSA-097, tiktok_slots.py): 2 counted applications per half-year per program, both companies
       together; a counted role is dropped ("tiktok slots full") when its program's slots in the current period are used,
       and the slots left are printed. Project Intern / PhD roles are exempt. --today YYYY-MM-DD sets the period (tests).
Also skips companies listed in data/dashboard/skip_companies.txt (paused / in progress / dropped — keep it updated).
"""
import argparse, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tiktok_slots  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
def newest(pat):
    f = sorted(glob.glob(os.path.join(ROOT, pat)), key=os.path.getmtime)
    return f[-1] if f else None

NO_LOGIN = {"gh": "greenhouse", "ab": "ashby", "lv": "lever"}
LOGIN = {"wd": "workday"}
URL_ATS = [("greenhouse", "greenhouse", "no"), ("gh_jid", "greenhouse", "no"), ("ashbyhq", "ashby", "no"), ("lever.co", "lever", "no"),
           ("myworkday", "workday", "YES"), ("icims", "icims", "YES"), ("oraclecloud", "oracle", "YES"), ("taleo", "taleo", "YES"),
           ("successfactors", "successfactors", "YES"), ("smartrecruiters", "smartrecruiters", "?"),
           ("builtin.com", "builtin", "?"), ("jobright", "jobright", "?"), ("zapply.jobs/l/d/greenhouse", "greenhouse", "no"),
           ("zapply.jobs/l/d/ashby", "ashby", "no"), ("zapply.jobs/l/d/lever", "lever", "no"), ("simplify.jobs", "simplify", "?")]

RX = {
    "CLEAR": re.compile(r"\b(security|secret|TS/SCI|public trust)\s+clearance|\bU\.?S\.?\s+persons?\b|\bITAR\b|export[- ]control|\b(must|required to) be (a )?(U\.?S\.?|United States) citizen", re.I),
    "NOSPON": re.compile(r"\b(unable|not able|cannot|will not|won't|do(es)? not)\b[^.;]{0,50}\bsponsor|\bno (visa )?sponsorship\b|sponsorship (is )?not available|\b(not|never)\s+(to\s+)?(currently\s+)?(require|need)s?\b[^.;]{0,40}\bsponsor", re.I),
    "DEG": re.compile(r"\b(currently )?(enrolled in|pursuing) (a )?(Ph\.?D|doctoral|MBA)\b|\bMBA (students?|candidates?) only\b|\bPh\.?D\.? (students?|candidates?) only\b", re.I),
}
DEFENSE = ("anduril", "lockheed", "northrop", "raytheon", "rtx", "general dynamics", "l3harris", "leidos", "bae systems", "booz allen", "saic", "huntington ingalls", "sierra nevada", "shield ai", "palantir")
MONTHS = "january february march april may june july august september october november december".split()


def start_patterns(intern_summer=2027, fulltime_from="2028-01"):
    """Pure (tested, JSA-087). The START regexes for a candidate's target terms.
    Internship (summer Y): a fall / winter / spring term of Y-1 or Y, a January–March Y date, co-op, residency, "starting … Y-1".
    Full-time (from YYYY-MM): a start 4 or more months before it — whole years up to that point (from two years before),
    then the months of the cutoff year ("start … 2026", "start … September 2027" for Jan 2028), ASAP / immediate start."""
    y = int(intern_summer)
    fy, fm = (int(x) for x in str(fulltime_from).split("-")[:2])
    intern = re.compile(rf"\b(fall|autumn|winter|spring) ({y - 1}|{y})\b|\b(january|jan\.?|february|march) {y}\b|\bco-?op\b|\bresidency\b"
                        rf"|\b(starting|start date)[^.;]{{0,30}}\b{y - 1}\b", re.I)
    cy, cm = (fy, fm - 4) if fm > 4 else (fy - 1, fm + 8)          # last early month = 4 months before the start ("september 2027")
    years = [str(x) for x in range(fy - 2, cy)] + ([str(cy)] if cm == 12 else [])
    alts = "|".join(years + (["(" + "|".join(MONTHS[:cm]) + f") {cy}"] if cm < 12 else []))
    ft = re.compile(rf"\b(start(ing)?|start date)[^.;]{{0,40}}\b({alts})\b|\bimmediate(ly)? start\b|\bASAP\b", re.I)
    return intern, ft


def _profile_terms():
    try:
        sys.path.insert(0, os.path.join(ROOT, "config")); import jsa_profile
        e = jsa_profile.get("eligibility", {}) or {}
        return e.get("intern_summer", 2027), e.get("fulltime_from", "2028-01"), e.get("degree_level", "masters")
    except Exception:
        return 2027, "2028-01", "masters"


_SUMMER, _FT_FROM, DEGREE_LEVEL = _profile_terms()
START_INTERN, START_FT = start_patterns(_SUMMER, _FT_FROM)
if str(DEGREE_LEVEL).lower() in ("phd", "doctoral"):   # a PhD student: PhD-only roles are fine, MBA-only still flagged
    RX["DEG"] = re.compile(r"\b(currently )?(enrolled in|pursuing) (a )?MBA\b|\bMBA (students?|candidates?) only\b", re.I)

MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
TERM_RANGE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(?:\d{1,2}(?:st|nd|rd|th)?,?\s*)?(?:(?:20)?(2[6-8])\s*)?"
                        r"(?:-|–|—|to|through|until)\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(?:\d{1,2}(?:st|nd|rd|th)?,?\s*)?(?:20)?(2[6-8])\b", re.I)

def term_range(t):
    """A dated internship range that never touches June–August ("Duration: 3 Months (January - March 2027)", Hitachi
    2026-10-30) — the same check as eligibility_rules.js termRange. Returns the matched text or None."""
    for m in TERM_RANGE.finditer(t or ""):
        if re.search(r"graduat|class of|degree|commencement|apply|deadline|posted|application", t[max(0, m.start() - 70):m.start()], re.I):
            continue
        a, b = MON[m.group(1).lower()[:3]], MON[m.group(3).lower()[:3]]
        yb = int(m.group(4)); ya = int(m.group(2)) if m.group(2) else (yb if a <= b else yb - 1)
        months, y, mo = [], ya, a
        while (y, mo) <= (yb, b) and len(months) < 24:
            months.append(mo); y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        if 0 < len(months) <= 9 and not any(6 <= x <= 8 for x in months):
            return m.group(0)
    return None

def ats_of(job, jd):
    key = (jd or {}).get("key", "") or ""
    pre = key.split(":")[0]
    if pre in NO_LOGIN: return NO_LOGIN[pre], "no"
    if pre in LOGIN: return LOGIN[pre], "YES"
    u = (job.get("ats_url") or job.get("url") or "").lower()   # ats_url = the company form behind a Built In link (resolve_builtin.py, JSA-004)
    for k, name, lg in URL_ATS:
        if k in u: return name, lg
    return (pre or "other"), "?"

POST_RX = re.compile(r"(?:lever\.co|ashbyhq\.com)/[^/]+/([0-9a-f-]{36})|greenhouse\.io/.*?(?:jobs/|token=|gh_jid=)(\d{6,})|gh_jid=(\d{6,})", re.I)


def posting_key(url):
    """Board posting id (Lever / Ashby UUID, Greenhouse job id) — the same job whatever list or aggregator it came from."""
    m = POST_RX.search(url or "")
    return next((g.lower() for g in m.groups() if g), None) if m else None


SOFT = {"TRACK", "APPLIED", "SLOT1", "SLOT2"}   # shown, never a reason to drop a row (SLOTn = TikTok / ByteDance slots left)

def flags_of(job, jd, applied_cos, tracked_cos):
    F = []
    t = (jd or {}).get("text") or ""
    st = (jd or {}).get("status")
    if st != "ok" or len(t) < 400: F.append("STALE")
    for k, rx in RX.items():
        if rx.search(t): F.append(k)
    lvl = (job.get("level") or "").lower()
    if "intern" in lvl:
        if START_INTERN.search(t + " " + (job.get("title") or "")) or term_range(t): F.append("START")
    elif START_FT.search(t): F.append("START")
    cl = (job.get("company") or "").lower()
    if any(d in cl for d in DEFENSE) and "CLEAR" not in F: F.append("DEF")
    if (job.get("posted") or "9999") < "2026-06-01": F.append("OLD")
    co = cl.split()[0] if cl else ""
    if co in tracked_cos: F.append("TRACK")
    if co in applied_cos: F.append("APPLIED")
    return F

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs"); ap.add_argument("--jds"); ap.add_argument("--apps")
    ap.add_argument("--track", nargs="*", default=None, help='e.g. "Data Analyst" "Product Manager"')
    ap.add_argument("--level", default=None, help="Internship / New grad / Early career (substring)")
    ap.add_argument("--tier", nargs="*", default=None)
    ap.add_argument("--login", choices=["no", "any"], default="any", help="no = only forms that need no account")
    ap.add_argument("--keep-flagged", action="store_true", help="also list rows with CLEAR/NOSPON/DEG/START/STALE")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--json", help="write the picked rows here (input for the batch runner)")
    ap.add_argument("--today", help="the submit day that decides the TikTok / ByteDance period (default: today)")
    a = ap.parse_args()
    # every cached JD file, oldest first: a newer readable copy wins; a newer failed fetch never hides older readable text
    jds_files = [a.jds] if a.jds else sorted(glob.glob(jpaths.data("processed/jds_*.jsonl")), key=os.path.getmtime)
    jds_p = jds_files[-1] if jds_files else None
    sys.path.insert(0, os.path.join(ROOT, "scripts/store")); import store  # data/store is the source (ADR-0004)
    jobs = json.load(open(a.jobs)) if a.jobs else store.load("jobs"); jobs = jobs if isinstance(jobs, list) else jobs.get("rows", [])
    jds = {}
    for fp in jds_files:
        for line in open(fp, encoding="utf8"):
            try: d = json.loads(line)
            except Exception: continue
            if d.get("status") == "ok" or (jds.get(d.get("id")) or {}).get("status") != "ok":
                jds[d["id"]] = d
    apps = json.load(open(a.apps)) if a.apps else store.load("applications"); apps = apps if isinstance(apps, list) else apps.get("rows", [])
    first = lambda s: (s or "").lower().split()[0] if s else ""
    applied_cos = {first(x.get("company")) for x in apps if x.get("status") not in ("Shortlisted", "Archived", "", None)}
    tracked_cos = {first(x.get("company")) for x in apps if x.get("status") == "Shortlisted"}
    applied_ids = {x.get("job_id") for x in apps}
    # the same posting under another row id (Built In row resolved to a board URL already applied to: Simbe J11772 = J12011, 2026-10-31)
    jobs_by_id = {j["id"]: j for j in jobs} if isinstance(jobs, list) else {}
    applied_posts = {posting_key(u) for x in apps for u in (x.get("url"), (jobs_by_id.get(x.get("job_id")) or {}).get("url"),
                     (jobs_by_id.get(x.get("job_id")) or {}).get("ats_url")) if posting_key(u)}
    skip_p = jpaths.data("dashboard/skip_companies.txt")
    skip = {}
    if os.path.exists(skip_p):
        for line in open(skip_p, encoding="utf8"):
            if line.strip() and not line.startswith("#"):
                c, _, why = line.partition("|"); skip[c.strip().lower()] = why.strip()
    # a skip line for a company the tracker now shows as applied / rejected / in assessment is stale: the pause it
    # recorded is over, and its other roles should come back (flagged APPLIED) (JSA-011)
    stale = sorted(c for c in skip if any((x.get("company") or "").lower().startswith(c) and x.get("status") not in ("Shortlisted", "Archived", "", None) for x in apps))
    for c in stale:
        skip.pop(c)
    if stale:
        print(f"skip list: {len(stale)} stale line(s) ignored (company now in the tracker): {', '.join(stale)} — remove them from data/dashboard/skip_companies.txt")
    out, skipped = [], {"not 可投": 0, "same job in tracker": 0, "same posting in tracker": 0, "skip list": 0, "tiktok slots full": 0, "flagged": 0, "login": 0}
    slot_why = {}
    for j in jobs:
        if a.track and j.get("track") not in a.track: continue
        if a.level and a.level.lower() not in (j.get("level") or "").lower(): continue
        if a.tier and j.get("tier") not in a.tier: continue
        if j.get("elig") != "可投": skipped["not 可投"] += 1; continue
        if j["id"] in applied_ids: skipped["same job in tracker"] += 1; continue
        if {posting_key(j.get("url")), posting_key(j.get("ats_url"))} & applied_posts - {None}: skipped["same posting in tracker"] += 1; continue
        if any((j.get("company") or "").lower().startswith(c) for c in skip): skipped["skip list"] += 1; continue
        sl = tiktok_slots.check(j, apps, a.today) if tiktok_slots.limited(j) else None
        if sl and not sl["allowed"]:
            skipped["tiktok slots full"] += 1; slot_why.setdefault(sl["reason"], []).append(j["id"]); continue
        jd = jds.get(j["id"])
        ats, login = ats_of(j, jd)
        if a.login == "no" and login != "no": skipped["login"] += 1; continue
        F = flags_of(j, jd, applied_cos, tracked_cos)
        hard = [f for f in F if f not in SOFT]
        if hard and not a.keep_flagged: skipped["flagged"] += 1; continue
        if sl and sl["counted"]: F.append(f"SLOT{sl['remaining']}")   # TikTok / ByteDance: slots left in this period (soft)
        out.append(dict(j, ats=ats, login=login, flags=F))
    rank = {"no": 0, "?": 1, "YES": 2}
    out.sort(key=lambda r: (len([f for f in r["flags"] if f not in SOFT]), "APPLIED" in r["flags"], rank[r["login"]], -(r.get("score") or 0)))
    # one row per company
    seen, pick = set(), []
    for r in out:
        c = first(r.get("company"))
        if c in seen: continue
        seen.add(c); pick.append(r)
        if len(pick) >= a.n: break
    print(f"inputs: {os.path.basename(a.jobs or 'jobs.jsonl')} · {len(jds_files)} JD file(s), newest {os.path.basename(jds_p or '-')} · {os.path.basename(a.apps or 'applications.jsonl')}")
    print(f"candidates {len(out)} (skipped: " + ", ".join(f"{k} {v}" for k, v in skipped.items()) + ")")
    if any(tiktok_slots.limited(j) for j in jobs if not a.track or j.get("track") in a.track):
        print("TikTok / ByteDance slots (2 per half-year per program, both companies together; Project Intern / PhD exempt):")
        for line in tiktok_slots.summary(apps, a.today):
            print("  " + line)
        for why, ids in slot_why.items():
            print(f"  refused {len(ids)} role(s): {why} — e.g. {', '.join(ids[:5])}")
    for r in pick:
        print(f"{r['id']} {r.get('score', 0):>5} {r.get('tier', '')} | {r['login']:<3} {r['ats']:<11} | {','.join(r['flags']) or '-':<12} | "
              f"{(r.get('company') or '')[:26]:<26} | {(r.get('title') or '')[:58]:<58} | {(r.get('location') or '')[:20]:<20} | {r.get('posted', '')} | {r.get('url', '')}")
    if a.json:
        json.dump([{k: r.get(k) for k in ("id", "company", "title", "track", "level", "location", "url", "ats", "login", "flags", "score", "tier")} for r in pick],
                  open(a.json, "w", encoding="utf8"), ensure_ascii=False, indent=1)
        print("wrote", a.json)

if __name__ == "__main__":
    main()
