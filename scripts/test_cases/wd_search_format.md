Return a JSON array of test cases. Each case is ONE of:
{"name": "...", "fn": "parse_tenant", "url": "...", "expect": ["host", "tenant", "site"] or null}
{"name": "...", "fn": "keep_posting", "title": "...", "location": "...", "expect": true}
{"name": "...", "fn": "job_key", "path": "...", "expect": "r-12345"}
About 8 cases per function.
