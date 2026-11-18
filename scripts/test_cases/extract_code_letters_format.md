A JSON array. Each case: {"name": "...", "text": "Subject: ...\n<body>", "n": <integer or null>, "expect": "<code>" or null,
 "spec_quote": "the spec sentence the case tests", "ambiguous": false}
Write "\n" for line breaks inside text. Cover: Greenhouse mails "Security code for your application to <Company>" whose body
has "Copy and paste this code into the security code field on your application:" then the code alone on the next line
(letters-only mixed-case codes, letters+digits codes, digit codes, company names containing a digit like a Greenhouse employer or C3 AI,
a year line like 2027 in the subject); letters-only codes right after "code:" / "code is"; ALL-CAPS words (REQUIRED,
EXPIRED, ATTENTION, CONFIRMED, PASSWORD, IMPORTANT), all-lower words and Capitalized words in code positions that must
NOT match; letters-only tokens of the wrong length with n=8 and with n=6; n given vs null; letters-only tokens further away
(not in a code position) that must be ignored; digit codes starting with 19 / 20; 8-digit dates further away; no code.
