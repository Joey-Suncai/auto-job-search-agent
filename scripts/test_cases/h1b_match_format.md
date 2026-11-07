Return a JSON array. Each case is one object:
{"name": "short-unique-name", "fn": "norm" | "lookup" | "group_key" | "refresh" | "merge", "input": {...}, "expect": {...}}
- fn "norm": input {"name": "..."}; expect {"key": "..."}
- fn "lookup": input {"records": [{"name", "fy25", "total", "first"}, ...], "company": "..."};
  expect {"fy25": int, "total": int, "first": int or null, "names": [sorted list of hit employer names]}
  (names: the display name of each hit employer = the name of the first record that created it; compare as a sorted set)
- fn "group_key": input {"a": "...", "b": "..."}; expect {"same": true | false}   (same = group keys equal; NOT_SAME ignored here)
- fn "refresh": input {"row": {...}, "facts": {"fy25", "total", "first"}}; expect {"row": {...full output row...}}
- fn "merge": input {"records": [...H-1B records...], "rows": [company rows: company, open_roles, internships, new_grad,
  a_roles, best_score, best_role, best_tier, gc_sponsor, gc_perm, gc_months, referral, contacts, warm_path, tracks,
  sponsorship, h1b_fy25, h1b_total, h1b_since]}; expect {"rows": [output rows sorted by company], "merged": {kept: [other names]}}
  (only the fields given in the input rows are compared)
Keep each case small (≤ 6 records, ≤ 4 rows). Use realistic employer names (big U.S. H-1B sponsors, their legal
entities and brand / unit names) and include near misses that must NOT match.
