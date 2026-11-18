# Overtime answer on job application forms (JSA-317; supersedes the JSA-050 "evenings only" spec)

The applicant's confirmed answer (2026-11-11): he CAN work overtime, on evenings AND weekends, whenever needed.
Any overtime option is acceptable to him; he never answers No.
Given a form question label, its field type (select / radio / text) and its options, return the answer the form should get:
- Preference order among the offered options: an option that combines evenings and weekends ("Yes, evenings and/or
  weekends", "Evenings and weekends", "Evenings & weekends") → else an any-time / as-needed / flexible option
  ("Any time", "Anytime", "As needed", "Flexible") → else a plain Yes ("Yes", "Yes, I can") → else an evenings-only
  option ("Evenings only", "Just evenings", "Weeknights only") → else a weekends-only option.
- "No" / "Not at this time" is never picked while any of the above is offered.
- Free text → "Yes — evenings and weekends when needed".
- Questions that do not ask about overtime (e.g. "Are you willing to travel?", "How many hours per week can you work?")
  → "NOT_OVERTIME".
