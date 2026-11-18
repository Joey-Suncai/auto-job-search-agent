"""Local daily job-email check (ADR-0004, JSA-030) — replaces the claude.ai 10:00 "Daily job email check".

Reads the profile's Gmail (config/profile.json accounts.gmail) over IMAP, read-only (EXAMINE + BODY.PEEK: nothing is marked read, moved or sent), for
the last 2 days. Newsletters, surveys and job alerts are skipped. A mail is matched to an application row by company name, classified by keyword rules, appended to
data/store/emails.jsonl, and the row's email fields are updated. Unclear job mails are listed in the log for a
session to read — never guessed. Since 2026-10-30 Claude reads every candidate mail (claude_reader.py) and its checked verdict decides; the rules are
the recall filter. When the Claude read fails the rules change nothing: the mail is stored as Pending (no stage, type or
application) and read again by later runs, which then apply Claude's verdict in full; reads failing > 2 h in a row push
one alert (reader_health.py, JSA-280 ①). --no-claude = rules decide alone. A rejection closes the row, an assessment invite moves Applied → Assessment;
interview / offer / action mails set action_needed and are pushed to Joey, as are unmatched and unsure ones. Never changes applied_on, never creates application rows, never drafts or sends.

Credential: a Google app password in the macOS Keychain (Joey creates it; an agent never sees it in chat):
  security add-generic-password -s jobagent-gmail -a <your gmail> -w
usage: python3 scripts/daily/email_check.py [--days 2] [--no-git] [--no-notify] [--dry-run] [--no-claude] [--reread]

Runs every 30 min in the day (JSA-140): each message is read once. data/runner/daily/seen_email.json keeps every message
id already handled (7 days), so a run with no new mail makes no Claude call and pushes nothing; an unmatched job mail is
read again only when the tracker has gained rows since (it may match now) and is pushed only the first time; a message
whose Claude read failed is tried again next run. --reread ignores the record.
"""
import datetime, email, json, email.header, email.utils, html, imaplib, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, os.path.join(ROOT, "scripts", "store"))
sys.path.insert(0, HERE)
import store  # noqa: E402
import next_step  # noqa: E402  (JSA-265)

sys.path.insert(0, os.path.join(ROOT, "config"))
import jsa_profile  # noqa: E402  (JSA-077)
ACCOUNT = jsa_profile.get("accounts.gmail")
KEYCHAIN = "jobagent-gmail"
TODAY = datetime.date.today()
ATS = re.compile(r"greenhouse|myworkday|workday|lever\.co|ashbyhq|smartrecruiters|icims|workable|jobvite|successfactors|"
                 r"taleo|eightfold|oraclecloud|avature|recruitee|bamboohr|rippling|gem\.com|hire\.|talent|recruit", re.I)
IGNORE = re.compile(r"security code|survey|feedback matters|verification code|verify your (email|candidate account|account)|job alert|jobs? you may be interested|one-time (pass)?code|password reset|sign-in code", re.I)
# a subject that says the application arrived is a confirmation, even when the body explains every later status
# ("Not Selected … we will not be moving forward" in a Workday employer's process legend, 2026-10-30)
RECEIVED_SUBJECT = re.compile(r"received your application|application (was |has been )?(received|submitted)", re.I)
# a saved-but-unsent application ("We saved a draft … continue to apply", Goldman 11-05) is not a confirmation (JSA-280)
DRAFT = re.compile(r"saved a draft|continue to apply|complete and submit your (job )?application|finish (your|the) application", re.I)
# a conditional sentence names a later step, it is not an invite: "the next step may include a HireVue interview",
# "if selected … HackerRank", "we will contact you to schedule an interview" (EQT, a Greenhouse employer, an employer, Verition, an employer — JSA-280)
CONDITIONAL = re.compile(r"\b(if|may|might|should you|once|upon|whether)\b|candidates who|will (contact|reach out|be in touch)|"
                         r"we will (contact|reach)|potential fit|how to prepare|to equip you", re.I)
