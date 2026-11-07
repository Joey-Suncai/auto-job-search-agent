# Close the browser tab when a Workday run ends?

The candidate's computer runs out of memory when application tabs pile up (his rule 2026-11-01): when an automated
Workday application run ends, its browser tab is closed — except when someone will act in that tab right away:
- "needs-user" (the run waits for the candidate's answer to a question, then continues in the same tab) → keep;
- "blocked" or "dry-run" (the run reached the Review page and waits for a reviewer's check before submit) → keep;
- "captcha" (the candidate must solve a CAPTCHA in that tab) → keep;
- "filled" / "review" (form filled, waiting at Review) → keep.
Every other end state closes the tab: "submitted", "already-submitted", "unconfirmed" (submit clicked, confirmation is
checked by e-mail), "handoff" (stopped on an error; it is retried fresh later), "login-timeout" (sign-in not finished),
or any unknown status string.
Return true = close, false = keep.
