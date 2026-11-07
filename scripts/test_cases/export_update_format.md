Return a JSON object {"cases": [...]} with 26 cases, each one of:
{"name": "snake_case_unique", "fn": "parse_version", "v": "v0.2", "expect": [0, 2, 0]}          (expect null when invalid; "v" may be a non-string JSON value such as 2 or null)
{"name": "...", "fn": "release_message", "version": "v0.3", "expect": "auto-job-search-agent v0.3 (public export)"}
{"name": "...", "fn": "preflight", "args": {"version": "v0.2", "tags": ["v0.1"], "dirty": false, "behind": 0, "branch": "main", "has_commits": true}, "expect": []}
{"name": "...", "fn": "stale_paths", "clone_tracked": ["a.py", "b.py"], "exported": ["a.py"], "expect": ["b.py"]}
Add "spec_sentence" to every case. Mix: about 7 parse_version, 1 release_message, 11 preflight (combinations of codes), 7 stale_paths.
