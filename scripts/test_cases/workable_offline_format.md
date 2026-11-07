Each case: {"id": "w1", "fn": "offline_unknowns" | "offline", "input": {...}, "expect": ..., "spec": "<quoted>"}.
- offline_unknowns: input {"fields": [{"key","label","type","required","options"}...], "ans": {key: {"status", "value"}}, "missing": [{"id","label"}...]} → expect list.
- offline: input {"ats": "...", "dry_run": bool} → expect bool.
