Return {"cases": [...]}. Each case is one of:
1. {"name": "...", "fn": "lever_urls", "args": {"page": "short HTML with <input> tags"}, "expect": [{"key": str, "label": str, "required": bool}, ...], "spec_quote": "...", "ambiguous": false}
2. {"name": "...", "fn": "optional_essay", "args": {"field": {...}}, "expect": bool, "spec_quote": "...", "ambiguous": false}
3. {"name": "...", "fn": "city_state", "args": {"label": str, "type": "text" | "textarea"}, "expect": "Chicago, IL" | null, "spec_quote": "...", "ambiguous": false}   // null = not answered by city_state
Write 24 cases: lever_urls 9, optional_essay 9, city_state 6.
