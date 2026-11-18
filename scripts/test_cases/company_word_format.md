A JSON array of 26–27 cases: {"name": "<unique snake_case>", "company": "<hiring company>", "label": "<question text>",
"type": "radio|select|combo|text|textarea", "options": [strings], "required": true|false,
"expect": "employment_no" | "employment_yes" | "applied" | "not_filled" | "personal_email"}.
"employment_no" = answered as the employment question with No (or the No-type option); "employment_yes" = a question
about RESUME_EMPLOYER_A / RESUME_EMPLOYER_B, answered Yes; "applied" = the applying-before question (answered from the
tracker, the case does not say Yes or No); "not_filled" = the rules give no value (left empty / asked);
"personal_email" = his personal e-mail. Use company names that contain rule words (a Workday employer, Applied Intuition,
an employer Surgical, Verify Inc, Everpure, Priority Health, Current Health, ApplyBoard, Prior Labs …) and some without.
Vary wording, long sentence options ("No, I have never worked for …"), and include look-alikes.
