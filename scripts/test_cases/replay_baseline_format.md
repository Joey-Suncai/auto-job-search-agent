Return {"cases": [...]}; each case:
{"name": "<unique>",
 "corpus": [{"folder": "<name>", "question": "<text>", "filled": "<the answer that was filled on the form>"}],
 "submitted": ["<folder>", ...],
 "audit": [{"folder": "<name>", "check": "right" | "wrong" | "unsure" | null}],   // judged audit items per folder; [] = none
 "baseline": {"<question>": {"status": "ok"|"unknown", "value": "<text or ''>"}},  // questions not listed have no baseline entry
 "reasons": [{"question": "<text>", "value": "<value the reason was recorded for>", "text": "<the reason text>"}],
 "now": {"<question>": {"status": "ok"|"unknown", "value": "<text>"}},          // what the current rules answer
 "qa": null | {"before": {"<question>": {"status": "ok"|"unknown", "value": "<text>"}},   // rules' answers BEFORE the new qa entry (now = after)
               "reason": "<the reason text qa_add records, e.g. 'qa#12 (2026-11-16): Joey 2026-11-16 (prefetch) — …'>"},
 "record_reason": null | "<a --reason text recorded for all current changes before the check (rule 5)>",
 "expect_exit": 0 | 1,                       // of `--check`, run last (after qa / record_reason)
 "expect_record_exit": null | 0 | 2,         // of the record_reason step
 "expect_merged": <int>,                     // forms merged into the baseline by rule 1
 "expect_new": <int>,                        // submitted forms reported "new, not in baseline" (rule 3)
 "expect_reasoned": ["<question>", ...],     // questions that got the qa reason (rule 6); [] when qa is null
 "spec_quote": "...", "ambiguous": false}
Questions are unique within a case; a folder may hold several questions. Signature-date questions use the label
"Date signed" and a value like "11/16/2026". Write ~25 cases; cover every rule, including the traps in rules 1, 4 and 6.
