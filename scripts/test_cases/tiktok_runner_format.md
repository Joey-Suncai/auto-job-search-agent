Each case: {"name": "...", "fn": "apply_url" | "parse_slots" | "field_of" | "month" | "edu_plan" | "lang_plan" | "work_plan" | "same",
"args": [<positional arguments as JSON>], "expect": <return value as JSON; for the *_plan functions {"plan": [...], "problems_count": <int>, "problems_mention": [<substrings that must appear in the problems, optional>]}>,
"spec_quote": "<the spec sentence the case tests>", "ambiguous": false}
Cover every function (at least 2 cases each, 4+ for edu_plan), including edge cases from the spec.
