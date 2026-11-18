# Form prefetch: re-reading records saved with cut option lists (JSA-276)

The morning prefetch reads job application forms and saves one record per job: `read_at` (ISO date of the read), `status`
(`ok`, `closed`, `error`, `restricted`, …) and the form's questions in up to three lists named `fields`, `questions` and
`needs`. Each list item may have an `options` list (the choices of a dropdown). Any of the three keys may be missing, may
be a number instead of a list (a count), and list items may be something other than an object (ignored).

Before 2026-11-09 the prefetch kept only the first 60 options of every dropdown, which hid choices such as
"University of Chicago" on long school lists. Records read on or after 2026-11-09 have full lists.

`due(last, today, recheck_days=5, only_new=False)` decides whether the job's form is read again on this run. Rules in order:
1. No previous record (`last` is None/empty) → read.
2. `only_new` is true → not read (only never-read jobs are read).
3. `status` == `closed` → never read again.
4. `status` == `error` → read (retry).
5. NEW: the record was read before 2026-11-09 AND at least one item in `fields`, `questions` or `needs` has exactly 60
   options → read now, whatever its age. 59 or 61 options, or a record read on/after 2026-11-09, do not trigger this.
6. Otherwise read when the record is at least `recheck_days` days old (today − read_at ≥ recheck_days); an unreadable
   `read_at` → read.

`cut_options(last)` is rule 5 alone: true or false.