RULES = [  # first match wins
    ("Rejection", re.compile(r"not (be )?moving forward|unfortunately|other candidates|decided not to|no longer (under )?consider|"
                             r"decision not to move (you )?forward|(not|unable) (be )?able to (move|proceed) forward|unable to move forward|"
                             r"position has been filled|will not be (moving|proceeding)|not been selected|regret to inform|"
                             r"closed the .{0,60}(role|position)|pursue other|not to proceed|"
                             r"(decided|chosen|chose) to (move|go) forward with (other |another )?candidates|more closely (match|align)", re.I)),
    ("Assessment", re.compile(r"assessment|hackerrank|codesignal|coderpad|codility|hirevue|online test|coding (challenge|exercise)|"
                              r"take-home", re.I)),
    ("Interview", re.compile(r"interview|phone screen|schedule (a|your) (call|time|conversation)|your availability|"
                             r"recruiter (call|chat)", re.I)),
    ("Action", re.compile(r"additional info|action required|complete (the|this|a) .{0,40}form|please (provide|submit|complete)|"
                          r"required information", re.I)),
    ("Confirmation", re.compile(r"thank(s| you) for (applying|your application|your interest|submitting)|application (was |has been )?"
                                r"(received|submitted)|we (have )?received your (job )?application", re.I)),
]
SUFFIX = re.compile(r"\b(inc|llc|corp|corporation|co|company|ltd|group|the|technologies|technology|labs?|holdings)\b")


def norm(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower().replace("&", " and "))
    return " ".join(SUFFIX.sub(" ", s).split())


GENERIC = {"data", "ai", "open", "general", "american", "united", "first", "national", "global", "new", "north", "south",
           "capital", "digital", "health", "energy", "systems", "solutions", "bank", "one", "blue", "red", "green", "san"}


_WORDS = None


def english(w):
    """True for an ordinary English word (macOS /usr/share/dict/words, lower-case entries only) or a GENERIC one."""
    global _WORDS
    if _WORDS is None:
        try:
            _WORDS = {x.strip() for x in open("/usr/share/dict/words") if x[:1].islower()}
        except OSError:
            _WORDS = set()
    return w in GENERIC or w in _WORDS


def keys(company, firsts=None):
    """Names a mail may use for this company: (full normalised name, first word or ""). The first word counts only when
    it is distinctive (JSA-280): ≥ 3 letters, not an English word, and no other company in the tracker starts with it
    ("a Greenhouse employer" → imc; never "applied", "base", "human"). firsts = {first word: number of companies}."""
    c = norm(company)
    first = c.split()[0] if c else ""
    if first == c or len(first) < 3 or english(first) or (firsts or {}).get(first, 1) > 1:
        first = ""
    return c, first


def domain_labels(sender):
    m = re.search(r"@([\w.-]+)", sender or "")
    return set(m.group(1).lower().split(".")) if m else set()


STOP = {"intern", "internship", "interns", "summer", "2025", "2026", "2027", "2028", "program", "the", "and", "of", "for", "a",
        "in", "to", "at", "new", "grad", "early", "career", "co", "op", "s", "role", "position"}


def stems(text):
    """Title words, stemmed by their first 5 letters (Science / Scientist, Analyst / Analytics)."""
    return {w[:5] for w in norm(text).split() if w not in STOP}


def dec(v):
    return "".join(t.decode(c or "utf-8", "replace") if isinstance(t, bytes) else t for t, c in email.header.decode_header(v or ""))


def text_of(msg):
    parts = [p for p in msg.walk() if p.get_content_type() in ("text/plain", "text/html") and not p.get_filename()]
    parts.sort(key=lambda p: p.get_content_type() != "text/plain")
    for p in parts:
        raw = p.get_payload(decode=True) or b""
        t = raw.decode(p.get_content_charset() or "utf-8", "replace")
        if p.get_content_type() == "text/html":
            t = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(style|script).*?</\1>", " ", t)))
        return " ".join(t.split())
    return ""


def plain(text):
    """The text without its conditional sentences (JSA-280): only what the mail says now is an invite."""
    return " ".join(x for x in re.split(r"(?<=[.!?])\s+", text) if not CONDITIONAL.search(x))


def classify(subject, body):
    blob = f"{subject} {body[:4000]}"
    if IGNORE.search(subject):
        return None
    if DRAFT.search(blob):
        return "Other"
    if RECEIVED_SUBJECT.search(subject):
        return "Confirmation"
    if RULES[0][1].search(blob):
        return "Rejection"
    now = f"{subject} {plain(body[:4000])}"
    return next((t for t, rx in RULES[1:] if rx.search(now)), "Other")


