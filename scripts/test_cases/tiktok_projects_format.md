Each case: {"name": "...", "fn": "project_plan",
"args": [<entries>, <projects>], "expect": {"plan": [<plan items; only the keys listed are compared>], "problems_count": <int>, "problems_mention": [<substrings that must appear in some problem, optional>]},
"spec_quote": "<the spec sentence the case tests>", "ambiguous": false}
Cover: a club role read as a project, real projects matched, missing projects added (idx null), ongoing end → "Present",
month formats, used-once, order, missing match_re, empty / null names, empty config, extra whitespace.
