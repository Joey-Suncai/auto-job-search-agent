"""Read-only audit: Claude re-reads the last N days of job mail and lists where its verdict differs from the tracker
(email row type, matched application, application stage). Writes nothing; prints a report for a session / Joey.
usage: ~/.job-agent-venv/bin/python scripts/daily/recheck_emails.py [--days 10] [--out <file.json>]
"""
import json, sys
import email_check as ec
from claude_reader import Reader


def main(a):
    days = int(a[a.index("--days") + 1]) if "--days" in a else 10
    apps, emails = ec.store.load("applications"), ec.store.load("emails")
    by_id = {e["id"]: e for e in emails}
    R, out = Reader(apps), []
    for m in ec.fetch(days):
        if ec.classify(m["subject"], m["body"]) is None:
            continue
        a_rule = ec.match(apps, m["sender"], m["subject"], m["body"])
        if not (m["id"] in by_id or a_rule or ec.ATS.search(m["sender"]) or ec.JOBWORDS.search(m["subject"] + " " + m["body"][:4000])):
            continue
        v = R.read(m)
        e = by_id.get(m["id"])
        app = next((x for x in apps if x.get("job_id") == v["job_id"]), None)
        issues = []
        if e and v["type"] != "NotJob" and e["type"] != v["type"] and not (e["type"] == "Other" and v["type"] == "Action"):
            issues.append(f"type {e['type']} → {v['type']}")
        if e and v["job_id"] and e.get("job_id") != v["job_id"]:
            issues.append(f"job {e.get('job_id')} → {v['job_id']}")
        if e and v["type"] == "NotJob":
            issues.append("stored but Claude says not a job mail")
        if not e and v["type"] != "NotJob":
            issues.append("missed: not in the tracker's mail list")
        want = {"Rejection": "Rejected", "Assessment": "Assessment"}.get(v["type"])
        if app and want and app.get("status") not in (want, "Rejected", "Offer", "Withdrawn", "Declined by Joey"):
            issues.append(f"stage {app.get('status')} → {want}?")
        if issues:
            out.append({"id": m["id"], "date": m["date"], "from": m["sender"][:60], "subject": m["subject"][:90], "issues": issues,
                        "claude": v})
    print(json.dumps({"usage": R.usage, "issues": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
