Return a JSON array of about 10 cases: {"name", "why", "fn": "master", "master": {...}, "expect_kinds": [...]} where kinds are
"outcome_first" and, only if a case deliberately breaks them, "verb", "why", "problem", "length", "repeated_verb",
"shape_dominant", "few_shapes". Keep pages at 2–5 bullets in total so the shape rules are easy to keep clean (ceil(0.4×n):
n=2→1, 3→2, 4→2, 5→2 — vary shapes: verb + " to <purpose>", a context phrase first, two clauses joined by ";",
", <word>ing" result clause, a plain verb sentence). Include: first bullet without digit + later digit (fires); single
bullet entry; no digits anywhere; digit first and none later; two entries where only one fires; number words only;
a digit inside a word like "S&P 500" or "Q3" in a later bullet.
