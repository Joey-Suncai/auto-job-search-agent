Return {"cases": [...]}. Each case is one of:
{"name": "unique_snake_case", "fn": "message_kind", "text": "...", "expect": "locked|exists|wrong_password|verify|none", "spec": "quoted spec sentence"}
{"name": "unique_snake_case", "fn": "failure_code", "t": {"created": true, "exists_msg": false, "verify_banner": false, "verified": false, "error": "wrong_password", "mails": [{"date": "2025-10-21", "kind": "other"}], "agent_since": "2026-10-28"}, "expect": "locked|old_account|agent_account_password|no_verify_mail|no_answer|other", "spec": "quoted spec sentence"}
Write about 10 message_kind cases and about 18 failure_code cases (combinations, dates equal to agent_since, both mail kinds at once, created false).
