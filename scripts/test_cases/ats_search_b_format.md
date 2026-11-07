Return {"cases": [...]}. Each case:
{"name": "...", "fn": "match_posting",
 "args": {"title": str, "location": str, "postings": [[title, url, location], …]},
 "expect": the matched url (string) or null,
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Addition (2026-11-03, b)": 10 cases — single posting with a country-suffixed city elsewhere (null),
same city with country suffix (url), posting location only "United States" / "USA" (url), "Remote" posting (url),
"Multiple Locations" (url), row city empty (url), city named in the row's title (url), titles differing only in the
trailing city tail with different posting cities.
