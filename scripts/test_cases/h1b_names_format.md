Return a JSON array. Each case is one object:
{"name": "short-unique-name", "fn": "lookup", "input": {"records": [{"name", "fy25", "total", "first"}, ...], "company": "..."},
 "expect": {"fy25": int, "total": int, "first": int or null, "names": [sorted list of hit employer names]}}
(names: the display name of each hit employer = the name of the first record that created it; compare as a sorted set)
Focus on the JSA-103 rules: the one-word rule (a single-word brand not in FAMILIES keeps its prefix family only when every
candidate has the same second word), FAMILIES (whole family kept), ENTITIES (raw name checked before norm; exact keys only;
[] = no filings) and NOT_FAMILY — plus their interaction with the older rules (GENERIC, "<brand> IT", ALIASES, "=" roots,
multi-word roots that still take a prefix family). Include near misses that must NOT match and cases that must still match.
Keep each case small (≤ 6 records). Use the employer names from the tables where you can.
