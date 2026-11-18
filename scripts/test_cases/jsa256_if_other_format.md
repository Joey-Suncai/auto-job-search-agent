kind "followup": {"name": "...", "kind": "followup", "fields": [{"label": "...", "type": "select"|"text"|..., "options": ["..."], "answer": "..." or null}, ...],
 "target": <index in fields of the unanswered field being judged>, "expect": "drop" | "keep" | "keep_with_context", "label": "<expected new label when keep_with_context>", "spec_quote": "..."}
 - answer null = unanswered; "keep" = the unchanged label.
