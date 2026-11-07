"""Local daily job-email check (ADR-0004, JSA-030) — replaces the claude.ai 10:00 "Daily job email check".

Reads the profile's Gmail (config/profile.json accounts.gmail) over IMAP, read-only (EXAMINE + BODY.PEEK: nothing is marked read, moved or sent), for
the last 2 days. Newsletters, surveys and job alerts are skipped. A mail is matched to an application row by company name, classified by keyword rules, appended to
data/store/emails.jsonl, and the row's email fields are updated. Unclear job mails are listed in the log for a
session to read — never guessed. Since 2026-10-30 Claude reads every candidate mail (claude_reader.py) and its checked verdict decides; the rules are
the recall filter and the fallback. A rejection closes the row, an assessment invite moves Applied → Assessment;
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
RULES = [  # first match wins
    ("Rejection", re.compile(r"not (be )?moving forward|unfortunately|other candidates|decided not to|no longer (under )?consider|"
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
                                r"(received|submitted)|we (have )?received your application", re.I)),
]
SUFFIX = re.compile(r"\b(inc|llc|corp|corporation|co|company|ltd|group|the|technologies|technology|labs?|holdings)\b")


def norm(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower().replace("&", " and "))
    return " ".join(SUFFIX.sub(" ", s).split())


GENERIC = {"data", "ai", "open", "general", "american", "united", "first", "national", "global", "new", "north", "south",
           "capital", "digital", "health", "energy", "systems", "solutions", "bank", "one", "blue", "red", "green", "san"}


def keys(company):
    """Names a mail may use for this company: the full normalised name, plus its first word when distinctive
    ("a Greenhouse employer" → imc trading, imc)."""
    c = norm(company)
    first = c.split()[0] if c else ""
    return [k for k in {c, first if len(first) >= 3 and first not in GENERIC else ""} if k]


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


def classify(subject, body):
    blob = f"{subject} {body[:4000]}"
    if IGNORE.search(subject):
        return None
    if RECEIVED_SUBJECT.search(subject):
        return "Confirmation"
    return next((t for t, rx in RULES if rx.search(blob)), "Other")


def match(apps, sender, subject, body):
    """The applied row this mail is about, or None. Company must appear in sender/subject, or in the body of a mail
    sent by an ATS / careers address. Several rows at one company → the one whose title words overlap most."""
    head, start = norm(sender + " " + subject), norm(body[:3000])
    ats = bool(ATS.search(sender))
    cands = []
    for a in apps:
        if a.get("status") in ("Shortlisted", "Archived"):   # never applied (Archived: JSA-013, 2026-11-05)
            continue
        names = keys(a["company"])
        if any(re.search(rf"\b{re.escape(c)}\b", head) or (ats and re.search(rf"\b{re.escape(c)}\b", start)) for c in names):
            cands.append(a)
    if len(cands) > 1:
        words = set(norm(subject + " " + body[:1500]).split())
        cands.sort(key=lambda a: (-len(words & set(norm(a["title"]).split())), a.get("applied_on") or ""))
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
    return {"id": m["id"], "date": m["date"], "company": a["company"], "role": a["title"],
            "type": "Other" if kind == "Action" else kind, "subject": m["subject"], "summary": summary,
            "action": action, "deadline": deadline, "job_id": a["job_id"], "url": m["url"]}


def _record(apps, emails, a, m, row, kind, move=True):
    emails.append(row)
    if (a.get("last_email_date") or "") <= m["date"]:
        a.update(last_email=row["summary"], last_email_date=m["date"], email_url=m["url"],
                 action_needed=row["action"] or a.get("action_needed", ""), updated=TODAY.isoformat())
    # a rejection closes the row; an assessment invite moves Applied → Assessment (a Workday employer HireVue 2026-10-30);
    # an interview / offer mail is flagged for Joey and a session
    if not move:
        return row
    if kind == "Rejection" and a.get("status") not in ("Rejected", "Withdrawn", "Offer"):
        a.update(status="Rejected", next_step=f"Closed — rejected {m['date']}")
    elif kind == "Assessment" and a.get("status") in ("Applied", "Applied (unconfirmed)"):
        a.update(status="Assessment", next_step=f"Complete the assessment (invite {m['date']}) — see the email")
    return row


def apply_mail(apps, emails, m, reader=None, notes=None):
    """Update step (tested): returns the new email row, {'unmatched': …}, or None. Mutates the matched application row.
    With a reader (claude_reader.Reader) every candidate message is read by Claude and its checked verdict decides;
    the keyword rules are the recall filter and the fallback. `notes` collects fallbacks / disagreements / unsure rows."""
    notes = notes if notes is not None else {}
    if any(e["id"] == m["id"] for e in emails):
        return None
    kind = classify(m["subject"], m["body"])
    if kind is None:
        return None                               # security codes, surveys, job alerts — never read further
    ats = bool(ATS.search(m["sender"]))
    a = match(apps, m["sender"], m["subject"], m["body"])
    if m.get("bulk") and kind not in ("Rejection", "Confirmation") and not ats and not a:
        return None  # newsletters, surveys, job alerts, school career mail
    if reader is not None and (a or ats or JOBWORDS.search(m["subject"] + " " + m["body"][:4000])):
        try:
            v = reader.read(m)
        except Exception as e:
            notes.setdefault("fallback", []).append(f"{m['subject'][:60]}: {type(e).__name__} {str(e)[:80]}")
        else:
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
            action = v["action_needed"] or ("Read the email and act — see the link" if v["type"] in ("Action", "Assessment", "Interview", "Offer") else "")
            if unsure:
                action = f"请确认（Claude 不确定）：{v['type']} — {v['reason'][:120]}"
                notes.setdefault("unsure", []).append(f"{a['company']}: {v['type']}? {m['subject'][:60]}")
            row = _row(a, m, v["type"], f"{a['company']}: {v['summary'][:220]}", action, v.get("deadline", ""))
            row.update(reader="claude", confidence=v["confidence"])
            return _record(apps, emails, a, m, row, v["type"], move=not unsure)
    if not a:
        return {"unmatched": True, "kind": kind, "subject": m["subject"], "sender": m["sender"]} if ats else None
    row = _row(a, m, kind, summary_of(kind, a["company"], m["subject"], m["body"]),
               "Read the email and act — see the link" if kind in ("Action", "Assessment", "Interview") else "")
    if reader is not None:
        row["reader"] = "rules"
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


def fetch(days):
    pw = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN, "-a", ACCOUNT, "-w"],
                        capture_output=True, text=True).stdout.strip()
    if not pw:
        raise LookupError("no Gmail app password in the Keychain (service jobagent-gmail)")
    im = imaplib.IMAP4_SSL("imap.gmail.com")
    im.login(ACCOUNT, pw)
    im.select('"[Gmail]/All Mail"', readonly=True)
    _, ids = im.search(None, "X-GM-RAW", f'"newer_than:{days}d -from:me -category:promotions"')
    out = []
    for n in ids[0].split():
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
    apps, emails = store.load("applications"), store.load("emails")
    reader, notes = make_reader(apps, log, a), {}
    rd = None if isinstance(reader, dict) else reader
    sp = seen_path("email")
    seen = load_seen(sp)
    new, push, handled = run_new(mails, lambda m: apply_mail(apps, emails, m, rd, notes), seen, notes, len(apps),
                                 "--reread" in a)
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
    elif reader is not None and reader.usage["calls"]:
        u = reader.usage
        log(f"claude {u['calls']} calls · input {u['input']} (+{u['cache_read']} cached) · output {u['output']} tokens")
    for k in ("disagree", "unsure", "fallback", "same_company"):
        for line in notes.get(k, []):
            log(f"{k}: {line}")
    news = [r for r in rows if r["type"] != "Confirmation"]
    lines = [f"· {r['type']} — {r['company']}: {(r.get('summary') or r['subject'])[:90]}" for r in news[:10]]
    lines += [f"· 没对上申请（{u['kind']}）: {(u.get('summary') or u['subject'])[:90]}" for u in unmatched[:5]]
    lines += [f"· 请确认: {x}" for x in notes.get("unsure", [])[:5]]
    if notes.get("fallback"):
        lines.append(f"· {len(notes['fallback'])} 条没经过 Claude，按规则处理（见 data/runner/daily/{TODAY}.md）")
    if lines and push:
        from notify import notify
        notify(title, "\n".join(lines))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
