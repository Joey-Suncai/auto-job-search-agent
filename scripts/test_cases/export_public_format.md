Return a JSON array of 26-30 cases, mixed over the four functions:
{"name": "snake_case_unique", "fn": "keep", "path": "repo/relative/path", "expect": true|false}
{"name": "...", "fn": "phone_re", "phone": "555-010-2030", "text": "call (555) 010-2030 today", "expect": true|false}   // does the regex match the text; expect null when phone_re returns None
{"name": "...", "fn": "find_hits", "rel": "a/b.md", "text": "line1\nline2", "terms": [["label", "regex"]], "expect": ["a/b.md:2: label: matched"]}
{"name": "...", "fn": "render", "template": "...", "values": {"REPO": "/x"}, "expect": "rendered text" | "error"}
