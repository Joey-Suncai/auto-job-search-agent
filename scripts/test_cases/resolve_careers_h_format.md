Return {"cases": [...]}. Each case:
{"name": "...", "fn": "inv_keys" | "inv_hint_of" | "inv_lookup",
 "args": inv_keys {"name": str} · inv_hint_of {"fname": str, "name": str, "url": str} ·
   inv_lookup {"company": str, "files": {"<system>.csv": "<full CSV text including header>"}},
 "expect": inv_keys → list of strings · inv_hint_of → [system, ident] or null (ident a string; for Workday urls give null-free
   form only if you are sure — prefer Greenhouse / Lever / Ashby / iCIMS / SmartRecruiters urls) · inv_lookup → list of [system, ident],
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Addition (2026-11-03, h)": 20 cases — inv_keys 6, inv_hint_of 7, inv_lookup 7 (two files, a phenom-style
row, duplicate hints, a name that differs only by suffix, no hit).