def match(apps, sender, subject, body, date=""):
    """The applied row this mail is about, or None (JSA-280). The full company name in sender / subject, or in the body
    of a mail sent by an ATS / careers address; the distinctive first word (keys) only in sender / subject, and only
    when the sender is an ATS or the word is a label of the sender's domain (imc.com). Several rows → the most title
    words in common (stemmed), then the row applied most recently on or before the mail date; rows applied after the
    mail come last."""
    head, start = norm(sender + " " + subject), norm(body[:3000])
    ats = bool(ATS.search(sender))
    live = [a for a in apps if a.get("status") not in ("Shortlisted", "Archived")]   # never applied (JSA-013)
    firsts = {}
    for c in {norm(a["company"]) for a in live}:
        if c:
            firsts[c.split()[0]] = firsts.get(c.split()[0], 0) + 1
    labels = domain_labels(sender)
    has = lambda k, t: bool(k) and re.search(rf"\b{re.escape(k)}\b", t)   # noqa: E731
    cands = []
    for a in live:
        full, first = keys(a["company"], firsts)
        if has(full, head) or (ats and has(full, start)) or (first and has(first, head) and (ats or first in labels)):
            cands.append(a)
    if len(cands) > 1:
        words = stems(subject + " " + body[:1500])
        day = date or "9999"
        cands.sort(key=lambda a: (-len(words & stems(a["title"])), (a.get("applied_on") or "") > day,
                                  "".join(chr(0x10FFFF - ord(ch)) for ch in (a.get("applied_on") or ""))))
    return cands[0] if cands else None


def pick_same_company(ids, apps, emails, kind):
    """Pure (tested). A mail that names the company but not the role, when Joey applied to several roles there: a
    Confirmation goes to the earliest-applied of those rows that has no Confirmation yet (ties → job_id order);
    any other type, no ids, or every row already confirmed → None (stays unmatched for Joey)."""
    if kind != "Confirmation" or not ids:
        return None
    by = {a.get("job_id"): a for a in apps}
    done = {e.get("job_id") for e in emails if e.get("type") == "Confirmation"}
    rows = sorted((by[i] for i in dict.fromkeys(ids) if i in by and i not in done),
                  key=lambda a: (a.get("applied_on") or "", a.get("job_id") or ""))
    return rows[0] if rows else None


def summary_of(kind, company, subject, body):
    first = re.split(r"(?<=[.!?])\s", body[:600])
    lead = next((s for s in first if len(s) > 40 and not re.match(r"(?i)(hi|dear|hello)\b", s)), subject)
    return f"{company}: {lead[:220]}" if kind != "Confirmation" else f"{company}: application received ({subject[:120]})"


# wide recall filter: a message that uses one of these words (or comes from an ATS, or names an applied company) is
# worth a careful read; everything else (personal mail) is never sent anywhere
JOBWORDS = re.compile(r"applica|interview|recruit|hiring|talent|candida|position|\brole\b|intern(ship)?\b|assessment|hirevue|"
                      r"offer|onboard|phone screen|next step|background check|\bHR\b|human resources|requisition", re.I)


def _row(a, m, kind, summary, action, deadline=""):
    row = {"id": m["id"], "date": m["date"], "company": a["company"], "role": a["title"],
           "type": "Other" if kind == "Action" else kind, "subject": m["subject"], "summary": summary,
           "action": action, "deadline": deadline, "job_id": a["job_id"], "url": m["url"]}
    if m.get("channel"):
        row["channel"] = m["channel"]
    return row


