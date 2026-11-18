#!/usr/bin/env python3
"""JSA-417 (rule 13): job_closed verdicts + the closed mark, on DeepSeek-written cases
(scripts/test_cases/job_closed_cases.json from job_closed_spec.md; spec-misreading cases in job_closed_verdicts.json),
plus fixed checks: 403 / timeout is never closed, the mark goes through store.save, screen() drops and marks closed jobs.
Offline.   python3 scripts/store/test_job_closed.py → "fails 0" """
import copy, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
TC = os.path.join(os.path.dirname(HERE), "test_cases")
cases = json.load(open(os.path.join(TC, "job_closed_cases.json"), encoding="utf-8"))
vp = os.path.join(TC, "job_closed_verdicts.json")
verdicts = json.load(open(vp, encoding="utf-8")) if os.path.exists(vp) else {}
os.environ["JOB_STORE_DIR"] = tempfile.mkdtemp()
import job_closed as JC  # noqa: E402
import store  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        return
    if name in verdicts:
        print("skip %s (verdict: %s)" % (name, verdicts[name][:90])); return
    fails += 1; print("FAIL", name, detail)


for c in cases:
    if c["fn"] == "gh_verdict":
        got = JC.gh_verdict(c["statuses"]); check(c["name"], got == c["expect"], "got %r want %r" % (got, c["expect"]))
    elif c["fn"] == "board_verdict":
        got = JC.board_verdict(c["status"], c["body"], c["job_id"], c["platform"]); check(c["name"], got == c["expect"], "got %r want %r" % (got, c["expect"]))
    elif c["fn"] == "mark_closed_row":
        row = copy.deepcopy(c["row"]); ex = c["expect"]
        ch = JC.mark_closed_row(row, c["why"], c["source"], c["today"])
        bad = []
        if ch != ex["changed"]: bad.append("changed %r" % ch)
        if row.get("elig") != ex["elig"]: bad.append("elig %r" % row.get("elig"))
        if "tier" in ex and row.get("tier") != ex["tier"]: bad.append("tier %r" % row.get("tier"))
        if ex.get("elig_closed") is None and ex["changed"] is False and row != c["row"]: bad.append("row mutated")
        if ex.get("elig_closed") and ex["changed"]:
            ec = row.get("elig_closed") or {}
            if ec.get("at") != c["today"] or ec.get("source") != c["source"]: bad.append("elig_closed %r" % ec)
        check(c["name"], not bad, "; ".join(bad))

# fixed checks -----------------------------------------------------------------------------------------------
check("403 is unknown", JC.gh_verdict([403, 403]) == "unknown")
check("timeout (0) is unknown", JC.board_verdict(0, "", "x", "ashby") == "unknown")
check("ashby 403 is unknown", JC.board_verdict(403, "{}", "x", "ashby") == "unknown")
r = {"id": "J1", "elig": "可投", "tier": "B"}
JC.mark_closed_row(r, "x" * 500, "prefetch", "2026-11-17")
check("why cut to 200", len(r["elig_closed"]["why"]) == 200 and r["tier_orig"] == "B" and r["tier"] == "Blocked")
check("date in reason", "2026-11-17" in r["elig_reason"] and "prefetch" in r["elig_reason"])

check("parse_url greenhouse", JC.parse_url("https://boards.greenhouse.io/acme/jobs/123?gh_src=x") == ("greenhouse", "acme", "123"))
check("parse_url lever", JC.parse_url("https://jobs.lever.co/acme/0a1b2c3d-0a1b-0a1b-0a1b-0a1b2c3d4e5f/apply") == ("lever", "acme", "0a1b2c3d-0a1b-0a1b-0a1b-0a1b2c3d4e5f"))
check("parse_url ashby", JC.parse_url("https://jobs.ashbyhq.com/uipath/0a1b2c3d-0a1b-0a1b-0a1b-0a1b2c3d4e5f/application") == ("ashby", "uipath", "0a1b2c3d-0a1b-0a1b-0a1b-0a1b2c3d4e5f"))
check("parse_url other", JC.parse_url("https://x.myworkdayjobs.com/a/job/b_1") is None)

# store: mark through store.py, row kept; idempotent
rows = [{"id": "J1", "company": "A", "title": "t", "score": 5, "elig": "可投", "tier": "B", "url": "https://boards.greenhouse.io/a/jobs/1"},
        {"id": "J2", "company": "B", "title": "t", "score": 5, "elig": "可投", "tier": "B", "url": "https://boards.greenhouse.io/b/jobs/2"}]
store.save("jobs", rows)
check("mark_store changes", JC.mark_store("J1", "Greenhouse 404", "prefetch", "2026-11-17") is True)
check("mark_store idempotent", JC.mark_store("J1", "again", "prepare", "2026-11-18") is False)
check("mark_store unknown id", JC.mark_store("J9", "x", "prepare", "2026-11-17") is False)
got = {j["id"]: j for j in store.load("jobs")}
check("row kept + closed", len(got) == 2 and got["J1"]["elig"] == "已关闭" and got["J1"]["elig_closed"]["why"] == "Greenhouse 404" and got["J2"]["elig"] == "可投")

