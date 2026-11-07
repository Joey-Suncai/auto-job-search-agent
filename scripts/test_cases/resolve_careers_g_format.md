Return {"cases": [...]}. Each case:
{"name": "...", "fn": "match_posting",
 "args": {"title": str, "location": str, "postings": list of [title, url, location]},
 "expect": the URL string of the chosen posting, or null,
 "spec_quote": "...", "ambiguous": false}
Write only cases for the "match_posting changes (2026-11-03, g)" bullet, combined with the earlier match_posting rules:
12 cases — clones picked (2), clones but one in another city vs the row (tie broken by city), same title different
locations with no city match → null, the "Greater …" filler words, a city with only short / filler words, a single posting in
another city → null, a single posting in "51 Locations" → chosen, near misses.
