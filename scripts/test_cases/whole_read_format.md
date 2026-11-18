Return {"cases": [...]}. Each case: {"name": str, "fn": "select" | "same" | "month" | "ym" | "enabled" | "read_items", "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}.
select: args {"items": [{"key","label","options","type","value","rule"[, "leave"]}], "qa": [{"q": str}]} → expect [the keys selected, in input order].
same: args {"rule": str|[str], "model": str|null, "options": [str]} → expect bool.
month: args {"s": str} → expect int|null.  ym: args {"s": str} → expect [int, int|null] | null.
enabled: args {"env": {..}} → expect bool.
read_items: args {"items": [{"key","label","options","value"}], "answers": {"<key>": "<model answer>" | "UNSURE" | "ERROR"}, "meaning": {"<key>": "SAME" | "DIFFERENT"}} (the injected model returns answers[key] for step 1 and meaning[key] for step 2) → expect {"<key>": {"agree": bool, "how": str}}.
Write 30 cases: select 8, same 9, month 2, ym 2, enabled 3, read_items 6.
