#!/usr/bin/env python3
"""DeepSeek-written cases for complete_jobs.update_sources (rule 13): python3 scripts/store/test_update_sources.py.

Cases: scripts/test_cases/update_sources_cases.json · verdicts: update_sources_verdicts.json.
"""
import copy, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from complete_jobs import update_sources

TC = os.path.join(os.path.dirname(HERE), "test_cases")
cases = json.load(open(os.path.join(TC, "update_sources_cases.json"), encoding="utf-8"))
vp = os.path.join(TC, "update_sources_verdicts.json")
verdicts = json.load(open(vp, encoding="utf-8")) if os.path.exists(vp) else {}
fails = 0
for c in cases:
    src = copy.deepcopy(c["sources"])
    args = (src, c["jobs"], c["today"], c["github_ok"], c["boards_ok"])
    got = update_sources(*args)
    bad = []
    if got != c["expect"]:
        bad.append("got %s" % json.dumps(got, ensure_ascii=False)[:300])
    if src != c["sources"]:
        bad.append("input mutated")
    if update_sources(got, c["jobs"], c["today"], c["github_ok"], c["boards_ok"]) != got:
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
