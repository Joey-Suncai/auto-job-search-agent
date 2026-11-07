A JSON array of 12 cases: {"name": str, "fn": "muted", "env": {…}, "expect": true|false} for 9 cases (missing key, "",
"0", " 0 ", "1", "yes", "false", "  ", other keys only), and 3 cases {"name", "fn": "notify", "env": {…}, "title": str,
"body": str, "expect_calls": 0 or "≥1", "expect": [] or "nonempty"} (muted → 0 calls and []; not muted → ≥1 call).