def _record(apps, emails, a, m, row, kind, move=True):
    emails.append(row)
    if (a.get("last_email_date") or "") <= m["date"]:
        a.update(last_email=row["summary"], last_email_date=m["date"], email_url=m["url"], updated=TODAY.isoformat())
        if row["action"]:
            a.update(action_needed=row["action"], action_deadline=row.get("deadline", ""))
    # a rejection closes the row; an assessment invite moves Applied → Assessment (a Workday employer HireVue 2026-10-30);
    # an interview / offer mail is flagged for Joey and a session
    if not move:
        return row
    before = {"stage_before": a.get("status", ""), "next_before": a.get("next_step", "")}
    if kind == "Rejection" and a.get("status") not in ("Rejected", "Withdrawn", "Offer", "Declined by Joey"):
        a.update(status="Rejected", next_step=f"Closed — rejected {m['date']}")
        row.update(before)                    # kept so a later re-read can undo exactly this move (JSA-281)
    elif kind == "Assessment" and a.get("status") in ("Applied", "Applied (unconfirmed)"):
        a.update(status="Assessment", next_step=f"Complete the assessment (invite {m['date']}) — see the email")
        row.update(before)
    return row


PENDING = "Pending"   # emails.type of a mail Claude could not read yet (JSA-281): it changes nothing in the tracker


def _pending(a, m, kind, err):
    """The row for a mail whose Claude read failed (JSA-281 layer A): stored so a later run re-reads it, but attached to
    no application — the rules' guesses are kept apart (rules_type / rules_job_id) and change no stage, type or
    last_email. A rejection waits too (Joey 2026-11-10: 规则只记录信、不改阶段 / 类型 / 归属)."""
    who = a["company"] if a else (re.sub(r"\s*<[^>]*>", "", m.get("sender", "")).strip(' "') or m.get("sender", "") or "?")
    row = {"id": m["id"], "date": m["date"], "company": who, "role": a["title"] if a else "", "type": PENDING,
           "subject": m["subject"], "summary": f"{who}: not read by Claude yet ({type(err).__name__}) — the rules guess {kind}",
           "action": "", "deadline": "", "job_id": "", "url": m["url"], "reader": "pending", "reread": True,
           "rules_type": kind, "rules_job_id": a["job_id"] if a else ""}
    if m.get("channel"):
        row["channel"] = m["channel"]
    return row


def step_of(kind, m, claude_action="", claude_deadline=""):
    """The action written for a mail (JSA-265): Claude's own step when it is concrete, else the rules' step from the mail
    type + the deadline / platform / request sentence found in the text. Never the old generic line.
    Returns (action, deadline, reread) — reread = no concrete step could be found, a later run should read it again."""
    if not next_step.is_vague(claude_action):
        return claude_action, claude_deadline, False
    r = next_step.rules_action(kind, m.get("subject", ""), m.get("body", ""), m["date"])
    return r["action"], claude_deadline or r["deadline"], r["reread"]


def refresh_action(apps, erow, action, deadline):
    """Re-read result for a stored mail row (JSA-265 backfill / reread): rewrite its `action` / `deadline`, and the
    application's `action_needed` / `action_deadline` only while that still shows this mail's old (or the generic) step —
    a step Joey marked done (action_done) or a newer mail's step is left alone. Returns True when the row changed."""
    old = erow.get("action", "")
    a = next((x for x in apps if x.get("job_id") == erow.get("job_id")), None)
    erow.update(action=action, deadline=deadline or erow.get("deadline", ""))
    erow.pop("reread", None)
    cur = (a or {}).get("action_needed") or ""
    if a and cur and (cur == old or cur == next_step.OLD_GENERIC):
        if action:
            a.update(action_needed=action, action_deadline=erow["deadline"])
        else:
            a.update(action_needed="")
            a.pop("action_deadline", None)
    return action != old


