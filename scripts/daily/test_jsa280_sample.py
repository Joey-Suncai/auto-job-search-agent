"""JSA-280 fixed sample: the 33 real mails of 11-05 / 06 that Claude could not read (data home data/raw, git-ignored —
skipped when absent). Checks with the answers Joey approved in JSA-266:
  1. rules-only mode (reader=None): every mail gets the right type and the right application (or none);
  2. a reader that always fails (credit error): no application changes at all, every candidate stored as Pending;
  3. the reader comes back (answers as verdicts): the Pending rows end up with the right type / application.
Prints `fails 0` when everything passes."""
import copy, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import email_check as ec  # noqa: E402
RAW = ec.jpaths.data("raw")
fails = 0
def ok(c, label):
    global fails
    fails += 0 if c else 1
    print(("PASS " if c else "FAIL ") + label)

try:
    MAILS = json.load(open(os.path.join(RAW, "jsa280_mails_2026-11-10.json")))
    ANS = json.load(open(os.path.join(RAW, "jsa280_answers_2026-11-10.json")))
    APPS = json.load(open(os.path.join(RAW, "jsa280_apps_2026-11-10.json")))
except OSError as e:
    print(f"SKIP sample not on this machine ({e.filename})\nfails 0"); sys.exit(0)

# Claude's judgment where the JSA-266 answer and a later rule of Joey's differ: JSA-280 ② (Joey 2026-11-10) drops every
# non-ATS bulk mail, even from the company — Corquinnev's two candidate-experience surveys (qemailserver.com, List-Unsubscribe)
# were kept as "Other" in JSA-266; under ② they are dropped, which is right: a survey is not news about the application.
JUDGED = {"1a1b0f35d9cd8ead": ("NotJob", ""), "1a1b0f48e76f1733": ("NotJob", "")}


def want(i):
    if i in JUDGED:
        return JUDGED[i]
    t, j = ANS[i]["type"], ANS[i]["job_id"] or ""
    return ("NotJob" if not j else t), j

# 1. rules only
apps, emails = copy.deepcopy(APPS), []
for m in MAILS:
    r = ec.apply_mail(apps, emails, dict(m))
    e = next((x for x in emails if x["id"] == m["id"]), None)
    got = (e["type"], e["job_id"]) if e else ("NotJob", "")
    if got == ("NotJob", "") and r and r.get("unmatched"):
        got = ("unmatched", "")
    w = want(m["id"])
    good = got == w or (w[0] == "NotJob" and got[0] in ("NotJob", "unmatched"))
    ok(good, f"rules {m['id']} {m['subject'][:50]!r}: got {got} want {w}")

# 2. reader always fails
class Down:
    def read(self, m):
        raise RuntimeError("Error code: 400 - Your credit balance is too low to access the Anthropic API.")
apps, emails, notes = copy.deepcopy(APPS), [], {}
before = json.dumps(apps, sort_keys=True)
for m in MAILS:
    ec.apply_mail(apps, emails, dict(m), Down(), notes)
ok(json.dumps(apps, sort_keys=True) == before, "credit error: no application row changes (stage, last_email, action)")
ok(all(e["type"] == ec.PENDING and not e["job_id"] and e["reread"] for e in emails), f"credit error: {len(emails)} stored rows are all Pending")
for m in MAILS:     # second run, still down: nothing changes, nothing doubles
    ec.apply_mail(apps, emails, dict(m), Down(), notes)
ok(json.dumps(apps, sort_keys=True) == before and len({e["id"] for e in emails}) == len(emails), "second failing run: still no change, no duplicates")
job_mails = [i for i in ANS if want(i)[1]]
ok(all(any(e["id"] == i for e in emails) for i in job_mails), "every real job mail is kept as Pending for a re-read")

# 3. Claude is back: verdicts = the approved answers
class Back:
    def read(self, m):
        t, j = want(m["id"])
        return {"is_job_related": t != "NotJob", "job_id": j, "company_job_ids": [], "type": t, "summary": "s",
                "action_needed": "", "deadline": "", "confidence": "high", "reason": "r"}
for m in MAILS:
    ec.apply_mail(apps, emails, dict(m), Back(), notes)
for i in ANS:
    t, j = want(i)
    e = next((x for x in emails if x["id"] == i), None)
    ok((e is None and t == "NotJob") or (e and (e["type"], e["job_id"]) == (t, j)), f"re-read {i}: {t} {j}")
by = {a["job_id"]: a for a in apps}
ok(all(by[a["job_id"]].get("applied_on") == a.get("applied_on") for a in APPS), "applied_on never changes")
print(f"fails {fails}")
