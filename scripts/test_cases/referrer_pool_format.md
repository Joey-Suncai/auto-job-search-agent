# Case format (JSON)
Return {"cases": [ … ]}, each case:

```json
{
  "name": "snake_case_unique_name",
  "args": {
    "label": "the question exactly as the form shows it",
    "type": "radio | select | checkbox | text | textarea",
    "options": ["…"],
    "company": "the hiring company name as the application passes it, or null when none is given"
  },
  "expect": {"status": "ok", "value": "<the exact answer / option text>"}
         or {"status": "ok", "leave": true}
         or {"status": "unknown", "ask": true}
         or {"status": "unknown"},
  "quote": "the spec sentence this outcome comes from"
}
```

- `options` is `[]` for text / textarea boxes; a single checkbox has one option (its own text).
- `{"status": "unknown", "ask": true}` = the candidate must be asked (the runner stops; no model may guess it).
- `{"status": "unknown"}` = left unanswered (ask may be true or false).
- Cover: in-pool companies including name variants (→ ask); not-in-pool companies with Yes/No lists, None lists, single
  checkboxes, text boxes with and without a "type N/A / write None" instruction, name boxes, know-anyone questions
  (→ No / N/A / None / leave); no company (→ ask); how-did-you-hear lists that contain "Employee referral" (never picked,
  in and out of the pool); recruiter questions (always No, even for an in-pool company or no company); near misses
  between similar company names.
