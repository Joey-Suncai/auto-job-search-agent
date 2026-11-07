"""Checks for sms_check.py (no real Messages database: a fixture chat.db). Prints `fails 0` when everything passes."""
import datetime, os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sms_check as sc  # noqa: E402

fails = 0
def ok(c, label):
    global fails
    fails += 0 if c else 1
    print(("PASS " if c else "FAIL ") + label)

def apps():
    return [{"job_id": "B1", "company": "CorBrakel", "title": "Quantitative Masters Internship", "status": "Applied", "applied_on": "2026-10-30"},
            {"job_id": "T1", "company": "Target", "title": "Data Analyst Intern", "status": "Applied", "applied_on": "2026-10-28"},
            {"job_id": "N1", "company": "OSTROSROS", "title": "AI Systems Intern", "status": "Shortlisted", "applied_on": ""}]

def text(i, body, sender="+13125550100"):
    return {"id": f"sms-{i}", "date": "2026-10-30", "sender": sender, "service": "SMS", "body": body}

A, E = apps(), []
r = sc.apply_text(A, E, text("1", "Hi Joey, this is Sarah, a recruiter at CorBrakel. Are you free for a phone interview this week?"))
ok(r and r["type"] == "Interview" and r["channel"] == "sms" and A[0]["action_needed"], "recruiter text naming the company → Interview, channel sms")
ok(A[0]["status"] == "Applied" and A[0]["applied_on"] == "2026-10-30", "interview text flags but does not move the stage")
ok(sc.apply_text(A, E, text("2", "Meet me at Target at 6? need to grab snacks")) is None, "personal text naming a company but no job word → ignored")
ok(sc.apply_text(A, E, text("3", "Your CorBrakel verification code is 482913. Do not share it.")) is None, "verification codes are skipped")
r = sc.apply_text(A, E, text("4", "Target HR: unfortunately we will not be moving forward with your application for the Data Analyst Intern role."))
ok(r and r["type"] == "Rejection" and A[1]["status"] == "Rejected", "rejection text → Rejected")
r = sc.apply_text(A, E, text("5", "Hello, I'm a recruiter with a great internship opportunity, can we chat?"))
ok(r and r.get("unmatched"), "job-sounding text with no applied company → listed, not guessed")
ok(sc.apply_text(A, E, text("6", "OSTROSROS recruiter here: we'd like to schedule an interview.")).get("unmatched"), "a Shortlisted row is never matched")
ok(sc.apply_text(A, E, text("1", "Hi Joey, this is Sarah, a recruiter at CorBrakel. interview?")) is None, "same message id is not added twice")
ok(len(E) == 2 and all(e["id"].startswith("sms-") for e in E), "only the two matched texts are stored")

# attributedBody decoding + fetch from a fixture database
s = "Your CorBrakel interview is confirmed for Monday 10am."
blob = b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84\x12NSAttributedString\x00\x84\x84\x08NSObject\x00\x85\x92\x84\x84\x84\x08NSString\x01\x94\x84\x01+" + bytes([len(s)]) + s.encode()
ok(sc.decode_body(blob) == s, "attributedBody (short) decodes")
long_s = "x" * 300
blob2 = b"..NSString\x01\x94\x84\x01+\x81" + len(long_s).to_bytes(2, "little") + long_s.encode()
ok(sc.decode_body(blob2) == long_s, "attributedBody (2-byte length) decodes")
d = tempfile.mkdtemp()
db = os.path.join(d, "chat.db")
con = sqlite3.connect(db)
con.executescript("create table handle (ROWID integer primary key, id text);"
                  "create table message (ROWID integer primary key, guid text, date integer, text text, attributedBody blob, handle_id integer, is_from_me integer, service text);")
con.execute("insert into handle values (1, '+13125550100')")
now_ns = int((datetime.datetime.now(datetime.timezone.utc) - sc.APPLE_EPOCH).total_seconds() * 1e9)
old_ns = now_ns - int(10 * 86400 * 1e9)
con.executemany("insert into message (guid, date, text, attributedBody, handle_id, is_from_me, service) values (?,?,?,?,?,?,?)",
                [("g1", now_ns, "plain text", None, 1, 0, "SMS"), ("g2", now_ns, None, blob, 1, 0, "iMessage"),
                 ("g3", now_ns, "sent by me", None, 1, 1, "SMS"), ("g4", old_ns, "too old", None, 1, 0, "SMS")])
con.commit(); con.close()
got = sc.fetch(2, db)
ok([g["body"] for g in got] == ["plain text", s], "fetch: incoming only, last 2 days, attributedBody fallback")
ok(got[0]["id"] == "sms-g1" and got[0]["date"] == datetime.date.today().isoformat(), "fetch: id and local date")

print(f"fails {fails}")
sys.exit(1 if fails else 0)
