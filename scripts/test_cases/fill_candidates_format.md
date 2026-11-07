Return a JSON array. Each case is one object:
{"name": "short-unique-name", "input": {"selection": {...}, "base": {...}, "bank": {...}, "pool": {...}, "jd": "..."},
 "expect": [["bullet", "HP", "HP04"], ["skill", null, "SK5"], ...]}
Keep each case small: 2-3 entries, ≤ 4 base bullets per entry, ≤ 5 skill lines, short texts, short JD. Cover: nothing dropped (empty
output), a dropped bullet, swapped variant with equal tags (skipped), entry already at base+1, total already at base+1, dropped skill line,
skill line whose label is already selected, ID missing from bank/pool, JD-relevance ordering, ties in base order, stop words not counting.
Count JD word overlaps carefully.
