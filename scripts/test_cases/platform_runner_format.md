A JSON array of 24 cases, each one of:
{"name": str, "fn": "runner_status", "args": {"platform": str or null}, "expect": "ready"|"testing"|"none"|"unknown"}
{"name": str, "fn": "runner_fields", "args": {"row": {...}}, "expect": {"platform": str, "runner": str}}
About 10 runner_status cases (every group, null, "") and 14 runner_fields cases (ats_url wins over url, only url, LinkedIn /
Wellfound url with no ats_url, subdomains, missing keys, empty strings, a known no-runner platform).