# screen(): fake checker; closed → dropped + marked; unknown / open → kept
verdict = {"J1": ("closed", "x"), "J2": ("unknown", "Ashby board 403"), "J3": ("open", ""), "J4": ("closed", "no longer on the Lever board")}
store.save("jobs", [{"id": i, "company": "C", "title": "t", "score": 1, "elig": "可投", "tier": "B", "url": "u"} for i in verdict])
jobs = [{"id": i} for i in verdict]
keep, dropped = JC.screen(jobs, today="2026-11-17", source="prepare", check=lambda j: verdict[j["id"]])
check("screen keeps open + unknown", [j["id"] for j in keep] == ["J2", "J3"])
check("screen drops closed", [d["id"] for d in dropped] == ["J1", "J4"])
got = {j["id"]: j for j in store.load("jobs")}
check("screen marked the store", got["J4"]["elig"] == "已关闭" and got["J2"]["elig"] == "可投" and got["J3"]["elig"] == "可投")
keep, dropped = JC.screen(jobs, today="2026-11-17", source="prepare", check=lambda j: verdict[j["id"]], mark=False)
check("screen mark=False writes nothing more", dropped and True)

# check_job with a fake transport: Ashby 403 → unknown, Lever board without the job → closed
def fake(table):
    return lambda url, **k: table.get(url, (0, "", url))
lv = "0a1b2c3d-0a1b-0a1b-0a1b-0a1b2c3d4e5f"
t = {"https://api.lever.co/v0/postings/acme?mode=json": (200, json.dumps([{"id": "other"}]), ""),
     "https://api.lever.co/v0/postings/acme/" + lv: (404, "", ""),
     "https://api.ashbyhq.com/posting-api/job-board/uipath?includeCompensation=false": (403, "", "")}
check("check_job lever closed", JC.check_job({"url": "https://jobs.lever.co/acme/" + lv}, get=fake(t))[0] == "closed")
check("check_job ashby 403 unknown", JC.check_job({"url": "https://jobs.ashbyhq.com/uipath/" + lv}, get=fake(t))[0] == "unknown")
check("check_job other ATS unknown", JC.check_job({"url": "https://x.myworkdayjobs.com/a/job/b_1"}, get=fake(t))[0] == "unknown")
check("check_job prefers ats_url", JC.check_job({"url": "https://linkedin.com/jobs/1", "ats_url": "https://jobs.lever.co/acme/" + lv}, get=fake(t))[0] == "closed")
# confirm_mark: GLA → the public API must agree; other ATS → eligibility_fetch.load must say closed
store.save("jobs", [{"id": i, "company": "C", "title": "t", "score": 1, "elig": "可投", "tier": "B", "url": "u"} for i in ("K1", "K2", "K3", "K4")])
gj = {"id": "K1", "url": "https://boards.greenhouse.io/a/jobs/1"}
check("confirm_mark API says open → not marked", JC.confirm_mark(gj, "Gone", "prefetch", check=lambda j: ("open", "")) == "")
check("confirm_mark API unknown (403) → not marked", JC.confirm_mark(gj, "Gone", "prefetch", check=lambda j: ("unknown", "403")) == "")
check("store untouched", {j["id"]: j["elig"] for j in store.load("jobs")}["K1"] == "可投")
check("confirm_mark API closed → marked", JC.confirm_mark(gj, "Gone", "prefetch", check=lambda j: ("closed", "Greenhouse 404")) == "Greenhouse 404")
wj = {"id": "K2", "url": "https://x.myworkdayjobs.com/a/job/b_1"}
check("confirm_mark other ATS unreadable → not marked", JC.confirm_mark(wj, "x", "prepare", load=lambda u: {"status": "unreadable"}) == "")
check("confirm_mark other ATS closed → marked", bool(JC.confirm_mark(wj, "x", "prepare", load=lambda u: {"status": "closed", "why": "Workday 404"})))
got = {j["id"]: j for j in store.load("jobs")}
check("confirm_mark wrote the store", got["K1"]["elig"] == "已关闭" and got["K2"]["elig_closed"]["source"] == "prepare")
def gh_fake(table):
    return lambda url, **k: (table.get(url, 0), "", url)
