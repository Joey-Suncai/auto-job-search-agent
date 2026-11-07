# pick_same_company(ids, apps, emails, kind)

The daily e-mail check reads company mails about job applications. Sometimes the candidate applied to two or more roles
at one company, and the company's mail names only the company, not the role ("Thank you for applying to SingleStore!").
The reader then returns a list of the candidate job_ids at that company (`ids`). This function decides which tracker row
the mail is recorded against.

Inputs:
- ids: list of job_id strings (may be empty, may contain duplicates, may contain ids that are not in apps).
- apps: list of application rows, each {job_id, company, title, applied_on (YYYY-MM-DD or empty)}.
- emails: list of already-recorded mail rows, each {job_id, type}. type is one of Rejection, Assessment, Interview,
  Offer, Action, Confirmation, Other.
- kind: the type of the new mail (same set of values).

Rules:
1. Only a Confirmation ("application received") is assigned this way. For any other kind return None — a rejection
   or interview at the wrong role would mislead the candidate, so those stay unmatched for a human.
2. Empty ids → None.
3. Ignore ids that are not a job_id in apps. Duplicates count once.
4. Drop rows that already have a recorded Confirmation e-mail (an emails entry with that job_id and type Confirmation).
   Other recorded types (e.g. an Assessment) do not drop the row.
5. From the remaining rows return the one with the earliest applied_on; an empty applied_on sorts before any date.
   Ties → the smaller job_id (string order).
6. Nothing left → None.

Return value: the application row (the dict from apps), or None.
