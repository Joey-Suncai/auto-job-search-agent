# Overtime answer on job application forms

The applicant's confirmed answer: he can work overtime on EVENINGS only, never weekends.
Given a form question label, its field type (select / radio / text) and its options, return the answer the form should get:
- Option lists with an "evenings only" style choice ("Just evenings", "Evenings only", "Only evenings", "Weeknights only") → that option.
- Yes / No only → "Yes".
- Options that only combine evenings with weekends ("Yes, evenings and/or weekends"), weekends only, or "No" are never picked when an evenings-only option exists.
- Free text → "Evenings only".
- Questions that do not ask about overtime (e.g. "Are you willing to travel?", "How many hours per week can you work?") → "NOT_OVERTIME".