J = "https://boards.greenhouse.io/a/jobs/1"; US = "https://boards-api.greenhouse.io/v1/boards/a"; EU = "https://boards-api.eu.greenhouse.io/v1/boards/a"
check("gh: US 404 + board exists on US, EU unreachable → closed", JC.check_job({"url": J}, get=gh_fake({US + "/jobs/1": 404, US: 200}))[0] == "closed")
check("gh: US 404, board unreadable (0), EU 0 → unknown", JC.check_job({"url": J}, get=gh_fake({US + "/jobs/1": 404}))[0] == "unknown")
check("gh: US 404, board 403 → unknown", JC.check_job({"url": J}, get=gh_fake({US + "/jobs/1": 404, US: 403, EU + "/jobs/1": 0}))[0] == "unknown")
check("gh: job on the EU host → open", JC.check_job({"url": J}, get=gh_fake({US + "/jobs/1": 404, EU + "/jobs/1": 200}))[0] == "open")
check("gh: US 403 → unknown", JC.check_job({"url": J}, get=gh_fake({US + "/jobs/1": 403, EU + "/jobs/1": 404}))[0] == "unknown")
# unlisted-but-live: absent from the list, the posting's own endpoint still answers → open (not closed)
t2 = {"https://api.lever.co/v0/postings/acme?mode=json": (200, json.dumps([{"id": "other"}]), ""), "https://api.lever.co/v0/postings/acme/" + lv: (200, "{}", "")}
check("lever unlisted but live → open", JC.check_job({"url": "https://jobs.lever.co/acme/" + lv}, get=fake(t2))[0] == "open")
t3 = {"https://api.lever.co/v0/postings/acme?mode=json": (200, json.dumps([{"id": "other"}]), "")}
check("lever list lacks it, own endpoint unreachable → unknown", JC.check_job({"url": "https://jobs.lever.co/acme/" + lv}, get=fake(t3))[0] == "unknown")
AB = "https://api.ashbyhq.com/posting-api/job-board/acme?includeCompensation=false"; GQ = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting"
def ab(gq):
    return lambda url, **k: (200, json.dumps({"jobs": [{"id": "other"}]}), url) if url == AB else gq if url == GQ else (0, "", url)
aj = {"url": "https://jobs.ashbyhq.com/acme/" + lv}
check("ashby graphql null → closed", JC.check_job(aj, get=ab((200, json.dumps({"data": {"jobPosting": None}}), "")))[0] == "closed")
check("ashby graphql posting → open", JC.check_job(aj, get=ab((200, json.dumps({"data": {"jobPosting": {"id": lv}}}), "")))[0] == "open")
check("ashby graphql errors → unknown", JC.check_job(aj, get=ab((200, json.dumps({"errors": [{}], "data": None}), "")))[0] == "unknown")
check("ashby graphql 403 → unknown", JC.check_job(aj, get=ab((403, "", "")))[0] == "unknown")

# screen survives a failed store write (the closed jobs are still dropped)
class Boom:
    @staticmethod
    def load(n): raise OSError("disk")
lines = []
import job_closed as _jc
_orig = _jc.mark_many
_jc.mark_many = lambda *a, **k: (_ for _ in ()).throw(ValueError("bad row"))
keep, dropped = JC.screen([{"id": "J1"}, {"id": "J3"}], today="2026-11-17", source="prepare", check=lambda j: verdict[j["id"]], log=lines.append)
_jc.mark_many = _orig
check("screen: failed write still drops", [d["id"] for d in dropped] == ["J1"] and [j["id"] for j in keep] == ["J3"] and "store not updated" in lines[0])

# the gate's fresh read that finds the posting open again drops the stale mark
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "..", "skills", "job-hunt-pipeline", "scripts"))
import eligibility_merge as EM
jr = {"id": "J9", "elig": "已关闭", "elig_closed": {"at": "2026-11-17"}, "elig_codes": ""}
EM.apply_result(jr, {"v": "Eligible", "c": "", "e": "", "key": "k"}, "2026-11-24")
check("gate re-read open drops elig_closed", jr["elig"] == "可投" and "elig_closed" not in jr)
jr = {"id": "J9", "elig": "已关闭", "elig_closed": {"at": "2026-11-17"}, "elig_codes": ""}
EM.apply_result(jr, {"v": "Closed", "c": "", "e": "", "key": "k"}, "2026-11-24")
check("gate re-read closed keeps elig_closed", jr["elig"] == "已关闭" and "elig_closed" in jr)
# batch_apply hook: screen_closed drops closed jobs, --keep-closed and a crashing check keep the batch whole
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "..", "skills", "auto-apply", "runner"))
import batch_apply as BA
class A: keep_closed = False
jobs = [{"id": "J1", "url": "x"}, {"id": "J3", "url": "x"}]
_jc.check_job = lambda j: verdict[j["id"]]
check("batch_apply.screen_closed drops closed", [j["id"] for j in BA.screen_closed(jobs, "2026-11-17", A)] == ["J3"])
A.keep_closed = True
check("batch_apply --keep-closed keeps all", len(BA.screen_closed(jobs, "2026-11-17", A)) == 2)
A.keep_closed = False
_jc.screen = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
check("batch_apply.screen_closed survives a crash", len(BA.screen_closed(jobs, "2026-11-17", A)) == 2)
print("fails", fails)
sys.exit(1 if fails else 0)
