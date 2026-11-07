# Workable offline questions (JSA-235)
`offline_unknowns(fields, ans, missing)` lists the questions Joey must answer before a Workable submit, from the public form
schema alone: every field that is required, is not of type "file", whose answer `ans[key]` is missing or has a status other
than "ok", and whose key is not the `id` of an entry in `missing` (missing = essay boxes not drafted yet — ds_materials drafts
those, so they are not Joey's questions here). Output, in field order: {"question": label, "options": the field's options (a
list, [] when none), "kind": "question"}. A not-required field is never listed, even with no answer.
`offline("workable", false)` is true (Workable publishes its form schema); `offline("workable", true)` is false (--dry-run).
