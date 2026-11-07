"""Checks for scripts/store/store.py. Prints `fails 0` when everything passes."""
import json, os, sys, tempfile

os.environ["JOB_STORE_DIR"] = tempfile.mkdtemp(prefix="store_test_")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402

fails = 0


def ok(cond, label):
    global fails
    if not cond:
        fails += 1
    print(("PASS " if cond else "FAIL ") + label)


jobs = [{"id": "J00002", "company": "B", "title": "t2", "score": 50, "rank": 9},
        {"id": "J00001", "company": "A", "title": "t1", "score": 80, "rank": 7, "elig": "可投"},
        {"id": "J00003", "company": "C", "title": "t3", "score": 80}]
ok(store.save("jobs", jobs) == 3, "save returns the row count")
lines = open(store.path("jobs"), encoding="utf-8").read().splitlines()
ok([json.loads(x)["id"] for x in lines] == ["J00001", "J00002", "J00003"], "rows are sorted by key")
ok(all("rank" not in json.loads(x) for x in lines), "rank is not stored")
ok("可投" in lines[0], "non-ASCII is written as text, not escapes")
back = {r["id"]: r for r in store.load("jobs")}
order = sorted(back, key=lambda i: (-back[i]["score"], i))   # store.save re-scores jobs (score_v2, JSA-096)
ok([back[i]["rank"] for i in order] == [1, 2, 3], "rank recomputed: score desc, id breaks ties")

before = open(store.path("jobs"), encoding="utf-8").read()
try:
    store.save("jobs", jobs + [{"id": "J00001", "company": "A", "title": "dup", "score": 1}])
    ok(False, "duplicate id is refused")
except ValueError:
    ok(open(store.path("jobs"), encoding="utf-8").read() == before, "duplicate id is refused and the file is unchanged")
try:
    store.save("applications", [{"job_id": "J1", "company": "X", "title": "t"}])
    ok(False, "row without status is refused")
except ValueError as e:
    ok("status" in str(e), "row without status is refused")
ok(store.load("emails") == [], "a missing dataset loads as empty")
ok(not [f for f in os.listdir(store.STORE) if f.endswith(".tmp")], "no temp files left behind")
report, bad = store.check()
ok(report["jobs"] == 3 and not bad, "check reports counts with no problems")

print(f"fails {fails}")
sys.exit(1 if fails else 0)
