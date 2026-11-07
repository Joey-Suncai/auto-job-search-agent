"""Checks for the Claude reading path (no network: a fake client). Prints `fails 0` when everything passes."""
import json, os, sys
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claude_reader as cr  # noqa: E402
import email_check as ec  # noqa: E402
import sms_check as sc  # noqa: E402

fails = 0
def ok(c, label):
    global fails
    fails += 0 if c else 1
    print(("PASS " if c else "FAIL ") + label)

def apps():
    return [{"job_id": "S1", "company": "Kelharcor", "title": "Data Science Intern", "status": "Applied", "applied_on": "2026-10-30"},
            {"job_id": "K1", "company": "Wynquinnev", "title": "Machine Learning Engineer Intern", "status": "Applied", "applied_on": "2026-10-28"},
            {"job_id": "B1", "company": "CorBrakel", "title": "Quantitative Masters Internship", "status": "Applied", "applied_on": "2026-10-30"},
            {"job_id": "N1", "company": "OSTROSROS", "title": "AI Systems Intern", "status": "Shortlisted", "applied_on": ""}]

def verdict(**k):
    v = {"is_job_related": True, "job_id": "", "type": "Other", "summary": "s", "action_needed": "", "deadline": "",
         "confidence": "high", "reason": "r"}
    v.update(k); return v

class FakeClient:
    """Answers with the queued verdicts; records what was sent."""
    def __init__(self, *vs, fail=False):
        self.vs, self.fail, self.sent = list(vs), fail, []
        self.beta = NS(messages=NS(create=self.create))
    def create(self, **kw):
        self.sent.append(kw)
        if self.fail:
            raise ConnectionError("network down")
        v = self.vs.pop(0)
        return NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(v))],
                  usage=NS(input_tokens=900, cache_read_input_tokens=4000, output_tokens=120))

def mail(i, sender, subject, body, date="2026-10-30"):
    return {"id": i, "date": date, "sender": sender, "subject": subject, "body": body, "url": "u" + i}

A, E = apps(), []
fc = FakeClient(verdict(job_id="K1", type="Rejection", summary="moving forward with other candidates"))
R = cr.Reader(A, client=fc)
notes = {}
r = ec.apply_mail(A, E, mail("k1", "Wynquinnev <no-reply@greenhouse.io>", "Thank you for your application", "Thank you for applying ..."), R, notes)
ok(r and r["type"] == "Rejection" and A[1]["status"] == "Rejected" and r["reader"] == "claude", "Claude's verdict decides (Wynquinnev → Rejected)")
ok("disagree" in notes, "rules vs Claude disagreement is logged")
kw = fc.sent[0]
ok(kw["model"] == "claude-opus-5-5" and kw["output_config"]["format"]["type"] == "json_schema" and kw["fallbacks"] == "default", "request: opus 5.5, json schema, default fallbacks")
ok("K1 | Wynquinnev" in kw["system"][0]["text"] and "N1 |" not in kw["system"][0]["text"], "applications list sent, Shortlisted rows left out")
ok(R.usage == {"calls": 1, "input": 900, "cache_read": 4000, "output": 120}, "token usage is counted")

R = cr.Reader(A, client=FakeClient(verdict(job_id="S1", type="Assessment", confidence="low", reason="maybe")))
r = ec.apply_mail(A, E, mail("s1", "Kelharcor <kelharcor@myworkday.com>", "Next steps", "Please complete ..."), R, notes)
ok(r and A[0]["status"] == "Applied" and A[0]["action_needed"].startswith("请确认") and notes.get("unsure"), "low confidence → no stage move, Joey asked to confirm")

R = cr.Reader(A, client=FakeClient(verdict(job_id="X9", type="Interview")))
r = ec.apply_mail(A, E, mail("x1", "Talent <talent@greenhouse.io>", "Interview", "We'd like to schedule an interview"), R, notes)
ok(r and r.get("unmatched"), "a job_id Claude invents is refused → unmatched, not written to a row")

R = cr.Reader(A, client=FakeClient(verdict(is_job_related=False, type="NotJob")))
ok(ec.apply_mail(A, E, mail("n1", "CorBrakel Events <events@corbrakel.com>", "CorBrakel newsletter", "Our quarterly outlook and hiring news"), R, notes) is None, "NotJob → nothing stored")

notes = {}
R = cr.Reader(A, client=FakeClient(fail=True))
r = ec.apply_mail(A, E, mail("b1", "CorBrakel <corbrakel@myworkday.com>", "Pre-Interview Assessment with CorBrakel", "Complete the HireVue assessment"), R, notes)
ok(r and r["reader"] == "rules" and A[2]["status"] == "Assessment" and notes.get("fallback"), "API failure → rules fallback, reported")

calls = FakeClient(verdict())
R = cr.Reader(A, client=calls)
ok(ec.apply_mail(A, E, mail("p1", "Friend <friend@gmail.com>", "dinner?", "see you at 7"), R, {}) is None and not calls.sent, "personal mail is never sent to Claude")
ok(ec.apply_mail(A, E, mail("c1", "Workday <noreply@myworkday.com>", "Your verification code", "123456 for Kelharcor"), R, {}) is None and not calls.sent, "codes are never sent to Claude")

# SMS through the reader
A2, E2 = apps(), []
R = cr.Reader(A2, client=FakeClient(verdict(job_id="B1", type="Interview", action_needed="Reply with times")))
r = sc.apply_text(A2, E2, {"id": "sms-1", "date": "2026-10-30", "sender": "+13125550100", "service": "SMS",
                           "body": "Hi Joey, recruiter here — are you free for an interview Tuesday?"}, R, {}, frozenset({"5550102030"}))
ok(r and r["channel"] == "sms" and r["type"] == "Interview" and A2[2]["action_needed"] == "Reply with times", "text without the company name: Claude matches it")
calls = FakeClient(verdict())
R = cr.Reader(A2, client=calls)
ok(sc.apply_text(A2, E2, {"id": "sms-2", "date": "2026-10-30", "sender": "+15550102030", "service": "iMessage",
                          "body": "求职邮件 2026-10-30\n· Interview — CorBrakel: interview"}, R, {}, frozenset({"5550102030"})) is None and not calls.sent,
   "the agent's own iMessage pushes are skipped")

# report(): pushes unmatched / unsure / fallback lines
pushed = []
import notify as nt; nt.notify = lambda t, b: pushed.append(b)
ec.report("t", [], [{"unmatched": True, "kind": "Interview", "subject": "s", "summary": "Recruiter wants a call"}],
          {"unsure": ["Kelharcor: Assessment?"], "fallback": ["x"]}, {"unavailable": "no key"}, lambda s: None)
ok(pushed and "没对上申请" in pushed[0] and "请确认" in pushed[0] and "Claude 没有运行" in pushed[0] or "没经过 Claude" in pushed[0], "report pushes unmatched, unsure and fallback")

print(f"fails {fails}")
sys.exit(1 if fails else 0)
