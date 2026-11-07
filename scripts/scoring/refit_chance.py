#!/usr/bin/env python3
"""Refit the chance-of-an-interview weights from tracker outcomes (JSA-102, ADR-0006). Analysis only: never writes the
store, the scorer or the dashboard — the live weights stay in score_v2.W until Joey adopts new ones.

Model: P(positive reply) = sigmoid(b0 + Σ β_k x_k), x = the four chance factors (s_referral, s_timing, s_sponsor,
s_fresh, each 0..1) of the applied job. With a handful of positives a free logistic fit is meaningless, so this is a
Bayesian update of the current priors: β_k ~ N(scale · w_k, prior_sd²) with w_k = score_v2.W, b0 ~ N(logit(base),
intercept_sd²); MAP by Newton, uncertainty by the Laplace approximation (inverse Hessian). New weights = positive part
of β normalised to sum 1, with 90 % intervals from posterior draws. shrink = posterior sd / prior sd per factor
(≈ 1.0 → the data said nothing about that factor). Stdlib only.

Sample: tracker rows that were really submitted, joined to jobs.jsonl by job_id, applied at least --min-days ago
(so a reply had time to arrive). positive = Assessment / Interview / Offer; negative = Rejected / Applied / No response.

    python3 scripts/scoring/refit_chance.py [--store DIR] [--today YYYY-MM-DD] [--min-days 7] [--scale 5]
                                            [--prior-sd 1] [--json OUT]
"""
import argparse, datetime as dt, json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from fit_bt import solve, inverse
import score_v2

KEYS = ["s_referral", "s_timing", "s_sponsor", "s_fresh"]
PRIOR_W = dict(score_v2.W)
POSITIVE = {"assessment", "interview", "offer"}
NEGATIVE = {"rejected", "applied", "no response"}


def outcome(status):
    """1 = positive reply, 0 = no / negative reply, None = not a usable submitted application."""
    s = (status or "").strip().lower()
    return 1 if s in POSITIVE else 0 if s in NEGATIVE else None


def _date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def build_sample(apps, jobs, today, min_days=7):
    """→ (rows, excluded). rows = [{"x": [4 floats], "y": 0/1, "job_id", "company", "status"}]; excluded = reason → count.
    jobs = {id: job}. Factors come from the job's s_* fields, or score_v2.factors(job) when they are missing."""
    rows, ex = [], {}
    def skip(r):
        ex[r] = ex.get(r, 0) + 1
    for a in apps:
        y = outcome(a.get("status"))
        if y is None:
            skip("not submitted / unknown status"); continue
        d = _date(a.get("applied_on"))
        if d is None:
            skip("no applied_on"); continue
        if (today - d).days < min_days:
            skip(f"applied < {min_days} days ago"); continue
        j = jobs.get(a.get("job_id"))
        if j is None:
            skip("job not in jobs.jsonl"); continue
        f = j if all(isinstance(j.get(k), (int, float)) for k in KEYS) else score_v2.factors(j)
        rows.append({"x": [float(f[k]) for k in KEYS], "y": y, "job_id": a.get("job_id"),
                     "company": a.get("company"), "status": a.get("status")})
    return rows, ex


def _logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def prior(rows, scale=5.0, prior_sd=1.0, intercept_sd=2.0, weights=None):
    """Prior means / sds for [b0, β_1..β_4]. b0 centred so that an average applied job gets the sample base rate
    (computed with add-one smoothing)."""
    w = weights or PRIOR_W
    mu_b = [scale * w[k] for k in KEYS]
    n = len(rows); pos = sum(r["y"] for r in rows)
    base = (pos + 1) / (n + 2)
    xbar = [sum(r["x"][i] for r in rows) / n for i in range(len(KEYS))] if n else [0.0] * len(KEYS)
    b0 = _logit(base) - sum(m * x for m, x in zip(mu_b, xbar))
    return [b0] + mu_b, [intercept_sd] + [prior_sd] * len(KEYS)


