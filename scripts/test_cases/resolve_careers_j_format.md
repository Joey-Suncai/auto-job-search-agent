Return {"cases": [...]}. Each case:
{"name": "...", "fn": "career_links" | "borrow_domains",
 "args": career_links {"page": str (short HTML), "base": str} · borrow_domains {"company": str, "jobs": [{"company", "url", "ats_url"}]},
 "expect": list of strings, "spec_quote": "...", "ambiguous": false}
Write only cases for the "Skip words, 2026-11-04 (j, JSA-137)" bullet combined with the earlier career_links / borrow_domains
rules: 10 cases — career_links 7 (Instagram / Facebook / YouTube / x.com / twitter.com "Join us" or "Careers" links dropped, a
box.com or netflix.com careers link kept, a mix with the company's own /careers link), borrow_domains 3 (a row whose url is on
facebook.com / instagram.com lends nothing; x.com vs a host ending in "x.com" such as "fedex.com").
