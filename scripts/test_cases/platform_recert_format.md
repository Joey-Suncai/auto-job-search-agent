Return {"cases": [...]}; each case:
{"name": "<unique>",
 "recert": {"<platform>": {"since": "YYYY-MM-DDTHH:MM:SS", "need": <int>}},     // {} = no entries
 "apps": [{"platform": "greenhouse"|"ashby", "submitted_at": "YYYY-MM-DDTHH:MM:SS" | null, "wrong_answers": <int>}],
 "expect": {"<platform>": {"wrong_ok": true|false, "wrong_answers": <total count>}},
 "spec_quote": "...", "ambiguous": false}
Use at most ~14 apps per case. Write ~14 cases incl. exact-boundary times (submitted exactly at `since`).
