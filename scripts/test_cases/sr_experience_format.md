Return {"cases": [...]}. Each case: {"name": str, "fn": "picker_ym" | "ym_of" | "experience_required" | "exp_entries" | "location_option", "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}.
picker_ym / ym_of: args {"value": str | null}, expect "YYYY-MM" or null.
experience_required: args {"cfg": object | null}, expect true / false.
exp_entries: args {"work": [object] | null}, expect the full output list (every key of every dict).
location_option: args {"city": str, "options": [str]}, expect a string or null.
Write 30 cases: picker_ym 8, ym_of 3, experience_required 6, exp_entries 7 (ordering, current, missing title / company / From, bad To, whitespace), location_option 6 (incl. the Chicago Heights near miss and the "Cannot find" entry).
