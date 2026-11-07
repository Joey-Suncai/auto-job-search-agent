A JSON array of 24 cases: {"name": "<unique snake_case>", "old": <plan dict or null>, "new": <plan dict or null>, "expect": [strings]}.
Cover: no change, skip_optional → answer, answer → different answer, answer → needs_user, multi-select answers like
"A | B", answers longer than 40 characters (cut), labels longer than 60 characters (cut) and with extra whitespace,
new fields, gone fields, ordering of mixed new/changed/gone, same outcome with a different source, status "ok" with
no answer, file / check_only fields, null plans, plans without "fields".