def fit_map(rows, mu, sd, iters=100):
    """MAP of the logistic model with independent normal priors N(mu, sd²); → (beta, cov)."""
    k = len(mu); b = list(mu); lam = [1.0 / s ** 2 for s in sd]
    H = None
    for _ in range(iters):
        g = [-lam[i] * (b[i] - mu[i]) for i in range(k)]
        H = [[lam[i] if i == j else 0.0 for j in range(k)] for i in range(k)]
        for r in rows:
            x = [1.0] + r["x"]
            z = sum(bi * xi for bi, xi in zip(b, x)); p = 1 / (1 + math.exp(-max(min(z, 35), -35)))
            for i in range(k):
                g[i] += (r["y"] - p) * x[i]
                for j in range(k):
                    H[i][j] += p * (1 - p) * x[i] * x[j]
        step = solve(H, g); b = [bi + si for bi, si in zip(b, step)]
        if max(abs(s) for s in step) < 1e-10:
            break
    return b, inverse(H)


def normalise(beta):
    """Positive part of the factor coefficients, scaled to sum 1 (all ≤ 0 → equal weights)."""
    pos = [max(x, 0.0) for x in beta]; s = sum(pos)
    return [x / s for x in pos] if s > 0 else [1.0 / len(beta)] * len(beta)


def _chol(A):
    n = len(A); L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][m] * L[j][m] for m in range(j))
            L[i][j] = math.sqrt(max(s, 1e-15)) if i == j else s / L[j][j]
    return L


def weight_intervals(beta, cov, draws=4000, seed=7, lo=0.05, hi=0.95):
    """90 % intervals of the normalised weights from N(beta, cov) draws (factor part only)."""
    rng = random.Random(seed); L = _chol(cov); k = len(beta); out = [[] for _ in range(k - 1)]
    for _ in range(draws):
        z = [rng.gauss(0, 1) for _ in range(k)]
        b = [beta[i] + sum(L[i][m] * z[m] for m in range(i + 1)) for i in range(k)]
        for i, w in enumerate(normalise(b[1:])):
            out[i].append(w)
    q = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))]
    return [(q(v, lo), q(v, hi)) for v in out]


def loglik(rows, beta):
    ll = 0.0
    for r in rows:
        z = beta[0] + sum(b * x for b, x in zip(beta[1:], r["x"])); p = 1 / (1 + math.exp(-max(min(z, 35), -35)))
        ll += math.log(max(p if r["y"] else 1 - p, 1e-12))
    return ll


def loo(rows, scale=5.0, prior_sd=1.0, intercept_sd=2.0):
    """Mean leave-one-out log-loss of (posterior, base rate only). Lower is better; equal → the factors add nothing."""
    post = base = 0.0; n = len(rows)
    for i in range(n):
        rest = rows[:i] + rows[i + 1:]
        mu, sd = prior(rest, scale, prior_sd, intercept_sd)
        b, _ = fit_map(rest, mu, sd)
        post -= loglik([rows[i]], b)
        p = (sum(r["y"] for r in rest) + 1) / (len(rest) + 2)
        base -= math.log(p if rows[i]["y"] else 1 - p)
    return post / max(n, 1), base / max(n, 1)


def needed_n(rows, beta, prior_sd=1.0, target=0.5):
    """Rough number of outcomes (like the current sample) until each factor's posterior sd is target × prior sd:
    data information per row = mean of p(1−p)(x−x̄)² (diagonal only, correlations ignored). None = no variation."""
    n = len(rows); out = {}
    for i, k in enumerate(KEYS):
        xbar = sum(r["x"][i] for r in rows) / n
        info = 0.0
        for r in rows:
            z = beta[0] + sum(b * x for b, x in zip(beta[1:], r["x"])); p = 1 / (1 + math.exp(-z))
            info += p * (1 - p) * (r["x"][i] - xbar) ** 2
        need = 1 / (target * prior_sd) ** 2 - 1 / prior_sd ** 2
        out[k] = int(math.ceil(need / (info / n))) if info > 1e-12 else None
    return out


def chance(job, w):
    return sum(w[k] * float(job.get(k) or 0) for k in KEYS)


