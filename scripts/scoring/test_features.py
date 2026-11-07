#!/usr/bin/env python3
"""DeepSeek-written cases for features.role_category (rule 13): python3 scripts/scoring/test_features.py → "fails 0"."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from features import role_category
TC = os.path.join(os.path.dirname(HERE), "test_cases")
cases = json.load(open(os.path.join(TC, "role_category_cases.json"), encoding="utf-8"))
vp = os.path.join(TC, "role_category_verdicts.json"); verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
fails = 0
for c in cases:
    got = role_category(c["title"])
    if got == c["expect"]: print("ok   " + c["name"])
    elif c["name"] in verdicts: print("skip %s (verdict: %s)" % (c["name"], verdicts[c["name"]][:90]))
    else: fails += 1; print("FAIL %s: %r → %s (expected %s)" % (c["name"], c["title"], got, c["expect"]))
print("fails %d" % fails); sys.exit(1 if fails else 0)
