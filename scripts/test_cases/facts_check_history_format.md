Return a JSON array of cases, same shape as facts_check cases:
{"name","why","facts": {"entries": [...], "facts": [...]}, "bank_md": "...", "expect": "pass"|"fail",
 "expect_problems": [kinds among "number_drift","no_entry","unmapped","unsupported_number","never_phrase","schema"],
 "expect_stale": ["normalized numbers reported as stale, sorted ascending as strings", ...]}
Facts must be schema-valid unless the case is about schema. Use fictional data. About 12 cases.
