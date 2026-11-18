A JSON array of 26 cases, each one of two kinds:
{"name": "<unique snake_case>", "set": "wrong", "reading": {"shape": "...", "subject": "...", "fact_key": "...", "negated": true|false, "degree": "...", "confidence": "high|low"},
 "gold": {"keys": [..], "shape": [..], "subject": [..], "negated": true|false|null, "degree": [..] | null}, "expect": "right|ask|wrong"}
{"name": "<unique snake_case>", "set": "right", "reading": {same fields}, "gold": {"key": "...", "answer": "..."},
 "facts": {"<key>": {"yes": true|false} or {"text": "..."} or both}, "expect": "same|ask|new_wrong"}
About half of each set. Cover every ask condition (including other_person with a key about others, which does NOT ask),
gold keys containing "none", wrong shape / subject / negated / degree, negated yes-no answers, two different keys with the
same value, a yes_no shape on a value fact, a paragraph shape on a yes fact, and a fact key missing from facts.
