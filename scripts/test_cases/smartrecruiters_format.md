Return {"cases": [...]}. Each case: {"name": str, "fn": "parse_posting" | "clean_label" | "plan_questions" | "if_other", "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}.
parse_posting: args {"url"}, expect object or null. clean_label: args {"text"}, expect string. plan_questions: args {"raw": [...]}, expect list. if_other: args {"label"}, expect bool.
Write 28 cases: parse_posting 10, clean_label 6, plan_questions 6, if_other 6.
