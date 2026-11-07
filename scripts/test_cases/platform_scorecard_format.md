Each case is a JSON object:
{"name": "short id",
 "results": [ ... ], "emails": [ ... ], "fmap": {...}, "ds_cost": {...}, "wrong": [ ... ], "today": "YYYY-MM-DD",
 "expect": {"<platform>": {only the output keys this case checks, with their exact values; rates rounded to 4 decimals}},
 "expect_absent": ["platform names that must not appear"],
 "spec_quote": "the rule(s) tested", "ambiguous": false}
Keep each case small (1–6 folders), except at most two cases that test the 50-submission bar (you may describe those with
a "generate": {"platform_url": "...", "n": 50, "status": "submitted", "secs": 10, "day": "2026-10-01"} block instead of
listing lines: n folders named "2026-10-01_GenN" each with one line, job id "JN", and one Confirmation e-mail on that day).
