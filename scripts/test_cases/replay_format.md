Return {"cases": [...]}; each case:
{"name": "<unique>",
 "corpus": [{"folder": "<name>", "question": "<text>", "type": "radio"|"text"|"select"}],   // [] = no corpus
 "submitted": ["<folder>", ...],
 "baseline": null | {"<question>": {"status": "ok"|"unknown", "value": "<text or ''>"}},     // null = no baseline file yet
 "reasons": [{"question": "<text>", "value": "<new value the reason was recorded for>", "kind": "change" | "known_issue"}],
 "now": {"<question>": {"status": "ok"|"unknown", "value": "<text>", "rule": "<name>"}},     // what the current rules answer
 "expect_exit": 0 | 1,
 "expect_changed": <int>,            // number of changed questions (rule 1)
 "spec_quote": "...", "ambiguous": false}
Questions are unique per case (one folder each unless stated). Write ~22 cases.
