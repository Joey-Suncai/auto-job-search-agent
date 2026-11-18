Return a JSON array of cases: {"name","why","fn": "assess" | "missing_tools", "role": {...}, "facts": {...},
 "min_weight": (optional), "proven_share": (optional),
 for assess: "expect": [{"id", "level", "coverage" (optional), "facts" (optional list), "missing" (optional list)}]  — one entry per returned row, in order;
 for missing_tools: "expect": [["Tool", 0.12], ...]}
Show the coverage arithmetic in "why". About 18 assess cases (every level, thresholds exactly at 0.5, min_weight filtering, resume_ok false, whole-token traps like "R" vs "R&D", "SQL" vs "NoSQL") and 6 missing_tools cases.
