#!/usr/bin/env python3
"""Joey's 👍 / 👎 on a role (JSA-096): sets `joey_pref` and re-scores through store.save (score_v2 reads it).

    python3 scripts/scoring/pref.py J01234 up       # 👍 → value level "top"
    python3 scripts/scoring/pref.py J01234 down     # 👎 → value level "exclude"
    python3 scripts/scoring/pref.py J01234 clear    # back to the rule-based level

Run from the main folder (live data). Every call is logged in data/scoring/prefs.jsonl — the labels a later preference
model learns from. The dashboard buttons go through the same apply() via scripts/scoring/pref_server.py (JSA-101).
"""
import datetime as dt, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, os.path.join(ROOT, "scripts", "store"))
import store

PREFS = ("up", "down", "clear")


def apply(ids, pref, via="cli"):
    """Set / clear joey_pref on ids, re-score, log. Returns [{id, pref, company, title, v_level, score, tier}].
    Raises KeyError(list of unknown ids) and writes nothing when an id is not in the store."""
    if pref not in PREFS:
        raise ValueError(f"pref must be one of {PREFS}")
    rows = store.load("jobs"); by = {r["id"]: r for r in rows}
    missing = [i for i in ids if i not in by]
    if missing:
        raise KeyError(missing)
    today = dt.date.today().isoformat()
    for i in ids:
        if pref == "clear":
            by[i].pop("joey_pref", None); by[i].pop("joey_pref_on", None)
        else:
            by[i]["joey_pref"], by[i]["joey_pref_on"] = pref, today
    store.save("jobs", rows)
    log = os.environ.get("JSA_PREFS_LOG") or jpaths.data("scoring", "prefs.jsonl"); os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        for i in ids:
            f.write(json.dumps({"id": i, "pref": pref, "on": today, "title": by[i]["title"], "company": by[i]["company"],
                                "via": via}, ensure_ascii=False) + "\n")
    after = {r["id"]: r for r in store.load("jobs")}
    return [{"id": i, "pref": pref, "company": after[i]["company"], "title": after[i]["title"],
             "v_level": after[i].get("v_level"), "score": after[i].get("score"), "tier": after[i].get("tier")} for i in ids]


def main(a):
    if len(a) < 2 or a[-1] not in PREFS:
        print(__doc__); return 2
    try:
        res = apply(a[:-1], a[-1])
    except KeyError as e:
        print("unknown id:", ", ".join(e.args[0])); return 1
    for r in res:
        print(f"{r['id']} {r['pref']}: {r['company']} — {r['title'][:60]} → {r['v_level']} · {r['score']} · {r['tier']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
