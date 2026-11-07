Return {"cases": [...]}. Each case:
{"name": "...", "fn": "career_links", "args": {"page": str (short HTML), "base": str}, "expect": list of URL strings,
 "spec_quote": "...", "ambiguous": false}
Write only cases for the "career_links (2026-11-03, i)" bullet combined with the career_links ordering rules: 8 cases —
LinkedIn / Indeed / Glassdoor / jobright links dropped, an ATS board link on a skip-word host kept, a careers link on the
company's own site kept, a mix, near misses (a company host that merely contains "link").
