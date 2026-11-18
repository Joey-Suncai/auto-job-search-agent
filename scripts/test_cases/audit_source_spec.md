# audit_sample.source_check(question, answer) — JSA-261 (Joey 2026-11-09)

Rule (Joey 2026-11-09): for a job-source question ("which job board / site did you see this posting on", "how did you
hear about us"), any filled answer is right — whether he really saw the job there does not matter.

`source_check(question, answer)` returns 'right' or None (None = this check does not decide; another check does).

- The question (trimmed, lower-cased) is a job-source question when it matches any of:
  "how/where did you [one word] hear/find/learn/see" (e.g. "How did you hear about us?", "Where did you first see this
  role?"); "how/where you [one word] heard/found out/learned/saw about/of"; "how were you made aware of"; a question that
  starts with "source", "applicant source", "candidate source", "source of application", "source of referral";
  "which/what/name of the [job] board/site/website" followed within 60 characters by learn/hear/see/saw/find/found
  (e.g. "Please provide the name of the job board where you learned about this position."); a question that is exactly
  "career communi…/job boards" (any spelling after "communi", e.g. "Career Communicatees/Job Boards"); a question that
  starts with "which job board".
- It is NOT a job-source question (→ None) when it also contains "if referred", "name of the/a/an employee|person|referr…",
  "who referred", "root cause", "investigat" or "problem".
- The answer (trimmed) must be non-empty; empty → None.
- An answer that claims a person → None (still checked by the model): it contains "referr", the word "employee",
  "recruiter", "friend", "colleague", "coworker"/"co-worker", "word of mouth", the word "family", "contacted me", "reached
  out", the word "agency", "search firm" or "staffing" (case-insensitive) — a claim that someone contacted or represented him.
- Otherwise 'right' — any filled answer: "Other", "LinkedIn", "Online job board", "Job Board", "Indeed", "Company
  website", "N/A", even a board he did not use.
- A question that is no source question (e.g. "Tell us about a time you taught yourself something", "Why this role?")
  → None, whatever the answer (even "Online job board").
