A JSON array. Each case: {"name": "...", "text": "Subject: ...\n<body>", "expect": "<code>" or null,
 "spec_quote": "the spec sentence the case tests", "ambiguous": false}
Cover: codes starting with 19 / 20 (6, 7, 8 digits) right after the trigger and further away; 8-digit dates before the
real code; dates that are not real (month 13, day 32) used as codes; "code is" / "code:" / "passcode -" forms; letters+digits
codes; mails with "Postal Code" or "code of conduct" noise; tokens of 5 or 11 characters; no code at all; realistic
Oracle / Workday / Greenhouse / SmartRecruiters verification mail bodies (with the year 2026 / 2027 in footer or job title).