def apply_verdict(apps, emails, m, v, kind, notes):
    """Claude's checked verdict → the tracker (the one path for a fresh read and a re-read). Returns the new email row,
    {'unmatched': …}, or None (not a job mail). `kind` = the rules' type, only used to log a disagreement."""
    if v["type"] != kind and not (v["type"] == "NotJob" and kind == "Other"):
        notes.setdefault("disagree", []).append(f"{m['subject'][:60]}: rules {kind} → Claude {v['type']} ({v['reason'][:90]})")
    if v["type"] == "NotJob":
        return None
    if not v["job_id"]:
        same = pick_same_company(v.get("company_job_ids") or [], apps, emails, v["type"])
        if same:
            v["job_id"] = same["job_id"]
            notes.setdefault("same_company", []).append(f"{same['company']}: {m['subject'][:60]} → {same['title'][:50]}")
    if not v["job_id"]:
        return {"unmatched": True, "kind": v["type"], "subject": m["subject"], "sender": m["sender"],
                "summary": v["summary"], "reason": v["reason"]}
    a = next(x for x in apps if x.get("job_id") == v["job_id"])
    unsure = v["confidence"] == "low"
    action, deadline, again = step_of(v["type"], m, v["action_needed"], v.get("deadline", ""))
    if unsure:
        action = f"请确认（Claude 不确定）：{v['type']} — {v['reason'][:120]}"
        notes.setdefault("unsure", []).append(f"{a['company']}: {v['type']}? {m['subject'][:60]}")
    row = _row(a, m, v["type"], f"{a['company']}: {v['summary'][:220]}", action, deadline)
    row.update(reader="claude", confidence=v["confidence"])
    if again and not unsure:
        row["reread"] = True
    return _record(apps, emails, a, m, row, v["type"], move=not unsure)


def _undo(apps, emails, old):
    """Take a stored row back out of the tracker before its re-read is applied (JSA-281 layer C): remove it, undo the
    stage move it made (only when the application still shows exactly that move), and give the application back the
    last_email / action of its newest remaining mail. applied_on is never touched."""
    emails[:] = [e for e in emails if e is not old]
    a = next((x for x in apps if old.get("job_id") and x.get("job_id") == old["job_id"]), None)
    if a is None:
        return None
    day = old.get("date", "")
    marks = {"Rejection": ("Rejected", f"Closed — rejected {day}"),
             "Assessment": ("Assessment", f"Complete the assessment (invite {day}) — see the email")}
    st = marks.get(old.get("type"))
    if st and a.get("status") == st[0] and (a.get("next_step") or "") == st[1]:
        a.update(status=old.get("stage_before") or "Applied", next_step=old.get("next_before", ""))
    if old.get("action") and (a.get("action_needed") or "") == old["action"]:
        a["action_needed"] = ""
        a.pop("action_deadline", None)
    if a.get("last_email_date") == old.get("date") and a.get("last_email") == old.get("summary"):
        rest = sorted((e for e in emails if e.get("job_id") == a["job_id"]), key=lambda e: e.get("date") or "")
        if rest:
            a.update(last_email=rest[-1].get("summary", ""), last_email_date=rest[-1].get("date", ""), email_url=rest[-1].get("url", ""))
        else:
            a.update(last_email="暂无回应", last_email_date="", email_url="")
    return a


def reapply(apps, emails, m, old, v, notes):
    """A re-read applies Claude's verdict fully (JSA-281 layer C): undo what the stored row did, then the same path as a
    fresh read — stage forward and back, emails.type, job_id, action. A step Joey already marked done (or a newer mail's
    step) on the same application is kept, as in refresh_action."""
    a_old = next((x for x in apps if old.get("job_id") and x.get("job_id") == old["job_id"]), None)
    cur = (a_old or {}).get("action_needed") or ""
    keep = a_old is not None and bool(old.get("action")) and cur not in (old["action"], next_step.OLD_GENERIC)
    snap = {k: a_old[k] for k in ("action_needed", "action_deadline") if k in a_old} if keep else {}
    _undo(apps, emails, old)
    r = apply_verdict(apps, emails, m, v, old.get("rules_type") or old.get("type"), notes)
    if keep and r and r.get("job_id") == a_old.get("job_id"):
        a_old.pop("action_deadline", None)
        a_old.update(snap)
    new = (r or {}).get("type") or ("NotJob" if r is None else "unmatched")
    notes.setdefault("reread", []).append(f"{m['subject'][:60]}: {old.get('type')} → {new}")
    return r


