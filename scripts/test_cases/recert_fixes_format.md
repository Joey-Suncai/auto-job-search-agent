A JSON array of about 30 cases, each with "name", "spec_quote", "fn" ("numeric_answer" | "state_on_review" |
"block_kind_of" | "blocks_of" | "ready"), "args" (numeric_answer: {"label","src","ans"}; state_on_review: {"value","txt"};
block_kind_of: {"section"}; blocks_of: {"fields","kind"}; ready: {"status","reasons"}), "expect" (numeric_answer:
[answer-or-null, source] — for a null answer give source as the literal "number box:" meaning "starts with"; others: the
return value).
