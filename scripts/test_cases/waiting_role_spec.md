# Spec: Role column of the dashboard's "Waiting for you" table (JSA-423)

`add_roles(rows, applications)` takes the to-do rows (each has `job_id`, possibly empty or missing) and the application
list (each application has `job_id` and `title`). It returns the same rows in the same order, each with a `role` field added.

- A row's role is the `title` of the application whose `job_id` equals the row's `job_id` (the same field as the Tracker's Role).
- The title is returned as stored, except that surrounding whitespace is trimmed.
- If the row has no job_id (empty / missing), or no application has that job_id, or the title is missing / empty / only
  whitespace, or the title is `(unknown role)` (any letter case): the role is `—` (an em dash). Never guess a role from
  the company name or anything else.
- Other fields of the row are unchanged. The input rows are not modified. If several applications share a job_id the first one wins.
- `applications` may be empty or None: every row gets `—`.
