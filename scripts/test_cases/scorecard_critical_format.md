Return {"cases": [...]}; each case:
{"name": "<unique>",
 "recert": {} | {"greenhouse": {"since": "YYYY-MM-DDTHH:MM:SS", "need": <int>}},
 "apps": [{"platform": "greenhouse"|"ashby", "submitted_at": "YYYY-MM-DDTHH:MM:SS" | null,
           "noncrit_answers": <int>,                               // non-critical answers on that form
           "wrong": [{"class": "critical"|"non-critical"} | {"field": "<question text, no class>"}]}],
 "expect": {"<platform>": {"crit_ok": true|false, "noncrit_ok": true|false, "wrong_ok": true|false, "critical_wrong": <int>, "noncrit_wrong": <int>}},
 "spec_quote": "...", "ambiguous": false}
Up to ~12 apps per case. Write ~16 cases including exact 95 % boundaries.
