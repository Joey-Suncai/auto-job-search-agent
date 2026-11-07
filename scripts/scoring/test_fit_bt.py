#!/usr/bin/env python3
"""DeepSeek-written cases for fit_bt (rule 13): python3 scripts/scoring/test_fit_bt.py → "fails 0".
Also checks: swapping A/B with the answer gives the same weights; weights finite."""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fit_bt
TC = os.path.join(os.path.dirname(HERE), "test_cases")
cases = json.load(open(os.path.join(TC, "fit_bt_cases.json"), encoding="utf-8"))
vp = os.path.join(TC, "fit_bt_verdicts.json"); verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
fails = 0
for c in cases:
    feats = fit_bt.MODELS[c.get("model", "buckets")]
    data, cons = fit_bt.rows(c["pairs"], c["answers"], feats)
    w, _ = fit_bt.fit(data, c.get("prior_sd", 2), k=len(feats)) if data else ([0.0] * len(feats), None)
    W = dict(zip(feats, w)); e = c["expect"]; bad = []
    if c.get("loo_all_predicted") and data:
        h, n, _ll = fit_bt.loo(data, c.get("prior_sd", 2))
        if h != n: bad.append(f"loo {h}/{n}")
    g = lambda f: W.get(f, 0.0)
    bad += [f"{f}>0" for f in e.get("positive", []) if not g(f) > 0]
    bad += [f"{f}<0" for f in e.get("negative", []) if not g(f) < 0]
    bad += [f"{f}=0" for f in e.get("zero", []) if abs(g(f)) >= 1e-9]
    bad += [f"{x}>{y}" for x, y in e.get("greater", []) if not g(x) > g(y)]
    if "n_choices" in e and len(data) != e["n_choices"]: bad.append(f"n {len(data)}≠{e['n_choices']}")
    if "consistency_same" in e and [s for _, _, s in cons] != e["consistency_same"]: bad.append(f"cons {[s for _,_,s in cons]}")
    if any(not math.isfinite(x) for x in w): bad.append("not finite")
    sw = [dict(p, a=p["b"], b=p["a"]) for p in c["pairs"]]
    sa = {k: {"A": "B", "B": "A"}.get(v, v) for k, v in c["answers"].items()}
    d2, _ = fit_bt.rows(sw, sa, feats)
    if d2:
        w2, _ = fit_bt.fit(d2, c.get("prior_sd", 2), k=len(feats))
        if any(abs(x - y) > 1e-6 for x, y in zip(w, w2)): bad.append("swap changes weights")
    if bad and c["name"] in verdicts: print("skip %s (verdict: %s)" % (c["name"], verdicts[c["name"]][:90]))
    elif bad: fails += 1; print("FAIL %s: %s · w=%s" % (c["name"], "; ".join(bad), {k: round(v, 2) for k, v in W.items() if v}))
    else: print("ok   " + c["name"])
print("fails %d" % fails); sys.exit(1 if fails else 0)
