A JSON array of about 26 cases, each with "name", "fn" ("summary" | "audit_gate" | "score"), "spec_quote" and:
- summary (about 9): "args": {"items": [...]}, "expect": the full result dict (all platforms + "all").
- audit_gate (about 9): "args": {"items": [...], "window": [...], "need": int|null, "keep_covered": bool|null},
  "expect": the full result dict.
- score (about 8): "args": {"submits": [{"folder": "2026-11-0X_Name", "at": "2026-11-0XT10:00:00", "platform":
  "greenhouse"|"ashby"}], "wrong": [{"folder", "field", "class": "critical"|"non-critical", "covered": {...}|absent}],
  "recert": {platform: {"since": str, "need": int}}|null}, "expect": {platform: {"critical_wrong": int, "noncrit_wrong":
  int, "recert_wrong": int}} (recert_wrong only for platforms in recert).
