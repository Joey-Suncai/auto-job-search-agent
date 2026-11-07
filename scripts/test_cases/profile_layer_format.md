Return a JSON array of 24-30 cases, mixed across the three groups. Each case:
{"name": "snake_case_unique", "fn": "resolve" | "data_file" | "get" | "answer", ...}
- resolve:   {"env": "custom.json" | null, "env_exists": true|false, "user": true|false, "example": true|false, "expect": "env"|"user"|"example"|"error"}
- data_file: {"name": "wd_profile.json", "env_value": "/tmp/x.json" | null, "user": true|false, "expect": "env"|"user"|"example"}
- get:       {"profile": {...}, "key": "a.b", "default": <any or omitted>, "expect": <value>}
- answer:    {"answers": {rule_id: answer}, "restricted": true|false, "label": "...", "options": [...], "expect_status": "ok"|"unknown", "expect_value": "..." | null}
Only use the six rule ids listed in the spec. Use fictional people (example.com e-mails, 555 phone numbers).
