"""Checks for backfill_actions.py (JSA-265), offline. Prints `fails 0` when everything passes."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backfill_actions as bf, next_step as ns  # noqa: E402

fails = 0
def ok(c, label):
    global fails
    fails += 0 if c else 1
    print(("PASS " if c else "FAIL ") + label)

G = ns.OLD_GENERIC
apps = [{"job_id": "A", "company": "Acme", "action_needed": G, "applied_on": "2026-11-01", "status": "Assessment"},
        {"job_id": "B", "company": "Beta", "action_needed": "", "action_done": [{"on": "2026-11-08", "action": G}]},
        {"job_id": "C", "company": "Gamma", "action_needed": G}]
emails = [{"id": "1", "job_id": "A", "company": "Acme", "type": "Assessment", "action": G, "deadline": ""},
          {"id": "2", "job_id": "B", "company": "Beta", "type": "Interview", "action": G, "deadline": ""},
          {"id": "3", "job_id": "C", "company": "Gamma", "type": "Other", "action": G, "deadline": ""},
          {"id": "4", "job_id": "A", "company": "Acme", "type": "Confirmation", "action": "", "deadline": ""},
          {"id": "5", "job_id": "A", "company": "Acme", "type": "Other", "action": "Upload your transcript", "deadline": ""}]
ok([e["id"] for e in bf.targets(emails)] == ["1", "2", "3"], "targets: generic rows only, not blank or concrete ones")
mails = {"1": {"id": "1", "date": "2026-11-05", "subject": "Acme assessment", "body": "Your HireVue interview takes 20 minutes. Complete it by Nov 9."},
         "2": {"id": "2", "date": "2026-11-05", "subject": "Beta", "body": "Please share your availability."},
         "3": {"id": "3", "date": "2026-11-05", "subject": "Gamma", "body": "Thanks again."}}
ch = bf.backfill(apps, emails, mails, None, log=lambda s: None)
ok(emails[0]["action"] == "Complete the HireVue assessment (20 min) via the link in the email" and emails[0]["deadline"] == "2026-11-09"
   and apps[0]["action_needed"] == emails[0]["action"] and apps[0]["action_deadline"] == "2026-11-09", "rules step + deadline into both rows")
ok(apps[0]["applied_on"] == "2026-11-01" and apps[0]["status"] == "Assessment", "applied_on / stage untouched")
ok(apps[1]["action_needed"] == "" and apps[1]["action_done"] == [{"on": "2026-11-08", "action": G}] and emails[1]["action"].startswith("Reply with your availability"),
   "a done step stays done; history untouched; the mail row still gets the step")
ok(emails[2].get("reread") and "not read automatically" in apps[2]["action_needed"], "no request sentence → specific open-this-mail step, marked reread")
ok(len(ch) == 3 and not any(c["new"] == G for c in ch), "the generic line is never written back")

class R:
    def __init__(self, **v): self.v = v
    def read(self, m):
        return dict({"type": "Assessment", "action_needed": "", "deadline": ""}, **self.v)
apps2 = [{"job_id": "C", "company": "Gamma", "action_needed": G}]
em2 = [{"id": "3", "job_id": "C", "company": "Gamma", "type": "Other", "action": G, "deadline": ""}]
bf.backfill(apps2, em2, mails, R(type="Confirmation"), log=lambda s: None)
ok(em2[0]["action"] == "" and apps2[0]["action_needed"] == "" and "reread" not in em2[0], "Claude: nothing to do → step cleared")
apps3 = [{"job_id": "C", "company": "Gamma", "action_needed": G}]
em3 = [{"id": "3", "job_id": "C", "company": "Gamma", "type": "Other", "action": G, "deadline": ""}]
bf.backfill(apps3, em3, mails, R(type="Action", action_needed="Fill out the WOTC questionnaire via the link in the email by Nov 12", deadline="2026-11-12"), log=lambda s: None)
ok(apps3[0]["action_needed"].startswith("Fill out the WOTC") and apps3[0]["action_deadline"] == "2026-11-12", "Claude's concrete step wins")
print(f"fails {fails}")
sys.exit(1 if fails else 0)
