#!/usr/bin/env python3
"""DeepSeek-written cases for complete_jobs (rule 13): python3 scripts/store/test_complete_jobs.py → "fails 0".

Cases: scripts/test_cases/complete_jobs_cases.json · verdicts (cases that misread the spec): complete_jobs_verdicts.json.
Also checks: input not mutated, idempotent.
"""
import copy, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import complete_jobs

TC = os.path.join(os.path.dirname(HERE), "test_cases")
cases = json.load(open(os.path.join(TC, "complete_jobs_cases.json"), encoding="utf-8"))
vp = os.path.join(TC, "complete_jobs_verdicts.json")
verdicts = json.load(open(vp, encoding="utf-8")) if os.path.exists(vp) else {}
fails = 0
for c in cases:
    row = copy.deepcopy(c["row"])
    got = complete_jobs.complete([row], c.get("companies", []))[0]
    bad = ["%s=%r≠%r" % (k, got.get(k), v) for k, v in c.get("expect", {}).items() if got.get(k) != v]
    bad += ["%s present" % k for k in c.get("expect_absent", []) if k in got]
    if row != c["row"]:
        bad.append("input mutated")
    if complete_jobs.complete([got], c.get("companies", []))[0] != got:
        bad.append("not idempotent")
    if bad and c["name"] in verdicts:
        print("skip %s (verdict: %s)" % (c["name"], verdicts[c["name"]][:90]))
    elif bad:
        fails += 1
        print("FAIL %s: %s" % (c["name"], "; ".join(bad)))
    else:
        print("ok   " + c["name"])
print("fails %d" % fails)
sys.exit(1 if fails else 0)
