"""Claude reads every job-looking e-mail / text before it changes the tracker (Joey 2026-10-30: 「不能只是靠脚本来阅读以免
出现今天这样的错误……用 API 接入 Claude 来阅读邮件和短信，防止误判、漏判」).

The keyword rules in email_check.py stay as (1) a wide recall filter that decides what is sent to Claude at all — so
personal mail and texts never leave the Mac — and (2) the fallback when the API is unavailable. For every candidate
message Claude returns a structured verdict (job related?, which application, type, action, deadline, confidence);
the code then checks it (the job_id must be a real applied row) before email_check.apply_mail writes anything.

Key: an Anthropic API key in the macOS Keychain, created by Joey (never pasted into chat):
    security add-generic-password -s jobagent-anthropic -a jobagent -w
Model: claude-opus-5-5 (override with JOBAGENT_READER_MODEL). Each call logs its token usage to the daily log.
"""
import json, os, subprocess

SERVICE, ACCOUNT = "jobagent-anthropic", "jobagent"
MODEL = os.environ.get("JOBAGENT_READER_MODEL", "claude-opus-5-5")
TYPES = ["Rejection", "Assessment", "Interview", "Offer", "Action", "Confirmation", "Other", "NotJob"]

SYSTEM = """You read messages that arrived in the user's job-search inbox (e-mail or SMS/iMessage) and decide what each
one means for his application tracker. Joey is a student applying to internships and new-grad roles.

For the message, return:
- is_job_related: true when a company, recruiter or applicant-tracking system is writing about one of his applications,
  an interview, an assessment, an offer or a recruiting conversation. Newsletters, job alerts / recommendations, school
  career-office mail, marketing, and personal messages are false.
- job_id: the job_id of the application below that the message is about, or "" when none of them fits. Pick only from
  the list. If several rows are at the same company, use the role title, requisition number or date to choose; if you
  still cannot tell, return "" and say so in reason.
- company_job_ids: when you returned job_id "" because several rows at the SAME company fit equally (the message names
  the company but not which role), list those job_ids; otherwise [].
- type: Rejection (any decision not to move forward, however politely worded) · Assessment (an online test / HireVue /
  coding challenge to complete) · Interview (an invitation or scheduling request) · Offer · Action (the company asks
  him to do or provide something else) · Confirmation (application received, no decision yet) · Other (job-related
  but none of these) · NotJob.
  Read the whole message: a confirmation that lists every possible later status ("Not Selected — we will not be moving
  forward") is still a Confirmation; a mail titled "Thank you for your application" that says they chose other
  candidates is a Rejection.
- summary: one plain English sentence a busy reader can act on (company + what happened).
- action_needed: the next step, written so Joey never has to open the message to know what to do (JSA-265). One
  imperative sentence, verb first: WHAT to do, WHERE (the platform, portal or tool the message names — HackerRank,
  the Workday candidate home, a Calendly link, a reply to the recruiter …; say "via the link in the email" for a link),
  BY WHEN (the deadline as a date, e.g. "by Nov 12"; "within 24 hours of receiving it" when that is all it says), and HOW
  LONG when the message says (e.g. "(25 min)"). Several required steps → name them all in order. Good examples:
  "Take the Coderbyte assessment (60 min) via the link in the email by Nov 14" ·
  "Book a start time for the take-home assignment via the Google Calendar link (check the time zone), then submit it
  within 24 hours of receiving the package" ·
  "Complete the Work Opportunity Tax Credit (WOTC) questionnaire via the link in the email" ·
  "Log in to the HPE Workday candidate home and finish the open application task".
  Never write a generic line such as "Read the email and act", "See the link" or "Check the email" — if you cannot tell
  what is asked, say what the message seems to want and add "(unclear — check the email)". Return "" when there is nothing
  for him to do (a confirmation, a rejection, a pure status update).
- deadline: YYYY-MM-DD if the message gives or implies one (e.g. "within 5 days" → the message date + 5), else "".
- confidence: high · medium · low. Use low whenever you are unsure of the type or the application.
- reason: one short sentence quoting the words that decided the type.

Applications (job_id | company | role | status | applied_on):
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "is_job_related": {"type": "boolean"},
        "job_id": {"type": "string"},
        "company_job_ids": {"type": "array", "items": {"type": "string"}},
        "type": {"type": "string", "enum": TYPES},
        "summary": {"type": "string"},
        "action_needed": {"type": "string"},
        "deadline": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "reason": {"type": "string"},
    },
    "required": ["is_job_related", "job_id", "company_job_ids", "type", "summary", "action_needed", "deadline", "confidence", "reason"],
    "additionalProperties": False,
}


def api_key():
    r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", ACCOUNT, "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


# tracker rows Joey never applied to: kept out of mail matching (Archived = a Shortlisted row closed by JSA-013, 2026-11-05)
NOT_APPLIED = ("Shortlisted", "Archived")


def apps_block(apps):
    rows = [a for a in apps if a.get("status") not in NOT_APPLIED]
    rows.sort(key=lambda a: (a.get("company") or "", a.get("applied_on") or ""))
    return "\n".join(f"{a.get('job_id')} | {a.get('company')} | {a.get('title')} | {a.get('status')} | {a.get('applied_on') or ''}"
                     for a in rows)


class Reader:
    """One client per run. read(m) → verdict dict (validated) — raises on API failure so the caller can fall back."""

    def __init__(self, apps, client=None, log=None):
        self.apps = {a.get("job_id"): a for a in apps if a.get("status") not in NOT_APPLIED}
        self.system = [{"type": "text", "text": SYSTEM + apps_block(apps), "cache_control": {"type": "ephemeral"}}]
        self.log = log or (lambda s: None)
        self.usage = {"calls": 0, "input": 0, "cache_read": 0, "output": 0}
        if client is None:
            key = api_key()
            if not key:
                raise LookupError("no Anthropic API key in the Keychain (service jobagent-anthropic)")
            import anthropic
            client = anthropic.Anthropic(api_key=key, max_retries=3)
        self.client = client

    def read(self, m):
        content = (f"Channel: {m.get('channel', 'email')}\nDate: {m['date']}\nFrom: {m['sender']}\n"
                   f"Subject: {m.get('subject', '')}\n\n{m['body'][:12000]}")
        r = self.client.beta.messages.create(
            model=MODEL, max_tokens=2048,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=self.system, messages=[{"role": "user", "content": content}])
        u = r.usage
        self.usage["calls"] += 1
        self.usage["input"] += u.input_tokens or 0
        self.usage["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
        self.usage["output"] += u.output_tokens or 0
        if r.stop_reason == "refusal":
            raise RuntimeError("Claude declined to read this message")
        text = next(b.text for b in r.content if b.type == "text")
        return self.check(json.loads(text))

    def check(self, v):
        """The verdict may only point at a real applied row; anything else becomes 'no match' with low confidence."""
        if v.get("job_id") and v["job_id"] not in self.apps:
            v.update(reason=f"unknown job_id {v['job_id']}: " + v.get("reason", ""), job_id="", confidence="low")
        ids = [i for i in (v.get("company_job_ids") or []) if i in self.apps]
        same = len({(self.apps[i].get("company") or "").lower() for i in ids}) == 1
        v["company_job_ids"] = ids if same and not v.get("job_id") else []
        if v.get("type") not in TYPES:
            v.update(type="Other", confidence="low")
        if not v.get("is_job_related"):
            v["type"] = "NotJob"
        return v
