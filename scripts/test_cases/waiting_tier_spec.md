# Spec: Tier column of the dashboard's "Waiting for you" table (JSA-404)

`add_tiers(rows, jobs)` takes the to-do rows (each has `job_id`, possibly empty or missing) and the job list (each job has
`id`, `tier` and possibly `tier_orig`). It returns the same rows in the same order, each with a `tier` field added.

- A row's tier is the `tier` of the job whose `id` equals the row's `job_id` (values A, B, C, D, ...).
- If the job's tier is `Blocked`, the row shows the job's `tier_orig` (its original tier); if `tier_orig` is missing or
  empty, it shows `Blocked`.
- If the row has no job_id (empty / missing), or no job has that id, or the job's tier is missing / empty: the tier is `—`
  (an em dash). Never guess a tier from the company name or anything else.
- Other fields of the row are unchanged. The input rows are not modified. If several jobs share an id the first one wins.
- `jobs` may be empty or None: every row gets `—`.
