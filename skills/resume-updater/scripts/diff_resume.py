"""Show what a job-tailored resume changed vs. its base role (to report to the candidate).
Usage: python3 diff_resume.py <base_role_key> <job content.json> [role_key]
"""
import sys, json, difflib, content as c
base = c.ROLES[sys.argv[1]]
job = json.load(open(sys.argv[2]))["ROLES"]
job = job[sys.argv[3]] if len(sys.argv) > 3 else next(iter(job.values()))
def lines(r):
    out = [f"[Label] {r.get('label','')}"]
    out += [f"[Skill] {k}: {v}" for k, v in r["skills"] + r.get("skills_a", [])]
    for p in r["projects"]: out += [f"[Project] {p['title']}"] + [f"  - {b}" for b in p["bullets"]]
    for e in r["exp"]: out += [f"[Exp] {e['org']}"] + [f"  - {b}" for b in e["bullets"]]
    out.append(f"[Leadership] {'short' if r.get('lead_short') else 'full'}")
    return out
for l in difflib.unified_diff(lines(base), lines(job), "base", "tailored", lineterm="", n=0):
    if not l.startswith(("@@", "---", "+++")): print(l)
