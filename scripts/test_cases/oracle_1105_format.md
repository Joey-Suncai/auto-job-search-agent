Return {"cases": [...]}. Each case: {"name": str, "fn": "related_question" | "email_value_ok" | "needs_retry", "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}.
related_question: args {"order": [field], "f_key": str, "rows": [row]} (f = the field of order with that key), expect {"label": str, "answer": str} or null. field = {"key", "kind", "label", "value"}; row = {"key"?, "kind", "want"}.
email_value_ok: args {"value": str | null, "email": str}, expect true | false.
needs_retry: args {"row": object | null, "f": {"kind", "value", "options"?, "geo"?}}, expect true | false.
Write 26 cases: related_question 10 (at least 4 with file rows that have no key, one f with nothing above, one list answer, one where the latest row wins), email_value_ok 6, needs_retry 10 (each False reason once, radio / checkbox / text / phone True cases).
