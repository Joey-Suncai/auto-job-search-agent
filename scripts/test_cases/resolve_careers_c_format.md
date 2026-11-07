{"name": "...", "fn": "same_name" | "pick_lookup" | "borrow_domains" | "script_srcs" | "sitemap_career_urls",
 "args": same_name: {"a": "...", "b": "..."}; pick_lookup: {"company": "...", "suggestions": [...]};
         borrow_domains: {"company": "...", "jobs": [{"company": "...", "url": "...", "ats_url": "..."}]};
         script_srcs: {"page": "<html>", "base": "https://..."}; sitemap_career_urls: {"xml": "..."},
 "expect": same_name: true/false; the others: list of strings,
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Additions (2026-11-03, b)": 4 same_name, 4 pick_lookup, 6 borrow_domains, 4 script_srcs, 3 sitemap_career_urls.
