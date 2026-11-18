#!/usr/bin/env python3
"""DeepSeek-written cases for refit_chance (rule 13, spec scripts/test_cases/refit_chance_spec.md):
python3 scripts/scoring/test_refit_chance.py → "fails 0". A disagreement Claude judged a case error is listed in
refit_chance_verdicts.json (case name → reason) and skipped."""
import datetime as dt, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import refit_chance as R
TC = os.path.join(os.path.dirname(HERE), "test_cases")
cases = json.load(open(os.path.join(TC, "refit_chance_cases.json"), encoding="utf-8"))
vp = os.path.join(TC, "refit_chance_verdicts.json"); verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
close = lambda a, b, t=1e-6: abs(a - b) <= t


def check(c):
    i, e, fn, bad = c["input"], c["expect"], c["fn"], []
    if fn == "outcome":
        got = R.outcome(i.get("status"))
        if got != e["value"]: bad.append(f"{got} ≠ {e['value']}")
    elif fn == "build_sample":
        rows, ex = R.build_sample(i["apps"], i["jobs"], dt.date.fromisoformat(i["today"]), i["min_days"])
        if len(rows) != e["n"]: bad.append(f"n {len(rows)} ≠ {e['n']}")
        if "ys" in e and [r["y"] for r in rows] != e["ys"]: bad.append(f"ys {[r['y'] for r in rows]}")
        if "xs" in e and [r["x"] for r in rows] != [[float(v) for v in x] for x in e["xs"]]: bad.append("xs")
        if "excluded" in e and ex != e["excluded"]: bad.append(f"excluded {ex}")
    elif fn == "normalise":
        got = R.normalise(i["beta"])
        if not all(close(a, b) for a, b in zip(got, e["weights"])): bad.append(f"{got}")
    elif fn == "fit_map":
        b, cov = R.fit_map(i["rows"], i["mu"], i["sd"])
        if e.get("equals_mu") and not all(close(x, m) for x, m in zip(b, i["mu"])): bad.append(f"≠ mu {b}")
        if e.get("cov_diag_equals_sd2") and not all(close(cov[k][k], s * s) for k, s in enumerate(i["sd"])): bad.append("cov")
        bad += [f"β{k}>0" for k in e.get("positive", []) if not b[k] > 0]
        bad += [f"β{k}<0" for k in e.get("negative", []) if not b[k] < 0]
        bad += [f"β{k} not pinned" for k in e.get("pinned", []) if not close(b[k], i["mu"][k], 1e-3)]
        if e.get("var_le_prior") and not all(cov[k][k] <= s * s + 1e-9 for k, s in enumerate(i["sd"])): bad.append("var > prior")
        if e.get("finite") and not all(math.isfinite(x) for x in b): bad.append("not finite")
    elif fn == "spearman":
        got = R.spearman(i["a"], i["b"])
        if not close(got, e["value"]): bad.append(f"{got:.4f}")
    elif fn == "ranking_change":
        got = R.ranking_change(i["jobs"], i["w_old"], i["w_new"], i.get("top", 50))
        for k, v in e.items():
            if k in got and not (close(got[k], v, 1e-3) if isinstance(v, float) else got[k] == v): bad.append(f"{k} {got[k]} ≠ {v}")
    elif fn == "needed_n":
        rows = [dict(r, x=[float(v) for v in r["x"]]) for r in i["rows"]]
        got = R.needed_n(rows, i["beta"], i.get("prior_sd", 1.0))
        bad += [f"{k} not None ({got[k]})" for k in e.get("none", []) if got[k] is not None]
        bad += [f"{k} not int ({got[k]})" for k in e.get("int", []) if not (isinstance(got[k], int) and got[k] > 0)]
    else:
        bad.append(f"unknown fn {fn}")
    return bad


# own checks beyond the cases: the live weights are the scorer's, untouched
assert R.PRIOR_W == {"s_referral": 0.40, "s_timing": 0.25, "s_sponsor": 0.10, "s_fresh": 0.25}
fails = 0
for c in cases:
    try:
        bad = check(c)
    except Exception as ex:   # noqa: BLE001
        bad = [f"{type(ex).__name__}: {ex}"]
    if bad and c["name"] in verdicts: print("skip %s (verdict: %s)" % (c["name"], verdicts[c["name"]][:90]))
    elif bad: fails += 1; print("FAIL %s [%s]: %s" % (c["name"], c["fn"], "; ".join(bad)))
    else: print("ok   " + c["name"])
print("fails %d" % fails); sys.exit(1 if fails else 0)
