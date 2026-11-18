"""One-off backfill (JSA-265): re-read every stored job mail whose `action` is the old generic line ("Read the email and act —
see the link") or empty-of-meaning, or that a run marked `reread`, and write a concrete next step.

The mail text is not kept in data/store/emails.jsonl, so each message is fetched again from Gmail by its id (IMAP,
read-only: EXAMINE + BODY.PEEK). Claude reads it (claude_reader.Reader); a vague or missing step falls back to the rules
step (email_check.step_of). Only emails.jsonl `action` / `deadline` and applications.jsonl `action_needed` /
`action_deadline` change, and an application's step only while it still shows that mail's old step (a step Joey marked
done, `action_done`, `applied_on` and the stage are never touched). Texts (sms-…) are skipped with a note.

usage: ~/.job-agent-venv/bin/python scripts/daily/backfill_actions.py [--dry-run] [--no-claude] [--no-git]
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import email_check as ec  # noqa: E402
import next_step  # noqa: E402


def targets(emails):
    """Pure (tested): the stored mail rows that need a new step."""
    return [e for e in emails if e.get("job_id") and (e.get("reread") or ((e.get("action") or "").strip()
                                                                          and next_step.is_vague(e["action"])))]


def backfill(apps, emails, mails, reader=None, log=print):
    """Pure apart from the reader (tested): mails = {id: fetched message}. Returns the list of changes."""
    changes = []
    for e in targets(emails):
        m = mails.get(e["id"])
        if not m:
            log(f"skip {e['id']} ({e.get('company')}): message not fetched")
            continue
        kind = "Action" if e.get("type") == "Other" else e.get("type")   # stored "Other" = a rules Action mail
        act, dl = "", ""
        if reader is not None:
            try:
                v = reader.read(m)
                kind = v["type"] if v["type"] != "NotJob" else "Other"     # Claude's type decides (Other / NotJob → no step)
                act, dl = v["action_needed"], v.get("deadline", "")
            except Exception as x:
                log(f"claude failed on {e['id']}: {type(x).__name__} {str(x)[:80]} — rules step")
        act, dl, again = ec.step_of(kind, m, act, dl)
        old = e.get("action", "")
        app = next((a for a in apps if a.get("job_id") == e["job_id"]), {})
        before = app.get("action_needed", "")
        ec.refresh_action(apps, e, act, dl)
        if again:
            e["reread"] = True
        changes.append({"id": e["id"], "company": e.get("company"), "old": old, "new": act, "deadline": e.get("deadline", ""),
                        "app_before": before, "app_after": app.get("action_needed", "")})
    return changes


def main(a):
    from run_daily import log, git_publish
    apps, emails = ec.store.load("applications"), ec.store.load("emails")
    todo = targets(emails)
    ids = [e["id"] for e in todo if not e["id"].startswith("sms-")]
    for e in todo:
        if e["id"].startswith("sms-"):
            print(f"skip text {e['id']} ({e.get('company')}): texts are not re-read here")
    mails = {m["id"]: m for m in ec.fetch_ids(ids)} if ids else {}
    reader = None if "--no-claude" in a else ec.make_reader(apps, log, a)
    reader = None if isinstance(reader, dict) else reader
    ch = backfill(apps, emails, mails, reader)
    for c in ch:
        print(f"{c['company']}: {c['old'][:40]!r} → {c['new']!r} (deadline {c['deadline'] or '—'}) · tracker {c['app_before'][:30]!r} → {c['app_after']!r}")
    print(f"{len(todo)} rows to fix · {len(mails)} fetched · {len(ch)} rewritten")
    if "--dry-run" in a:
        return 0
    ec.store.save("applications", apps)
    ec.store.save("emails", emails)
    if "--no-git" not in a:
        print("git:", git_publish(f"data: JSA-265 backfill — concrete next steps for {len(ch)} mails"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
