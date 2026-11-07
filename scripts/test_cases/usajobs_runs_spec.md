# usajobs_search.runs_for(eligibility) — spec (2026-11-03)
`eligibility` is the profile's eligibility object, e.g. {"needs_sponsorship": true, "citizen_or_pr": false, ...}.
Return True only when it is a dict whose "citizen_or_pr" is exactly the boolean true; otherwise False (missing key,
false, null, the string "true", 1, a non-dict such as null / a list / a string).
