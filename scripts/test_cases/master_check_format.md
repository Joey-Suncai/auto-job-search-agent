Return a JSON array of cases: {"name","why","facts": {...},"master": {...},
 "expect_kinds": [...kinds above...]}  — a set; empty = no problems. Use small fictional fact bases (entry ids may be jsa, hp, stock, fs, voice
or others). Every case must include every resume entry in the master unless it tests entries_missing. About 20 cases.
Every fact that a bullet cites must have non-empty S, T, A and R (the star_missing rule) unless the case tests star_missing.
Master bullets must mix sentence shapes (no shape on more than ceil(40 %) of the bullets of a case) and follow the why / problem rule. Bold lists may be empty.
Include about 4 cases for bold_too_many / bold_missing / bold_unknown.
