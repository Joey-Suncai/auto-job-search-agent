Return {"cases": [...]}. Each case: {"name": str (unique), "label": str, "type": "select" | "radio" | "text" | "textarea" | "checkbox",
"options": [str, ...] (empty for text / textarea / checkbox), "expect": str (the exact answer, an option exactly as written,
"Yes" for a ticked checkbox, or "none" when the rules must not answer), "spec_quote": str, "ambiguous": false}.
Write about 26 cases: 5 current-school text boxes (rule 1), 2 enrolled yes/no (rule 2), 5 current-degree text boxes (rule 3),
4 enrollment-status lists (rule 4, option orders vary), 3 language preference (rule 5), 3 attestation checkboxes (rule 6),
2 "are you local" (rule 7, one Chicago, one another city), 2 near misses from the list. Use realistic ATS wording
(SuccessFactors, Oracle, SmartRecruiters).
