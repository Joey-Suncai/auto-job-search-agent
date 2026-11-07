#!/usr/bin/env python3
"""Blind-ranking set for scoring v2 (JSA-096): 20 held-out Summer 2027 internships spread over the v1 value range.

    python3 scripts/scoring/make_blind.py <jobs.jsonl> <weights.json | --tiers> <out.json> <pairs.json | blind.json> …

Roles shown in the questionnaires are left out (other roles at the same companies may appear), so the check is out of sample. Joey rates each role
1–5 without seeing any score; Spearman ρ between his ratings and v1 value is the acceptance test (≥ 0.7, ADR-0006).
"""
import json, math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_pairs import pool, card
from features import role_category, value_tier


def value(c, w):
    v = w.get(f"role:{c['role']}", 0.0) if c["role"] not in ("data", "other") else 0.0
    return v + w.get("h1b_log10", 0.0) * math.log10(1 + (c.get("h1b_fy25") or 0))


def main(a):
    rows = [json.loads(l) for l in open(a[0], encoding="utf-8")]
    tiers = a[1] == "--tiers"
    w = {} if tiers else json.load(open(a[1], encoding="utf-8"))["weights"]
    seen = set()
    for pf in a[3:]:
        doc = json.load(open(pf, encoding="utf-8"))
        for p in doc.get("pairs", []):
            for c in (p["a"], p["b"]):
                seen.add(c["id"])
        seen.update(c["id"] for c in doc.get("roles", []))   # an earlier blind set
    cands = [card(j) for jobs in pool(rows).values() for j in jobs if j["id"] not in seen]
    rnd = random.Random(int(os.environ.get("BLIND_SEED", "5"))); rnd.shuffle(cands)
    for c in cands:
        c["v1"] = value_tier(c["title"]) if tiers else round(value(c, w), 3)
    cands.sort(key=lambda c: (c["v1"], c.get("h1b_fy25") or 0))
    # stratified: a quota per role category, spread over company size inside each (so the value range is wide)
    QUOTA = {"ai_pm": 3, "ai_nonengineering": 3, "data_analysis": 4, "pm": 4, "ai_engineering": 3, "data": 3}
    picked, comps = [], set()
    for role, q in QUOTA.items():
        group = [c for c in cands if c["role"] == role]
        for k in range(q):
            start = (len(group) - 1) * k // max(1, q - 1) if q > 1 else 0
            for c in group[start:] + group[:start]:
                if c["company"] not in comps:
                    picked.append(c); comps.add(c["company"]); break
    rnd.shuffle(picked)
    for i, c in enumerate(picked, 1):
        c["n"] = i
    json.dump({"version": 1, "weights_file": os.path.abspath(a[1]), "n": len(picked),
               "question": "这个岗位你有多想要？（1 = 不想投，5 = 非常想要）", "roles": picked},
              open(a[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for c in picked:
        print(c["n"], c["v1"], c["role"], c["h1b_fy25"], c["company"][:22], "—", c["title"][:60])


if __name__ == "__main__":
    main(sys.argv[1:])
