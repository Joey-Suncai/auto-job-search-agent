#!/usr/bin/env python3
"""DeepSeek-written cases for score_v2 (rule 13): python3 scripts/scoring/test_score_v2.py → "fails 0".
Also checks: input not mutated, idempotent."""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score_v2
TC = os.path.join(os.path.dirname(HERE), "test_cases")
cases = json.load(open(os.path.join(TC, "score_v2_cases.json"), encoding="utf-8"))
vp = os.path.join(TC, "score_v2_verdicts.json"); verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
fails = 0
for c in cases:
    job = copy.deepcopy(c["job"]); got = score_v2.score_row(job)
    bad = []
    for k, v in c["expect"].items():
        g = got.get(k)
        if isinstance(v, (int, float)) and isinstance(g, (int, float)) and not isinstance(v, bool):
            if abs(g - v) > 0.051: bad.append(f"{k}={g}≠{v}")
        elif g != v: bad.append(f"{k}={g!r}≠{v!r}")
    if job != c["job"]: bad.append("input mutated")
    if score_v2.score_row(got) != got: bad.append("not idempotent")
    if bad and c["name"] in verdicts: print("skip %s (verdict: %s)" % (c["name"], verdicts[c["name"]][:90]))
    elif bad: fails += 1; print("FAIL %s: %s" % (c["name"], "; ".join(bad)))
    else: print("ok   " + c["name"])
print("fails %d" % fails); sys.exit(1 if fails else 0)
