A JSON array of 26 cases: {"name": "<unique snake_case>", "label": "<question text>", "options": [strings],
"is_age_band": true|false, "expect": "<option text, or empty string when is_age_band is false or no band contains 23>"}.
Cover: every recognised label form with and without "?", mixed case, Ashby-style "Under 30 / 30-39 / … / 60 or older /
I prefer not to answer", Lever "18-24 / 25-34", a list with no band containing 23, and at least 10 look-alike labels
that must NOT be age-band questions (eligibility age questions with Yes/No options, words containing "age").