def apply_mail(apps, emails, m, reader=None, notes=None):
    """Update step (tested): returns the new email row, {'unmatched': …}, or None. Mutates the matched application row.
    With a reader (claude_reader.Reader) every candidate message is read by Claude and its checked verdict decides; the
    keyword rules are the recall filter. When the read fails the mail is stored as Pending (no stage / type / application
    change) and read again by a later run (JSA-281). reader=None (--no-claude) = the rules decide on their own.
    `notes` collects fallbacks / disagreements / unsure rows / re-reads."""
    notes = notes if notes is not None else {}
    old = next((e for e in emails if e["id"] == m["id"]), None)
    if old is not None:
        if old.get("reread") and reader is not None:     # Pending, or a step the rules could not find (JSA-265 / 281)
            try:
                v = reader.read(m)
            except Exception as e:
                notes.setdefault("fallback", []).append(f"{m['subject'][:60]}: re-read {type(e).__name__} {str(e)[:80]}")
                return None
            return reapply(apps, emails, m, old, v, notes)
        return None
    kind = classify(m["subject"], m["body"])
    if kind is None:
        return None                               # security codes, surveys, job alerts — never read further
    ats = bool(ATS.search(m["sender"]))
    if m.get("bulk") and not ats:
        return None  # newsletters, surveys, job alerts, school career mail — even when the sender is the company (JSA-280)
    a = match(apps, m["sender"], m["subject"], m["body"], m.get("date", ""))
    if reader is not None and (a or ats or JOBWORDS.search(m["subject"] + " " + m["body"][:4000])):
        try:
            v = reader.read(m)
        except Exception as e:
            notes.setdefault("fallback", []).append(f"{m['subject'][:60]}: {type(e).__name__} {str(e)[:80]}")
            if a or ats:
                emails.append(_pending(a, m, kind, e))
            return None                           # nothing else changes; not marked seen, so the next run reads it
        return apply_verdict(apps, emails, m, v, kind, notes)
    if not a:
        return {"unmatched": True, "kind": kind, "subject": m["subject"], "sender": m["sender"]} if ats else None
    action, deadline, again = step_of(kind, m)
    row = _row(a, m, kind, summary_of(kind, a["company"], m["subject"], m["body"]), action, deadline)
    if again:
        row["reread"] = True
    return _record(apps, emails, a, m, row, kind)


SEEN_DAYS = 7


def seen_path(channel):
    return jpaths.data("runner", "daily", f"seen_{channel}.json")


def load_seen(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return {}                                 # no record (first run, or lost) → read the window once more


def save_seen(path, seen, today=None):
    """Drop entries older than SEEN_DAYS (the fetch window is 2 days), write atomically."""
    cut = ((today or TODAY) - datetime.timedelta(days=SEEN_DAYS)).isoformat()
    keep = {k: v for k, v in seen.items() if v.get("on", "") >= cut}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(keep, f, indent=0, sort_keys=True)
    os.replace(path + ".tmp", path)
    return keep


def run_new(items, apply, seen, notes, n_apps, reread=False, today=None):
    """Step (tested): apply(item) to each item not handled before. Skips an id in `seen`, except an 'unmatched' entry
    recorded when the tracker had fewer rows than n_apps. Records every handled item ({on, kind, apps}) unless its
    Claude read failed (a new notes['fallback'] line) — that one is tried again. Returns (results, pushable unmatched,
    number handled); an unmatched result already recorded as unmatched is not pushed again."""
    out, push, n = [], [], 0
    for m in items:
        old = seen.get(m["id"])
        if old and not reread and not (old.get("kind") == "unmatched" and n_apps > old.get("apps", 0)):
            continue
        n += 1
        before = len(notes.get("fallback", []))
        r = apply(m)
        if len(notes.get("fallback", [])) == before:
            seen[m["id"]] = {"on": (today or TODAY).isoformat(), "apps": n_apps,
                             "kind": "unmatched" if r and r.get("unmatched") else "done"}
        if r:
            out.append(r)
            if r.get("unmatched") and not (old and old.get("kind") == "unmatched"):
                push.append(r)
    return out, push, n


def touch_waiting(apps):
    for a in apps:
        if a.get("status") in ("Applied", "Applied (unconfirmed)", "Assessment"):
            if not a.get("last_email"):
                a["last_email"] = "暂无回应"
            if a.get("applied_on"):
                a["days_since_applied"] = (TODAY - datetime.date.fromisoformat(a["applied_on"])).days
            a["last_checked"] = TODAY.isoformat()


def _imap():
    pw = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN, "-a", ACCOUNT, "-w"],
                        capture_output=True, text=True).stdout.strip()
    if not pw:
        raise LookupError("no Gmail app password in the Keychain (service jobagent-gmail)")
    im = imaplib.IMAP4_SSL("imap.gmail.com")
    im.login(ACCOUNT, pw)
    im.select('"[Gmail]/All Mail"', readonly=True)
    return im


