# Greenhouse read-back rows for the common closing books (JSA-196)

`gh_rows(plan_fields, bad)` turns the Greenhouse run's plan fields and the verify result's `bad` list into the field rows
the common closing books write (results line counts + fields.jsonl): one row per plan field whose `status` is "ok" (a
planned answer that was filled); fields with any other status (skip_optional, needs_user, absent, file …) give no row.
Each row: {"key", "label" (the plan field's label, else its key), "want" (the plan field's answer, as it is),
"page", "type", "required" (bool), "ok", "source"}.
- `page` is the read-back: when the field's key is in `bad` (a list of {"key", "page", …}) it is that entry's `page`
  (an empty string when it has none) and `ok` is false; otherwise the page matched the plan, so `page` equals `want` and
  `ok` is true.
- `type` is the plan field's type ('' when missing); `source` is the plan field's source ('' when missing).
- Row order = plan order. `bad` may be missing/null/empty (all rows ok). A key in `bad` that is not an "ok" plan field
  makes no row.
