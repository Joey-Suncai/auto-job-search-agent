# plan_changes(old, new) — spec (2026-11-05, JSA-213)

A job-application runner keeps a "plan" for one form: a dict with a list `fields`; each field is a dict with at least
`key` (string id), `label` (question text), `status` (one of "ok", "skip_optional", "needs_user", "file", "check_only")
and, when status is "ok", `answer` (a string). Before filling, the runner rebuilds the plan and logs what changed.

`plan_changes(old, new)` returns a list of strings, one per field whose planned OUTCOME differs:
- A field's outcome = its `answer` converted to a string and cut to its first 40 characters when status is "ok";
  otherwise its status string (e.g. "skip_optional"). (status "ok" with answer missing → the string "None".)
- Fields are matched by `key`. Order: first the fields of the NEW plan in their order, then fields that exist only in the
  OLD plan in the old plan's order.
- A field in both plans with a different outcome → "<label>: <old outcome> → <new outcome>".
- A field only in the new plan → "<label>: new → <new outcome>" (always listed).
- A field only in the old plan → "<label>: <old outcome> → gone".
- Fields with the same outcome are not listed (even if other attributes such as `source` or `label` differ).
- The label shown is the label of the plan the field is listed from (the new plan for fields in it, the old plan for
  "gone" fields), with runs of whitespace collapsed to one space, trimmed, then cut to its first 60 characters.
- The arrow is " → " (space, U+2192, space). Missing/None plans or missing `fields` count as no fields.