def fetch_ids(gids):
    """The stored messages with these Gmail ids (hex, as in emails.jsonl), read-only — for the JSA-265 backfill."""
    im, nums = _imap(), []
    for g in gids:
        _, ids = im.search(None, "X-GM-MSGID", str(int(g, 16)))
        nums += ids[0].split()
    return _read(im, nums)


def fetch(days):
    im = _imap()
    _, ids = im.search(None, "X-GM-RAW", f'"newer_than:{days}d -from:me -category:promotions"')
    return _read(im, ids[0].split())


def _read(im, nums):
    out = []
    for n in nums:
        _, d = im.fetch(n, "(X-GM-MSGID BODY.PEEK[])")
        meta = d[0][0].decode()
        gid = format(int(re.search(r"X-GM-MSGID (\d+)", meta).group(1)), "x")
        msg = email.message_from_bytes(d[0][1])
        dt = email.utils.parsedate_to_datetime(msg["Date"]).astimezone()
        out.append({"id": gid, "date": dt.date().isoformat(), "sender": dec(msg["From"]), "subject": dec(msg["Subject"]),
                    "bulk": bool(msg["List-Unsubscribe"] or msg["List-Id"]) or (msg["Precedence"] or "").lower() in ("bulk", "list"),
                    "body": text_of(msg), "url": f"https://mail.google.com/mail/?authuser={ACCOUNT}#all/{gid}"})
    im.logout()
    return out


def main(a):
    from run_daily import log, git_publish  # same log file and the same commit-only-data/store rule
    from notify import notify
    days = int(a[a.index("--days") + 1]) if "--days" in a else 2
    log("email start")
    try:
        mails = fetch(days)
    except Exception as e:
        log(f"email FAILED: {e}")
        if "--no-notify" not in a:
            notify(f"邮件核对失败 {TODAY}", f"{str(e)[:200]}\n申请台账未改动。")
        return 1
    if "--dry-run" not in a:
        confirm_receipts(log)
        sync_tracker(log)
    apps, emails = store.load("applications"), store.load("emails")
    reader, notes = make_reader(apps, log, a), {}
    rd = tracked(reader)
    if rd is not None and rd.reader is not None:
        mails += older_pending(emails, mails, "email", fetch_ids, log)
    sp = seen_path("email")
    seen = load_seen(sp)
    new, push, handled = run_new(mails, lambda m: apply_mail(apps, emails, m, rd, notes), seen, notes, len(apps),
                                 "--reread" in a)
    health(rd, log, "--no-notify" not in a and "--dry-run" not in a, "--dry-run" in a)
    unmatched = [r for r in new if r.get("unmatched")]
    rows = [r for r in new if not r.get("unmatched")]
    touch_waiting(apps)
    if "--dry-run" not in a:
        store.save("applications", apps)
        store.save("emails", emails)
        save_seen(sp, seen)
    for u in unmatched:
        log(f"unmatched job mail ({u['kind']}): {u['sender'][:60]} · {u['subject'][:80]}")
    pub = "skipped" if "--no-git" in a or "--dry-run" in a else git_publish(f"data: email {TODAY} (+{len(rows)} mails)")
    log(f"email ok · {len(mails)} in window · {handled} new · {len(rows)} matched · {len(unmatched)} unmatched · git: {pub}")
    report(f"求职邮件 {TODAY}", rows, push, notes, reader, log, "--no-notify" not in a)
    return 0


def older_pending(emails, items, channel, fetch_by_id, log):
    """Pending rows (JSA-281) whose message has left the fetch window: fetch them by id so a long outage is still
    re-read once Claude is back. channel 'email' = rows without a channel, 'sms' = channel sms."""
    have = {m["id"] for m in items}
    ids = [e["id"] for e in emails if e.get("reader") == "pending" and e.get("reread") and e["id"] not in have
           and (e.get("channel") == "sms") == (channel == "sms")]
    if not ids:
        return []
    try:
        got = fetch_by_id(ids)
    except Exception as e:
        log(f"pending re-read fetch failed ({type(e).__name__}: {str(e)[:120]}) — tried again next run")
        return []
    log(f"pending re-read: {len(got)} of {len(ids)} older messages fetched")
    return got


