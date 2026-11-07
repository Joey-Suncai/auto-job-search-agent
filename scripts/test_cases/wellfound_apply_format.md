A JSON array of cases. Each case:
{"name": "<unique snake_case>", "fn": "clean_url" | "posting_like" | "pick_external" | "classify" | "page_from_html", "args": {...}, "expect": ...}
- clean_url: args {"url": <string or null>}; expect a string.
- posting_like: args {"url": <string>}; expect true / false.
- pick_external: args {"page": <page record>}; expect a string.
- classify: args {"page": <page record>}; expect {"via": ..., "ats_url": ..., "apply_url": ...} (reason is not checked).
- page_from_html: args {"html": <string>, "url": <string>}; expect a dict with any of the keys "title", "links",
  "buttons", "data_urls" (each compared exactly), and optionally "text_contains": [strings that must appear in text].
Use realistic Wellfound-style pages and real ATS URL shapes (Greenhouse, Lever, Ashby, Workday, iCIMS, SmartRecruiters,
SuccessFactors). About 5 clean_url, 3 posting_like, 5 pick_external, 8 classify, 3 page_from_html.
