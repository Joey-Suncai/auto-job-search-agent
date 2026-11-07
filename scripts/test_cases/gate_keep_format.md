Each case: {"name": "...", "today": "YYYY-MM-DD",
 "row": {"elig": "...", "elig_reason": "...", "elig_codes": "...", "elig_evidence": "...", "elig_key": "...", "elig_checked": "...", "elig_read_on": "..."}   // any key may be absent
 "result": {"v": "Eligible|Review|Ineligible|Closed|Unverified", "c": "CODE1,CODE2", "e": "evidence", "key": "k"},
 "expect": {only the row keys this case checks, with exact values; use null for "must be absent"},
 "spec_quote": "...", "ambiguous": false}
Do not check elig_reason in rule-1 or rule-3 cases (its wording comes from a separate table); check it in rule-2 cases.