def _ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for m in range(i, j + 1):
            r[order[m]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = _ranks(a), _ranks(b); n = len(a)
    if n < 2:
        return 1.0
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra)); vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else 1.0


def ranking_change(jobs, w_old, w_new, top=50):
    """On 可投 rows: Spearman ρ of the v2 score (value level + 30·chance) old vs new, top-N overlap, B↔C flips."""
    live = [j for j in jobs if j.get("elig") == "可投"]
    sc = lambda j, w: score_v2.S_VALUE.get(j.get("v_level") or "standard", 40) + 30 * chance(j, w)
    old = [sc(j, w_old) for j in live]; new = [sc(j, w_new) for j in live]
    top_o = {live[i]["id"] for i in sorted(range(len(live)), key=lambda i: -old[i])[:top]}
    top_n = {live[i]["id"] for i in sorted(range(len(live)), key=lambda i: -new[i])[:top]}
    std = [j for j in live if j.get("v_level") == "standard"]
    flips = sum(1 for j in std if (chance(j, w_old) >= 0.5) != (chance(j, w_new) >= 0.5))
    to_b = sum(1 for j in std if chance(j, w_old) < 0.5 <= chance(j, w_new))
    return {"n": len(live), "spearman": round(spearman(old, new), 3), "top_overlap": len(top_o & top_n), "top": top,
            "b_c_flips": flips, "c_to_b": to_b, "b_to_c": flips - to_b}


def variation(rows):
    """Per factor: {value: [n, positives]} — shows which factors the sample can say anything about."""
    out = {}
    for i, k in enumerate(KEYS):
        t = {}
        for r in rows:
            c = t.setdefault(r["x"][i], [0, 0]); c[0] += 1; c[1] += r["y"]
        out[k] = dict(sorted(t.items()))
    return out


def refit(apps, jobs_list, today, min_days=7, scale=5.0, prior_sd=1.0, intercept_sd=2.0):
    jobs = {j.get("id"): j for j in jobs_list}
    rows, ex = build_sample(apps, jobs, today, min_days)
    res = {"today": today.isoformat(), "min_days": min_days, "n": len(rows), "positives": sum(r["y"] for r in rows),
           "excluded": ex, "variation": {k: {str(v): c for v, c in d.items()} for k, d in variation(rows).items()},
           "prior_weights": PRIOR_W, "scale": scale, "prior_sd": prior_sd}
    if not rows:
        return res
    mu, sd = prior(rows, scale, prior_sd, intercept_sd)
    b, cov = fit_map(rows, mu, sd)
    se = [math.sqrt(max(cov[i][i], 0)) for i in range(len(b))]
    w_new = dict(zip(KEYS, normalise(b[1:])))
    ivl = weight_intervals(b, cov)
    lp, lb = loo(rows, scale, prior_sd, intercept_sd)
    res.update({
        "positives_list": [f"{r['company']} ({r['status']})" for r in rows if r["y"]],
        "beta": {k: {"prior": round(m, 3), "post": round(x, 3), "sd": round(s, 3), "shrink": round(s / p, 3)}
                 for k, m, x, s, p in zip(["b0"] + KEYS, mu, b, se, sd)},
        "new_weights": {k: round(v, 3) for k, v in w_new.items()},
        "weight_90": {k: [round(lo, 3), round(hi, 3)] for k, (lo, hi) in zip(KEYS, ivl)},
        "loo_logloss": {"posterior": round(lp, 4), "base_rate_only": round(lb, 4)},
        "ranking": ranking_change(jobs_list, PRIOR_W, w_new),
        "needed_n_half_sd": needed_n(rows, b, prior_sd),
    })
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=os.path.expanduser("~/Projects/job-search-agent/data/store"))
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--min-days", type=int, default=7)
    ap.add_argument("--scale", type=float, default=5.0)
    ap.add_argument("--prior-sd", type=float, default=1.0)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    load = lambda n: [json.loads(l) for l in open(os.path.join(a.store, n), encoding="utf-8") if l.strip()]
    res = refit(load("applications.jsonl"), load("jobs.jsonl"), dt.date.fromisoformat(a.today), a.min_days,
                a.scale, a.prior_sd)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
