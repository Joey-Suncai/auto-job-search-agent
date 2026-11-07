Return a JSON array of cases, one of:
{"name": "unique_snake_case", "fn": "parse_board", "url": "...", "expect": ["lever", "quantco"] or null}
{"name": "unique_snake_case", "fn": "posting_id", "url": "...", "expect": "uuid or empty string"}
{"name": "unique_snake_case", "fn": "keep_posting", "title": "...", "location": "...", "expect": true}
Mostly keep_posting cases (at least 14).
