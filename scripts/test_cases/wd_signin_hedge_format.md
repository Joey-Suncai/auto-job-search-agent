Return {"cases": [...]}. Each case is one of:
{"name": "unique_snake_case", "fn": "message_kind", "text": "...", "expect": "locked|exists|wrong_password|verify|none", "spec": "quoted spec sentence"}
{"name": "unique_snake_case", "fn": "after_wrong", "s": {"has_long": true, "tried_long": false, "created": false, "mails": [{"date": "2025-10-21", "kind": "other"}], "agent_since": "2026-10-28"}, "expect": "retry_long|old_account|create|give_up", "spec": "quoted spec sentence"}
Write about 16 message_kind cases (hedged vs definite locks, mixed sentences, the generic Workday sentence, warnings about the future, case) and about 12 after_wrong cases (combinations, dates equal to agent_since, both mail kinds at once, no mails, has_long false).
