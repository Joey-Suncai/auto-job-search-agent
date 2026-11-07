# Oracle runner helpers (JSA-220, 2026-11-05)

1. `related_question(order, f, rows)` — `order` is the page's field list in page order (each field: `key`, `kind`,
   `label`, `value`); `f` is one of them; `rows` is the list of result rows so far. It returns the nearest choice
   question ABOVE `f` (kind one of select / pills / pills_multi / radio / checks) as `{"label", "answer"}`; the answer is
   the `want` of the latest row with that field's key and a non-null `want`, else the field's own page `value`; a list
   answer is joined with " | ". None when no choice question is above `f` (or `f` is not in `order`). Rows for file
   uploads (resume, cover letter, transcript) have NO `key` at all — they must simply be ignored, never raise.
2. `email_value_ok(value, email)` — the e-mail step's input before pressing Next: True only when the box holds our
   address (case and surrounding spaces ignored); False for empty / None / a different address; False when our own
   address is empty.
3. `needs_retry(row, f)` — after a fill pass, should a row that was already filled be filled once more? `row` is the
   result row (`want`, optional `error`, optional `gone`), `f` the freshly extracted field (`kind`, `value`, `options`,
   optional `geo`). False when there is no row, `want` is None, the row has an error or is gone, the field is a geo
   (address) list, or the kind is not one of radio / pills / checkbox / select / text / textarea / phone. Checkbox: True
   when bool(value) != bool(want). Radio / pills / select: True unless the page value matches the wanted option
   (case-insensitive, spaces collapsed). Phone: compare the last 10 digits. Text: True when the page value differs
   from want (case-insensitive, spaces collapsed).
