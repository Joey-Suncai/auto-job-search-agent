Return {"cases": [...]}; each case: {"name": "short_unique_snake_case", "value": "<the option text>", "expect": true|false,
"rule": "<quoted spec sentence>", "ambiguous": false}. Mix accepted and refused options; include prefixed forms with
each separator, prefixed forms whose prefix or full name hits a never-acceptable rule (e.g. "MBA - Master of Science"),
unprefixed forms, long words that are not abbreviations ("Bachelors - Arts"), and odd spacing.
