A JSON array of 24 cases: {"name": str, "input": str or null, "expect_exact": str or null (only for the five
eligibility values, plain English text and null; else null), "must_contain": [substrings that must appear in the output],
"no_cjk": true|false (true when rule 2 applies)}. About 6 exact cases (the five values, one with spaces), 2 English-only,
1 null, and 15 reason strings combining 1–4 phrases with real-looking J-numbers, dates and numbers (must_contain lists
those numbers / dates / J-numbers / English words such as "co-op", "JD", "MBA").
