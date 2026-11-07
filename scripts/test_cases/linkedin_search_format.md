Return a JSON array of cases, one of:
{"name": "unique_snake_case", "fn": "rel_date", "args": {"text": "..."}, "expect": "YYYY-MM-DD" or ""}
{"name": "unique_snake_case", "fn": "job_id", "args": {"url": "..."}, "expect": "digits" or ""}
{"name": "unique_snake_case", "fn": "parse_card", "args": {"rec": {"id": "...", "lines": ["..."]}}, "expect": {full output dict} or null}
{"name": "unique_snake_case", "fn": "pick_new", "args": {"cards": [{"job_id": "...", "title": "...", "company": "...", "location": "..."}], "ids": ["..."], "pairs": [["company key", "title key"]]}, "expect": ["job_id", ...]}
{"name": "unique_snake_case", "fn": "company_tiers", "args": {"rows": [{"company": "...", "tier": "...", "tier_orig": "..."}]}, "expect": {"company key": "A"}}
today is always 2026-11-01. Mix: about 6 rel_date, 4 job_id, 8 parse_card, 5 pick_new, 3 company_tiers.
