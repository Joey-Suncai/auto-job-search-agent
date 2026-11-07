Return a JSON array. Each case is one object:
{"name": "short-unique-name", "fn": "known" | "pick_new" | "to_rows", "input": {...}, "expect": {...}}
- fn "known": input {"rows": [...]}; expect {"keys": [sorted list], "boards": [[kind, board, company], ... sorted], "ab": [sorted list]}
- fn "pick_new": input {"keys": [...], "ab": [...], "results": [[[kind, board], company, data_or_null], ...]};
  expect {"ids": [posting ids in output order], "tiers": [tier per output posting]}
- fn "to_rows": input {"new": [picked postings], "rows": [existing rows], "today": "YYYY-MM-DD"};
  expect {"rows": [{"id", "score", "tier", "source", "track", "added", "ats_url"} for each output row]}  (only these fields are compared)
Use realistic UUIDs for posting ids. Keep each case small (≤ 5 postings).
