# A word in the hiring company's name never decides the answer (JSA-336 stop-gap, Joey approved 2026-11-16)

The form-answer rules read a question and pick an answer from the user's facts. Some company names contain words the
rules look for: **Applied** Materials, **Applied** Intuition, **an employer** Surgical, **Verify**, **Ever**pure,
**Prior**ity Health, **Current** Health, **Apply**Board, **Former** Co … A word inside the company name must never change
which question the rules think is being asked.

The user's facts:
- He has worked **only** for the employers on his resume (call them RESUME_EMPLOYER_A and RESUME_EMPLOYER_B). For any other
  company — including the hiring company — "have you (ever / previously / currently) worked at / been employed by /
  interned at / been a contractor for <company>?" is **No**. For a resume employer it is **Yes**.
- "Have you previously applied to <company>?" is answered from his application tracker (Yes when he applied there before
  today, else No) — only when the question really asks about **applying**.
- He has no e-mail address at any employer. His only addresses are his personal e-mail (and, if on file, a secondary
  personal e-mail).

Rules:
1. A question about **having worked / been employed / interned / contracted at the hiring company** is answered as an
   employment question (No, except a resume employer = Yes) — even when the company name contains "Applied", "Apply",
   "Previous", "Prior", "Ever", "Current" or another rule word. It is never answered from the application tracker, and
   never Yes because of a word in the company name.
2. A question that really asks about **applying before** ("Have you previously applied to a Workday employer?",
   "Have you applied to an employer Surgical in the last 12 months?") is still the applying question.
3. A **follow-up that asks for an e-mail address at the company or as an employee** — "If yes, please enter your
   a Workday employer email address", "If you were previously employed, provide your <company> e-mail", "Former employee
   email", "Your <company> work e-mail", "Employee e-mail address" — is **never filled with his personal e-mail**. The
   rules do not answer it: optional → left empty; required → asked (the user answers it). Nothing else (a saved answer,
   an AI answer, the page's prefill) may fill it either.
4. A plain contact e-mail question ("Email", "Email address", "Personal email", "Preferred email address") is still
   answered with his personal e-mail. "Send me emails about new jobs" is an opt-in, not the address.

Real questions (forms corpus):
- "Have you ever worked at a Workday employer as a regular employee, contingent worker, intern, etc.?" (Yes / No) → No
- "If yes, please enter your a Workday employer email address:" (text, optional) → not filled
- "Have you previously worked for Everpure (formerly Pure Storage)?" → No
- "Have you worked at AppLovin or any of its affiliates before?" → No, or asked when no rule reads the wording — never Yes
- "Have you previously applied to work at a Greenhouse employer?" → the tracker (applying question)
