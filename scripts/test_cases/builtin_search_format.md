Return a JSON array of cases, one of:
{"name": "unique_snake_case", "fn": "job_id", "args": {"url": "..."}, "expect": "digits" or ""}
{"name": "unique_snake_case", "fn": "parse_card", "args": {"rec": {"id": "...", "href": "...", "lines": ["..."]}}, "expect": {full output dict} or null}
{"name": "unique_snake_case", "fn": "known", "args": {"rows": [{"company": "...", "title": "...", "url": "...", "ats_url": "...", "elig_key": "..."}]}, "expect": {"ids": ["sorted ..."], "pairs": [["company key", "title key"], "... sorted"]}}
{"name": "unique_snake_case", "fn": "pick_new", "args": {"cards": [{"job_id": "...", "title": "...", "company": "...", "location": "..."}], "ids": ["..."], "pairs": [["company key", "title key"]]}, "expect": ["job_id", ...]}
today is always 2026-11-01. Mix: about 5 job_id, 10 parse_card, 3 known, 6 pick_new.
