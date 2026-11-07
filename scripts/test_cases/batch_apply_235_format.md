Each case: {"id": "o1", "fn": <fn>, "input": {...}, "expect": <value>, "spec": "<quoted spec sentence>"}.
- "offline": input {"ats": "<platform>", "dry_run": true|false} → expect true/false.
- "offline_items": input {"needs_user": [{"key","label","options"}...], "gate_items": [{"kind","required","msg","evidence"}...], "given": [<answers.json keys>]} → expect [{"question","options","kind"}...].
- "outcome": input {"status": "<word>"} → expect "done" | "needs-joey" | "rerun".
- "inherited": input {"holder": {"pid": ...} or null, "env_pid": "<string or null>", "parent_chain": [ints]} → expect true/false.
- "describe": input {"holder": {"pid","who","at"} or null} → expect the string.
