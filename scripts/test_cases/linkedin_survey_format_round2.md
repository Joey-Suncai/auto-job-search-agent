
This is a second round: write only hard edge cases and near misses (not the plain examples quoted in the spec) — e.g. counts inside longer page text with other numbers before them, "+" and spaces between number and "results", buttons whose aria-label mixes words, redirect links without a url parameter or with a non-http url, subdomains of linkedin.com, pick_sample with n larger than all ids.
A JSON array of cases: {"name": "<unique snake_case>", "fn": "<search_url|parse_count|classify_button|link_target|card_easy|pick_sample|share>", "args": {...}, "expect": ...}.
- search_url: args {"keyword": str, "easy": bool (optional), "start": int (optional)}; expect {"path": "/jobs/search/", "query": {param: value as decoded string}} — the harness parses the URL and compares host www.linkedin.com, the path and the decoded query parameters (order does not matter).
- parse_count: args {"text": str}; expect int or null.
- classify_button: args {"text": str}; expect "easy" | "external" | "unknown".
- link_target: args {"href": str or null}; expect str.
- card_easy: args {"lines": [str]}; expect true/false.
- pick_sample: args {"groups": [[keyword, [ids]]], "n": int}; expect [ids].
- share: args {"part": number or null, "total": number or null}; expect number or null.
Cover every function (at least 3 cases each, more for parse_count, classify_button and link_target): commas, K suffix,
"Over", "No matching jobs found", near misses; button rule order (e.g. "Applied" vs "Apply"); redirect decoding,
linkedin-internal links, www and port removal; round-robin with repeats and short groups.
