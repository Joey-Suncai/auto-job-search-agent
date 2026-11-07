A JSON array of 26 cases, two kinds:
{"name": str, "fn": "mark", "row": {...}, "done": true|false, "today": "2026-11-03", "expect_row": {...full row after...}, "expect_error": str|null}
{"name": str, "fn": "validate", "method": "POST"|"GET"|..., "path": str, "headers": {lower-case keys}, "body": "<raw body string>", "expect_code": int, "expect_payload_keys": [keys of the returned dict, sorted] , "expect_payload": {...} (only for code 200)}
About 14 mark cases (done / undo / waits / spaces / 等结果 / existing history / undo after a new action / removing the key) and
12 validate cases for /action (every error code, booleans vs 1 / "true", extra keys, bad ids, query strings, origins).
