A JSON array of cases, two kinds:
{"name": str, "fn": "is_vague", "text": str, "expect": true|false, "spec_quote": str}
{"name": str, "fn": "rules_action", "kind": str, "subject": str, "body": str, "date": "YYYY-MM-DD",
 "expect_action": str (the exact action text), "expect_deadline": "YYYY-MM-DD" or "", "expect_reread": true|false, "spec_quote": str}
About 6 is_vague cases and 20 rules_action cases: every kind, each deadline form (within days / business days / hours /
word numbers, explicit dates with and without year, a year rollover, a past date ignored, two dates → earliest), platform
names, durations incl. one preceded by "within", the three interview branches, Action sentence cleaning (URL, leading
please, long sentence cut, trailing colon), and the no-sentence re-read case. Write realistic recruiting e-mail text.
