Round 3 (spec amended 2026-11-05): write cases ONLY for the functions search_url, card_title and intern_title — about 7 each,
plain and edge cases (keywords with spaces, "&", "+", start 0 / 25 / 50, easy true and false; titles with "(Verified job)",
leading blank lines, "Intern | Data Science", "Internal", "International", "Co-op", "coop", "Interns", hyphenated
"Intern-Data"). Format:
A JSON array of cases: {"name": "<unique snake_case>", "fn": "<search_url|card_title|intern_title>", "args": {...}, "expect": ...}.
- search_url: args {"keyword": str, "easy": bool (optional), "start": int (optional)}; expect {"path": "/jobs/search-results/", "query": {param: value as decoded string}} — the harness parses the URL and compares host www.linkedin.com, the path and the decoded query parameters (order does not matter).
- card_title: args {"lines": [str]}; expect str.
- intern_title: args {"title": str or null}; expect true/false.
