Return {"cases": [...]}. Each case:
{"name": "...", "fn": "kind" | "detect_ats" | "norm_title" | "wd_queries",
 "args": kind {"url": str} · detect_ats {"text": str} · norm_title {"t": str} · wd_queries {"title": str},
 "expect": kind → string or null · detect_ats → list of [system, ident] (ident a string here) · norm_title → string · wd_queries → list of strings,
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Addition (2026-11-03, e)": 28 cases — kind 6 (incl. near misses), detect_ats 12 (each new system,
the ultipro n<digits> form, smartrecruiters www with a vendor page vs a company slug, order when several appear),
norm_title 5, wd_queries 5.
