Return a JSON array of cases, one of:
{"name": "unique_snake_case", "fn": "alt_key", "title": "...", "expect": "..."}
{"name": "unique_snake_case", "fn": "keep", "title": "...", "location": "...", "expect": true}
{"name": "unique_snake_case", "fn": "parse_cards", "html": "<div data-testid=\"job-card\" ...>...</div>", "expect": [{"guid": "...", "company": "...", "title": "...", "location": "..."}]}
{"name": "unique_snake_case", "fn": "pick_new", "store": [{"company": "...", "title": "...", "url": "..."}], "cards": [{"guid": "...", "company": "...", "title": "...", "location": "..."}], "expect": ["<guid of each kept card, in order>"]}
Mix: about 6 alt_key, 10 keep, 5 parse_cards, 6 pick_new. Use realistic Dice titles (junior / entry level / intern) and U.S. locations.
