Two kinds of case in one list.
Validation case: {"name": "...", "kind": "validate", "method": "POST", "path": "/pref", "headers": {"host": "127.0.0.1:8766", ...},
 "body": "<string>", "expect": [code, {"id","pref"} or {"error": "..."}], "spec_quote": "...", "ambiguous": false}
Apply case: {"name": "...", "kind": "apply", "jobs": [{"id": "J00001", "company": "A", "title": "Data Analyst Intern", "joey_pref": "down"?}],
 "ids": ["J00001"], "pref": "up",
 "expect": {"error": "unknown" or null, "prefs_after": {"<id>": "up"|"down"|null for every job in the table}, "log_lines": <int, lines appended>},
 "spec_quote": "...", "ambiguous": false}
Write about 22 validation cases and 8 apply cases.