def confirm_receipts(log):
    """JSA-193 step 8: a Submit the page did not confirm (results.jsonl `unconfirmed`) is confirmed by its company receipt e-mail
    when it arrives later; none after 48 h → one queue line for Joey. Never stops the mail check."""
    try:
        import receipt_confirm
        r = receipt_confirm.run(log=log)
        if r['confirmed'] or r['joey']:
            log(f"receipts: {len(r['confirmed'])} confirmed by e-mail · {len(r['joey'])} without receipt in 48 h → Joey")
    except Exception as e:
        log(f"receipt_confirm failed ({type(e).__name__}: {str(e)[:120]}) — tried again next run")


def sync_tracker(log):
    """Submitted runner results → tracker rows before the mail is read (JSA-280 ②): a confirmation that arrives minutes
    after a submit (an employer 11-05 23:44, row written 00:00) then finds its own row instead of another company's."""
    try:
        import sync_results
        sync_results.run(log=log)
    except Exception as e:
        log(f"sync_results before reading failed ({type(e).__name__}: {str(e)[:120]}) — reading with the tracker as it is")


def tracked(reader):
    """The reader every apply step gets (JSA-281): None only for --no-claude (rules decide); an unavailable reader
    (no key / SDK) becomes one whose every read fails, so mail waits as Pending instead of being decided by the rules."""
    import reader_health
    if reader is None:
        return None
    if isinstance(reader, dict):
        return reader_health.Tracked(down=LookupError(reader["unavailable"]))
    return reader_health.Tracked(reader)


def health(rd, log, push=True, dry=False):
    """Record this run's Claude reads in reader_health.json; one push once they have failed > 2 h in a row (JSA-280)."""
    if rd is None or not (rd.fails or rd.oks):
        return None
    import reader_health
    if dry:
        return None
    alert = reader_health.record(rd.fails, rd.oks, push=push)
    if alert:
        log(f"reader alert: {alert[0]} · {alert[1][:160]}")
    return alert


def make_reader(apps, log, a):
    """Claude reader unless --no-claude; None (rules only) when the key or the SDK is missing — reported, not silent."""
    if "--no-claude" in a:
        return None
    try:
        from claude_reader import Reader
        return Reader(apps, log=log)
    except Exception as e:
        log(f"claude reader unavailable ({type(e).__name__}: {str(e)[:120]}) — rules only")
        return {"unavailable": f"{type(e).__name__}: {str(e)[:120]}"}


def report(title, rows, unmatched, notes, reader, log, push=True):
    """Log what Claude did and push everything Joey must see: news, unmatched job mail, unsure verdicts, fallbacks."""
    if isinstance(reader, dict):
        notes.setdefault("fallback", []).insert(0, f"Claude 没有运行：{reader['unavailable']}")
    elif reader is not None and getattr(reader, "usage", {}).get("calls"):
        u = reader.usage
        log(f"claude {u['calls']} calls · input {u['input']} (+{u['cache_read']} cached) · output {u['output']} tokens")
    for k in ("disagree", "unsure", "fallback", "same_company", "reread"):
        for line in notes.get(k, []):
            log(f"{k}: {line}")
    news = [r for r in rows if r["type"] != "Confirmation"]
    lines = [f"· {r['type']} — {r['company']}: {(r.get('summary') or r['subject'])[:90]}" for r in news[:10]]
    lines += [f"· 没对上申请（{u['kind']}）: {(u.get('summary') or u['subject'])[:90]}" for u in unmatched[:5]]
    lines += [f"· 请确认: {x}" for x in notes.get("unsure", [])[:5]]
    if notes.get("fallback"):
        lines.append(f"· {len(notes['fallback'])} 条 Claude 没读成，记为待读、不改阶段，下轮重读（见 data/runner/daily/{TODAY}.md）")
    if notes.get("reread"):
        lines.append(f"· 重读 {len(notes['reread'])} 条: " + "; ".join(x[:60] for x in notes["reread"][:3]))
    if lines and push:
        from notify import notify
        notify(title, "\n".join(lines))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
