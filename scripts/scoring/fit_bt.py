#!/usr/bin/env python3
"""Fit value weights from pairwise choices — Bradley-Terry / logistic on attribute differences (JSA-096, ADR-0006).

    python3 scripts/scoring/fit_bt.py <pairs.json> <answers.json> [<pairs2.json> <answers2.json> …]
                                      [--model buckets|size] [--out weights.json] [--prior-sd 2]

Model: P(choose a over b) = sigmoid(w · (x_a − x_b)); x = role one-hot (baseline "data"), sponsorship one-hot (baseline
"unknown"), green card 0/1. A normal prior N(0, prior_sd²) on every weight keeps it finite with few answers (MAP by Newton);
intervals from the Laplace approximation (inverse Hessian). Repeated pairs (repeat_of) are not fitted twice: they only
measure consistency. Stdlib only.
"""
import json, math, sys

ROLES = ["ai_pm", "data_analysis", "pm", "ai_nonengineering", "ai_engineering", "data", "other"]
SPONSOR = ["offers", "strong", "some", "unknown"]
BASE_ROLE, BASE_SPONSOR = "data", "unknown"
ROLE_F = [f"role:{r}" for r in ROLES if r not in (BASE_ROLE, "other")]
MODELS = {
    # sponsorship as 3 levels against "unknown"
    "buckets": ROLE_F + [f"sponsor:{s}" for s in SPONSOR if s != BASE_SPONSOR] + ["green_card"],
    # company size as log10(1 + FY25 H-1B count) (the buckets "strong" / "some" are cuts of the same count), plus the
    # posting's own sponsorship statement and the green-card record
    "size": ROLE_F + ["h1b_log10", "sponsor:offers", "green_card"],
    # chosen 2026-11-03 by leave-one-out on Joey's 28 choices: LOO 18/28, log-loss 0.655 (the only one below 0.693 = chance);
    # adding sponsor:offers / green_card made the out-of-sample fit worse (JSA-096, ADR-0006)
    "v1": ROLE_F + ["h1b_log10"],
}
FEATURES = MODELS["buckets"]


def x_of(card, features=None):
    features = features or FEATURES
    v = [0.0] * len(features)
    for i, f in enumerate(features):
        if f == "h1b_log10":
            v[i] = math.log10(1 + (card.get("h1b_fy25") or 0))
        elif f == f"role:{card['role']}" or f == f"sponsor:{card['sponsor']}" or (f == "green_card" and card.get("green_card")):
            v[i] = 1.0
    return v


def rows(pairs, answers, features=None):
    """[(diff vector chosen − other, q)] for non-repeat pairs; consistency [(q, repeat_of, same_choice)]."""
    by_q = {p["q"]: p for p in pairs}
    data, cons = [], []
    for p in pairs:
        pick = answers.get(str(p["q"]), answers.get(p["q"]))
        if pick not in ("A", "B"):
            continue
        win, lose = (p["a"], p["b"]) if pick == "A" else (p["b"], p["a"])
        if p.get("repeat_of"):
            first = by_q[p["repeat_of"]]
            fp = answers.get(str(first["q"]), answers.get(first["q"]))
            fwin = first["a"] if fp == "A" else first["b"]
            cons.append((p["q"], p["repeat_of"], fwin["id"] == win["id"]))
            continue
        data.append(([a - b for a, b in zip(x_of(win, features), x_of(lose, features))], p["q"]))
    return data, cons


def solve(A, b):
    n = len(b); M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c])); M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c and M[c][c]:
                f = M[r][c] / M[c][c]; M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def inverse(A):
    n = len(A)
    return [list(col) for col in zip(*[solve(A, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)])]


def fit(data, prior_sd=2.0, iters=50, k=None):
    k = k or (len(data[0][0]) if data else len(FEATURES)); w = [0.0] * k; lam = 1.0 / prior_sd ** 2
    for _ in range(iters):
        g = [-lam * wi for wi in w]; H = [[(lam if i == j else 0.0) for j in range(k)] for i in range(k)]
        for d, _q in data:
            z = sum(wi * di for wi, di in zip(w, d)); p = 1 / (1 + math.exp(-z))
            for i in range(k):
                g[i] += (1 - p) * d[i]
                for j in range(k):
                    H[i][j] += p * (1 - p) * d[i] * d[j]
        step = solve(H, g); w = [wi + si for wi, si in zip(w, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    cov = inverse(H)
    return w, [math.sqrt(max(cov[i][i], 0)) for i in range(k)]


def loo(data, prior_sd=2.0):
    """Leave-one-out: share of choices predicted by weights fitted without them, and mean log-loss."""
    hit, ll = 0, 0.0
    for i in range(len(data)):
        w, _ = fit(data[:i] + data[i + 1:], prior_sd, k=len(data[i][0]))
        z = sum(x * y for x, y in zip(w, data[i][0])); p = 1 / (1 + math.exp(-z))
        hit += z > 0; ll -= math.log(max(p, 1e-12))
    return hit, len(data), ll / max(1, len(data))


def merge(files):
    """[(pairs.json, answers.json), …] → one pairs list + answers, q renumbered per round (round r adds 100·r)."""
    pairs, answers = [], {}
    for r, (pf, af) in enumerate(files):
        ps = json.load(open(pf, encoding="utf-8"))["pairs"]; an = json.load(open(af, encoding="utf-8"))["answers"]
        for p in ps:
            q = p["q"] + 100 * r
            pairs.append(dict(p, q=q, **({"repeat_of": p["repeat_of"] + 100 * r} if p.get("repeat_of") else {})))
            if str(p["q"]) in an or p["q"] in an:
                answers[str(q)] = an.get(str(p["q"]), an.get(p["q"]))
    return pairs, answers


def main(a):
    files = [(a[i], a[i + 1]) for i in range(0, len(a), 2) if not a[i].startswith("--") and i + 1 < len(a) and not a[i + 1].startswith("--")]
    files = [f for f in files if f[0].endswith(".json")]
    pairs, answers = merge(files)
    sd = float(a[a.index("--prior-sd") + 1]) if "--prior-sd" in a else 2.0
    model = a[a.index("--model") + 1] if "--model" in a else "v1"
    features = MODELS[model]
    data, cons = rows(pairs, answers, features)
    w, se = fit(data, sd, k=len(features))
    hit, n, ll = loo(data, sd)
    global FEATURES
    FEATURES = features
    agree = sum(1 for d, _ in data if sum(x * y for x, y in zip(w, d)) > 0)
    out = {"model": model, "loo": {"predicted": f"{hit}/{n}", "log_loss": round(ll, 3)}, "features": FEATURES, "baseline": {"role": BASE_ROLE, "sponsor": BASE_SPONSOR}, "prior_sd": sd,
           "n_choices": len(data), "weights": dict(zip(FEATURES, [round(x, 3) for x in w])),
           "se": dict(zip(FEATURES, [round(x, 3) for x in se])),
           "fit_agreement": f"{agree}/{len(data)}",
           "against_model": [q for d, q in data if sum(x * y for x, y in zip(w, d)) <= 0],
           "consistency": [{"q": q, "repeat_of": r, "same": s} for q, r, s in cons]}
    if "--out" in a:
        json.dump(out, open(a[a.index("--out") + 1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
