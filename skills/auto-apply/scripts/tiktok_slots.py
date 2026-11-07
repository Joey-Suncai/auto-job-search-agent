#!/usr/bin/env python3
"""TikTok / ByteDance application slots (JSA-097): never a 3rd counted application in one half-year.

TikTok's Early Careers FAQ (skills/ats-tiktok/SKILL.md §2): up to 2 Early Career positions per program per application
period (January–June, July–December), TikTok and its affiliates together, no withdrawal; PhD and Project Intern roles are
outside the limit. Spec + cases: scripts/test_cases/tiktok_slots_spec.md (harness scripts/test_tiktok_slots.py).

    python3 tiktok_slots.py            slots used / left per period and program, from data/store/applications.jsonl
    python3 tiktok_slots.py --backfill write the `period` field into the limited tracker rows that miss it (store.py)
Used by prefilter.py (refuses a counted role when its program is full) and run_tiktok.py (refuses to open the form).
"""
import argparse, os, re, sys
from datetime import date

LIMIT = 2
COMPANY_RX = re.compile(r"tiktok|bytedance|capcut|lemon8", re.I)
SITE_RX = re.compile(r"lifeattiktok\.com|careers\.tiktok\.com|jobs\.bytedance\.com|joinbytedance\.com", re.I)
EXEMPT_RX = re.compile(r"project\s+intern|\bph\.?\s?d\b", re.I)
NOT_SUBMITTED = ("", "shortlisted", "archived")   # archived = a never-applied row closed (JSA-013)


def limited(row):
    """A TikTok / ByteDance (or affiliate) row: company name or posting site."""
    r = row or {}
    return bool(COMPANY_RX.search(r.get("company") or "") or SITE_RX.search(f"{r.get('url') or ''} {r.get('ats_url') or ''}"))


def exempt(row):
    return bool(EXEMPT_RX.search((row or {}).get("title") or ""))


def period_of(day):
    """'2026-11-03' → '2026H2'; '2027-01-05' → '2027H1'; '' → ''."""
    m = re.match(r"(\d{4})-(\d{2})", str(day or ""))
    return f"{m.group(1)}H{1 if int(m.group(2)) <= 6 else 2}" if m else ""


def program(row):
    r = row or {}
    lvl, title = (r.get("level") or "").lower(), (r.get("title") or "").lower()
    if re.search(r"\bintern", lvl) or re.search(r"\bintern(s|ship)?\b", title):   # not "International …"
        return "intern"
    if any(k in lvl for k in ("new grad", "full-time", "full time", "graduate")):
        return "graduate"
    return "unknown"


def counted(app):
    """A tracker row that used a slot: limited, not exempt, submitted (any status but Shortlisted / empty)."""
    return limited(app) and not exempt(app) and (app.get("status") or "").strip().lower() not in NOT_SUBMITTED


def app_period(app):
    return app.get("period") or period_of(app.get("applied_on")) or period_of(app.get("updated"))


def usage(apps):
    """{period: {'intern': n, 'graduate': n, 'unknown': n, 'rows': [job_id…]}} over the counted tracker rows."""
    out = {}
    for a in apps or []:
        if not counted(a):
            continue
        u = out.setdefault(app_period(a), {"intern": 0, "graduate": 0, "unknown": 0, "rows": []})
        u[program(a)] += 1
        u["rows"].append(a.get("job_id"))
    return out


def used_in(u, prog):
    """Slots used for a program: rows of unknown program count against every program; an unknown job takes the fuller one."""
    if prog == "unknown":
        return max(u.get("intern", 0), u.get("graduate", 0)) + u.get("unknown", 0)
    return u.get(prog, 0) + u.get("unknown", 0)


def check(job, apps, today=None):
    """Would submitting `job` today stay inside the limit? → dict(limited, counted, period, program, used, remaining, allowed, reason)."""
    per = period_of(today or date.today().isoformat())
    prog = program(job)
    lim = limited(job)
    cnt = lim and not exempt(job)
    used = used_in(usage(apps).get(per, {}), prog)
    rem = max(0, LIMIT - used)
    ok = (not cnt) or rem > 0
    why = "" if ok else (f"TikTok/ByteDance {per} {prog} slots used {used}/{LIMIT} (2 per half-year per program, TikTok + "
                         f"ByteDance together, no withdrawal) — next period starts {next_start(per)}")
    return {"limited": lim, "counted": cnt, "period": per, "program": prog, "used": used, "remaining": rem, "allowed": ok, "reason": why}


def next_start(per):
    y, h = int(per[:4]), per[-1]
    return f"{y}-07-01" if h == "1" else f"{y + 1}-01-01"


def summary(apps, today=None):
    """One line per period with counted rows (and today's period always): used / left for intern and graduate."""
    u = usage(apps)
    cur = period_of(today or date.today().isoformat())
    lines = []
    for per in sorted(set(u) | {cur}):
        x = u.get(per, {})
        parts = [f"{p} {used_in(x, p)}/{LIMIT} used, {max(0, LIMIT - used_in(x, p))} left" for p in ("intern", "graduate")]
        lines.append(f"{per}{' (now)' if per == cur else ''}: " + " · ".join(parts) + (f"  [{', '.join(x['rows'])}]" if x.get("rows") else ""))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--today")
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../scripts/store")); import store
    if a.backfill:
        apps = store.load("applications")          # loaded right before the save
        n = 0
        for r in apps:
            if counted(r) and not r.get("period") and app_period(r):
                r["period"] = app_period(r); n += 1
        if n:
            store.save("applications", apps)
        print(f"backfill: period written on {n} row(s)")
    print("TikTok / ByteDance slots (limit 2 per half-year per program; Project Intern / PhD exempt):")
    for line in summary(store.load("applications"), a.today):
        print("  " + line)


if __name__ == "__main__":
    main()
