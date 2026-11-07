#!/usr/bin/env python3
"""Pairwise questionnaire for scoring v2 (JSA-096): 18 trade-off pairs of real Summer 2027 internships + 2 repeats.

    python3 scripts/scoring/make_pairs.py <jobs.jsonl> <out.json> [--seed 7]

Each job shows only value attributes (role, sponsorship, green card) — chance factors (referral, freshness, score) are
hidden, because the question is "if both were equally likely, which would you take?".
"""
import itertools, json, random, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import ROLES, ROLE_LABEL, SPONSOR_LABEL, role_category, sponsor_level, green_card

SUMMER27 = re.compile(r"(summer\s*2027|2027\s*summer|summer\s*'?27|2027 intern|\bsummer\b)", re.I)
OFF = re.compile(r"(fall|spring|winter|autumn|co-?op|part[- ]time|year[- ]round|semester|phd|ph\.d|mba|undergrad|undergraduate|bachelor)", re.I)
RANK_R = {r: i for i, r in enumerate(ROLES)}
RANK_S = {"offers": 0, "strong": 1, "some": 2, "unknown": 3}


def pool(rows):
    out = {}
    for j in rows:
        if j.get("elig") not in ("可投", "待核实") or j.get("level") != "Internship":
            continue
        t = j.get("title") or ""
        if OFF.search(t) or not SUMMER27.search(t + " " + str(j.get("sources") or "")):
            continue
        r, s = role_category(t), sponsor_level(j)
        if r == "other" or s == "blocked":
            continue
        out.setdefault((r, s), []).append(j)
    for k in out:
        out[k].sort(key=lambda j: (-(j.get("h1b_fy25") or 0), j["id"]))
    return out


def card(j):
    return {"id": j["id"], "company": j["company"], "title": j["title"], "location": (j.get("location") or "")[:60],
            "role": role_category(j["title"]), "role_label": ROLE_LABEL[role_category(j["title"])],
            "sponsor": sponsor_level(j), "sponsor_label": SPONSOR_LABEL[sponsor_level(j)],
            "h1b_fy25": j.get("h1b_fy25") or 0, "green_card": green_card(j)}


def main(a):
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 7
    rnd = random.Random(seed)
    rows = [json.loads(l) for l in open(a[0], encoding="utf-8")]
    P = pool(rows)
    profiles = sorted(P)
    trade, single = [], []
    for x, y in itertools.combinations(profiles, 2):
        dr, ds = RANK_R[x[0]] - RANK_R[y[0]], RANK_S[x[1]] - RANK_S[y[1]]
        if dr and ds and (dr > 0) != (ds > 0):
            trade.append((x, y))            # better role on one side, better sponsorship on the other
        elif (dr == 0) != (ds == 0):
            single.append((x, y))           # one attribute differs
    rnd.shuffle(trade); rnd.shuffle(single)
    chosen, use_r, use_s = [], {}, {}
    def ok(p):  # spread every level over the questionnaire
        return all(use_r.get(k[0], 0) < 6 and use_s.get(k[1], 0) < 9 for k in p)
    for p in trade:
        if len(chosen) < 14 and ok(p):
            chosen.append(p); [use_r.__setitem__(k[0], use_r.get(k[0], 0) + 1) or use_s.__setitem__(k[1], use_s.get(k[1], 0) + 1) for k in p]
    for p in single:
        if len(chosen) < 18 and ok(p):
            chosen.append(p); [use_r.__setitem__(k[0], use_r.get(k[0], 0) + 1) or use_s.__setitem__(k[1], use_s.get(k[1], 0) + 1) for k in p]
    used, pairs = set(), []
    for x, y in chosen:
        a_ = next((j for j in P[x] if j["id"] not in used and j["company"] not in {u for u in used}), P[x][0])
        b_ = next((j for j in P[y] if j["id"] not in used and j["company"] != a_["company"] and j["company"] not in used), None)
        if not b_:
            continue
        used.update([a_["id"], b_["id"], a_["company"], b_["company"]])
        A, B = (card(a_), card(b_)) if rnd.random() < 0.5 else (card(b_), card(a_))
        pairs.append({"q": len(pairs) + 1, "a": A, "b": B})
    for src in (pairs[2], pairs[9]):           # consistency repeats, sides swapped
        pairs.append({"q": len(pairs) + 1, "a": src["b"], "b": src["a"], "repeat_of": src["q"]})
    out = {"version": 1, "seed": seed, "made_from": os.path.abspath(a[0]), "n": len(pairs),
           "question": "如果两个岗位拿到面试的机会一样大，你更想要哪一个？", "pairs": pairs}
    json.dump(out, open(a[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(pairs)} pairs → {a[1]} · roles {use_r} · sponsorship {use_s}")


if __name__ == "__main__":
    main(sys.argv[1:])


# ---- round 2: targeted pairs for the weights round 1 left uncertain (JSA-096) ----
ROUND2 = [  # (role, sponsor, green_card) vs (role, sponsor, green_card); None = either
    (("data_analysis", "offers", None), ("data_analysis", "strong", None)),   # offers vs strong, role fixed
    (("pm", "offers", None), ("pm", "strong", None)),
    (("data", "offers", None), ("data", "strong", None)),
    (("pm", "some", None), ("data", "some", None)),                           # PM vs data, sponsorship fixed
    (("pm", "strong", None), ("data", "strong", None)),
    (("pm", "some", None), ("data_analysis", "some", None)),                  # PM vs analysis
    (("ai_pm", "some", None), ("data_analysis", "some", None)),               # AI PM vs analysis
    (("ai_engineering", "strong", None), ("data", "strong", None)),           # AI engineering vs data
    (("ai_nonengineering", "strong", None), ("pm", "strong", None)),
    (("data_analysis", "some", True), ("data_analysis", "some", False)),      # green card alone
    (("pm", "strong", True), ("pm", "strong", False)),
    (("data", "some", True), ("data", "some", False)),
]


def round2(rows, seed=11, exclude=()):
    rnd = random.Random(seed); P = pool(rows); used = set(exclude); pairs = []
    def pick(role, sp, gc, avoid):
        for j in P.get((role, sp), []):
            if j["id"] in used or j["company"] in used or j["company"] == avoid:
                continue
            if gc is not None and green_card(j) != gc:
                continue
            return j
    for x, y in ROUND2:
        a_ = pick(*x, None); b_ = pick(*y, a_["company"] if a_ else None) if a_ else None
        if not (a_ and b_):
            continue
        used.update([a_["id"], b_["id"], a_["company"], b_["company"]])
        A, B = (card(a_), card(b_)) if rnd.random() < 0.5 else (card(b_), card(a_))
        pairs.append({"q": len(pairs) + 1, "a": A, "b": B, "target": f"{x} vs {y}"})
    pairs.append({"q": len(pairs) + 1, "a": pairs[0]["b"], "b": pairs[0]["a"], "repeat_of": 1})
    return pairs
