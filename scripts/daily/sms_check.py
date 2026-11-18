"""Local daily job-text check (Joey 2026-10-30: 「还有一些信息可能会通过短信的形式发送」) — the SMS / iMessage twin of
email_check.py.

Reads the Mac's Messages database (~/Library/Messages/chat.db) read-only for the last 2 days: only incoming messages.
A text is kept only when BOTH hold — it names the company of an applied row AND it uses a job word (application,
interview, recruiter, assessment, offer, …) — so personal texts are never written anywhere. Kept texts go through the
same rules as e-mail (email_check.classify / apply_mail): appended to data/store/emails.jsonl with channel "sms",
the row's last-message fields updated, a rejection closes the row, an assessment invite moves Applied → Assessment.
When Claude cannot read a text it is stored as Pending and changes nothing until a later run reads it (JSA-281).
A job-sounding text that names no applied company is listed in the local log (git-ignored) for a session — never guessed.
Verification / security codes are skipped. Never sends, never replies, never marks anything read.

Needs Full Disk Access for the Python that runs it (System Settings → Privacy & Security → Full Disk Access) — macOS
blocks chat.db otherwise; the run then fails loudly with an iMessage and leaves the store untouched. Texts reach the
Mac only when the iPhone forwards them (Settings → Messages → Text Message Forwarding → this Mac).
Claude reads every candidate text (claude_reader.py), as for e-mail; the agent's own pushes to Joey's number are skipped.
usage: python3 scripts/daily/sms_check.py [--days 2] [--db <chat.db>] [--no-git] [--no-notify] [--dry-run] [--no-claude] [--reread]
Each text is read once (data/runner/daily/seen_sms.json, same rules as email_check.run_new; JSA-140).
"""
import datetime, json, os, re, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import email_check as ec  # noqa: E402  (same store, rules and matching)
store = ec.store

DB = os.path.expanduser("~/Library/Messages/chat.db")
APPLE_EPOCH = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
JOB = re.compile(r"applica|interview|recruit|hiring|talent|candida|position|\brole\b|intern(ship)?\b|assessment|hirevue|"
                 r"offer|onboard|phone screen|next step|background check|HR\b|human resources", re.I)
CODE = re.compile(r"\b(verification|security|one-time|login|sign-in|passcode|2fa)\b.{0,30}\bcode\b|\bcode\b.{0,20}\b\d{4,8}\b", re.I)


def decode_body(blob):
    """Newer macOS keeps the text only in attributedBody (an NSAttributedString typedstream): the string follows
    'NSString' + 5 header bytes, prefixed by a 1-, 2- or 3-byte length."""
    if not blob:
        return ""
    i = blob.find(b"NSString")
    if i < 0:
        return ""
    b = blob[i + 8 + 5:]
    if not b:
        return ""
    n, start = b[0], 1
    if n == 0x81:
        n, start = int.from_bytes(b[1:3], "little"), 3
    elif n == 0x82:
        n, start = int.from_bytes(b[1:4], "little"), 4
    return b[start:start + n].decode("utf-8", "replace")


SELECT = """select m.guid, m.date, m.text, m.attributedBody, coalesce(h.id, ''), coalesce(m.service, '')
            from message m left join handle h on m.handle_id = h.ROWID where m.is_from_me = 0 and """


def fetch(days, db=DB):
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    ns = int((since - APPLE_EPOCH).total_seconds() * 1e9)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(SELECT + "m.date > ? order by m.date", (ns,)).fetchall()
    con.close()
    return _texts(rows)


def fetch_ids(ids, db=DB):
    """Stored texts by id ("sms-<guid>") — Pending rows that left the window (JSA-281)."""
    guids = [i[4:] for i in ids if i.startswith("sms-")]
    if not guids:
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(SELECT + f"m.guid in ({','.join('?' * len(guids))}) order by m.date", guids).fetchall()
    con.close()
    return _texts(rows)


