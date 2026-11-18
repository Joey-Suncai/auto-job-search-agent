A JSON array of 24 cases, each one of two kinds:
{"name": "<unique snake_case>", "kind": "majority", "agree": 2 or 3, "reads": [reading, reading, reading], "expect_asks": true|false, "expect_fact_key": "<fact_key of the result>"}
{"name": "<unique snake_case>", "kind": "haiku", "ds": reading, "hk": reading (may carry "error": true), "expect_asks": true|false}
A reading is {"fact_key": "...", "shape": "...", "negated": true|false, "subject": "...", "confidence": "high|low"} (negated may be left out).
Use fact keys like spons_now, spons_future, citizen_pr, first_name, marketing, referral, gpa, none, unknown; shapes fill, yes_no, choice, paragraph, subscription, unclear.
About 14 majority and 10 haiku cases. Cover: 3/3 agree, 2/3 agree with agree 2 and with agree 3, all different, agreement except negated, agreement except subject,
missing negated vs false, a winning group with low confidence, three unknown readings, Haiku same except subject, Haiku different shape / key / negated, Haiku error, Haiku asks, ds asks.
For a result that asks, expect_fact_key is the fact_key of the result reading if one group won, else the fact_key of the first reading.
