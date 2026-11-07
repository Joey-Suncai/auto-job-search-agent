Return a JSON array. Each case is one of:
{"name": "snake_case", "fn": "date", "value": "June 14, 2027", "expect": "06/14/2027"}            (expect null = refused)
{"name": "snake_case", "fn": "multi", "value": ["A", "B"] or "A | B", "options": ["A", "B", "C"], "expect": "A | B"}   (expect null = refused)
About half date cases, half multi cases; about 1/3 of all cases are refusals. Cover the edge cases the spec names.
