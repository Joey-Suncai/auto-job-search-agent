# detect_ats: long runs blanked first (2026-11-05, JSA-171)
Context: detect_ats(text) scans a page's HTML + URL for links to applicant-tracking systems and returns
[[system, ident], ...] in a fixed preference order, each once. Examples of what it recognises (unchanged):
"https://boards.greenhouse.io/acme" → ["greenhouse", "acme"]; "https://jobs.lever.co/acme" → ["lever", "acme"];
"https://jobs.ashbyhq.com/acme" → ["ashby", "acme"]; "https://acme.icims.com/jobs" → ["icims", "acme.icims.com"];
"https://acme.bamboohr.com/careers" → ["bamboohr", "acme.bamboohr.com"]; "https://acme.breezy.hr" → ["breezy", "acme.breezy.hr"].
Order when several are present: greenhouse before lever before ashby before icims; bamboohr before breezy.
No recognised link → [].

New: before scanning, every run of 300 or more consecutive characters that are letters, digits, "_", "." or "-" is
replaced by a single space (an inline base64 image such as data:image/png;base64,AAAA… or a minified blob). A link
elsewhere in the text is still found. A link that is glued to such a run (the run continues straight into the host name
with no other character in between) is part of the run and is NOT found. A run of fewer than 300 such characters is left
alone. Text of any length (1.5 MB) must be scanned in well under a second.

Return {"cases": [...]}. Each case: {"name": str, "fn": "detect_ats", "args": {"text": str, "pad": [str, int] or null},
"expect": [[system, ident], ...], "spec_quote": str, "ambiguous": false}. To build a long run write it with "pad": the
harness replaces the marker "{PAD}" in text by pad[0] repeated pad[1] times (e.g. "pad": ["A", 400000]).
