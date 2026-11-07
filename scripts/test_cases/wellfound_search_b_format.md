A JSON array of cases. Each case:
{"name": "<unique snake_case>", "fn": "job_id" | "posted_date" | "parse_card" | "pick_new", "args": {...}, "expect": ...}
- job_id: args {"href": <string or null>}; expect a string.
- posted_date: args {"text": <string or null>}; today is always 2026-11-03; expect an ISO date string or "".
- parse_card: args {"rec": {"href", "text", "company", optional "parts": [strings]}}; today is 2026-11-03;
  expect the full dict {"job_id", "company", "title", "location", "posted", "url"} or null.
- pick_new: args {"cards": [parse_card-style dicts], "ids": [job id strings], "pairs": [[normalised company, title key], ...]};
  expect the list of job_id strings of the cards taken, in order.
Cover edge cases. Only parse_card cases, 8 of them, focused on HTML entities (&amp; &#39; &quot; &lt;) in title, company, location lines and parts.