def _texts(rows):
    out = []
    for guid, d, text, attr, handle, service in rows:
        body = " ".join((text or decode_body(attr) or "").split())
        if not body:
            continue
        secs = d / 1e9 if d > 1e11 else d          # very old databases store seconds
        dt = (APPLE_EPOCH + datetime.timedelta(seconds=secs)).astimezone()
        out.append({"id": f"sms-{guid}", "date": dt.date().isoformat(), "sender": handle, "service": service,
                    "body": body})
    return out


def own_numbers():
    """Joey's own number: the agent's iMessage pushes to it come back as incoming messages — never read them."""
    p = os.path.join(HERE, "notify.json")
    cfg = json.load(open(p)) if os.path.exists(p) else {}
    return {re.sub(r"\D", "", cfg.get("imessage_to", ""))[-10:]} - {""}


def apply_text(apps, emails, t, reader=None, notes=None, own=frozenset()):
    """Step (tested): returns the new row, {'unmatched': …} for a job-sounding text with no applied row, or None.
    Without a reader the company must be named in the text; with one, Claude decides which application it is."""
    body = t["body"]
    if re.sub(r"\D", "", t["sender"])[-10:] in own:
        return None                               # the agent's own pushes to Joey
    if CODE.search(body) or not JOB.search(body):
        return None                               # codes and everything that is not about a job (personal texts)
    m = {"id": t["id"], "date": t["date"], "sender": t["sender"], "subject": body[:300], "body": body, "bulk": False,
         "url": f"sms:{t['sender']}", "channel": "sms"}
    if reader is None and not ec.match(apps, "", m["subject"], ""):   # the company must be named in the text itself
        return {"unmatched": True, "kind": ec.classify(m["subject"], body) or "Other", "sender": t["sender"], "subject": body[:80]}
    row = ec.apply_mail(apps, emails, m, reader, notes)
    if row and not row.get("unmatched"):
        row["channel"] = "sms"
    return row


def main(a):
    from run_daily import log, git_publish
    from notify import notify
    days = int(a[a.index("--days") + 1]) if "--days" in a else 2
    db = a[a.index("--db") + 1] if "--db" in a else DB
    log("sms start")
    try:
        texts = fetch(days, db)
    except Exception as e:
        why = "没有读取短信的权限（给 Python 开「完全磁盘访问权限」）" if "authorization" in str(e) or "unable to open" in str(e) else str(e)[:200]
        log(f"sms FAILED: {e}")
        if "--no-notify" not in a:
            notify(f"短信核对失败 {ec.TODAY}", f"{why}\n申请台账未改动。")
        return 1
    if "--dry-run" not in a:
        ec.sync_tracker(log)
    apps, emails = store.load("applications"), store.load("emails")
    reader, notes, own = ec.make_reader(apps, log, a), {}, own_numbers()
    rd = ec.tracked(reader)
    if rd is not None and rd.reader is not None:
        texts += ec.older_pending(emails, texts, "sms", lambda ids: fetch_ids(ids, db), log)
    sp = ec.seen_path("sms")
    seen = ec.load_seen(sp)
    new, push, handled = ec.run_new(texts, lambda t: apply_text(apps, emails, t, rd, notes, own), seen, notes, len(apps),
                                    "--reread" in a)
    ec.health(rd, log, "--no-notify" not in a and "--dry-run" not in a, "--dry-run" in a)
    unmatched = [r for r in new if r.get("unmatched")]
    rows = [r for r in new if not r.get("unmatched")]
    if "--dry-run" not in a:
        store.save("applications", apps)
        store.save("emails", emails)
        ec.save_seen(sp, seen)
    for u in unmatched:
        log(f"unmatched job text ({u['kind']}): {u['sender'][:20]} · {u['subject']}")
    pub = "skipped" if "--no-git" in a or "--dry-run" in a or not rows else git_publish(f"data: sms {ec.TODAY} (+{len(rows)} texts)")
    log(f"sms ok · {len(texts)} in window · {handled} new · {len(rows)} matched · {len(unmatched)} unmatched · git: {pub}")
    ec.report(f"求职短信 {ec.TODAY}", rows, push, notes, reader, log, "--no-notify" not in a)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
