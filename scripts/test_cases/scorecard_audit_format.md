A JSON array of about 30 cases, each with "name", "fn" ("audit_gate" | "window_folders" | "sample" | "audit_cell"),
"spec_quote" and "args" plus the expectation:
- audit_gate (about 12): "args": {"items": [...], "window": [...], "need": int (optional), "noncrit": float (optional)},
  "expect": the full result dict.
- window_folders (about 7): "args": {"results": [...], "recert": {...}|null}, "expect": {platform: [folders]}.
- sample (about 6): "args": {"folders": [...], "audited": [...], "n": int, "seed": str, "first": [...]|null},
  "expect_len": int, "expect_from_first": int|null (how many of the result must be in first; null = not checked).
- audit_cell (about 5): "args": {"g": {...}|null}, "expect": str.
