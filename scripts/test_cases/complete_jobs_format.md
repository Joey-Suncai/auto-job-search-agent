Each case is a JSON object:
{
 "name": "short id",
 "row": { … one job row as stored … },
 "companies": [ { "company": "...", "sponsorship": "...", "h1b_fy25": 12, … } ],   // may be []
 "expect": { "field": value, … },          // only the fields this case checks, with their exact expected values
 "expect_absent": ["field"],              // fields that must still be absent (optional)
 "spec_quote": "the sentence(s) of the spec this case tests",
 "ambiguous": false
}
