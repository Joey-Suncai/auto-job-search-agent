# Spec: Last email link in the dashboard's "Waiting for you" table (JSA-413)

`tracker_actions(apps, today)` turns tracker rows (dicts with job_id, company, status, action_needed, and maybe last_email,
last_email_date, email_url) into to-do rows. Which rows become to-do rows is unchanged (a row with an open action_needed,
not Rejected / Archived / Withdrawn / No response / Declined by Joey, not a one-time-code or "waiting for the result"
note). Each resulting to-do row gets three more fields copied from the tracker row, as strings:
- `last_email`: the row's `last_email`, or "" when it is missing / None.
- `last_email_date`: the row's `last_email_date`, or "" when missing / None.
- `email_url`: the row's `email_url`, or "" when missing / None. Never invented, never built from other fields.
Values are copied unchanged (no trimming, no reformatting). All other fields of the to-do row are as before.
The to-do row's `job_id` is the tracker row's job_id; the output order is unchanged (dated by deadline, undated after).
