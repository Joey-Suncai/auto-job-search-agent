# convert_fields — old per-runner field records → one row shape (JSA-187)

`rows_of(folder)` reads ONE application-run folder and returns (ats, url, rows) or None. Each row is
{question, planned, page, source, type, required, ok, options}. Files are tried in this order; the first that yields at
least one row wins:
1. `form_check.json` — fields in `fields`, or nested in `sections[].fields` / `steps[].fields` (all are collected, top-level
   first). Field keys: label (or key), want = planned, page = value on the page, rule or source or why = source,
   type or kind = type, required, ok, options. ats = the file's `ats` key (often absent → None); url = `posting` or `url`.
2. `wd_log.json` — `pages[].fields` with label, answer (= planned), value, status, source, type, required. The page value (JSA-320, 2026-11-11): a field with its own `page` (logs from 2026-11-11) keeps it; in an older log, `value` was read BEFORE the fill, so a field with status "ok" that is not listed in the log's `failed` ({section, label}) has page = its answer; any other field has page = value.
   ok = true when status is "ok", "keep" or "skip"; false for any other status (e.g. "needs_user"). ats = "workday",
   url = the file's `url`.
3. `plan.json` (+ optional `verify.json`) — `fields` with label, answer, status. A field is ok only when verify.json says
   `pass: true`, the field's label is not in verify.json `bad`, and the field's status is "ok"; then page = answer,
   otherwise page = null. Without verify.json nothing is ok. ats = plan's `ats`, default "greenhouse"; url = plan's `url`.
- A folder with none of these files, or only files with zero fields, gives None. A file that is not valid JSON gives None.
- `required` is always a boolean (missing → false). `question` is the label cut to 300 characters.
