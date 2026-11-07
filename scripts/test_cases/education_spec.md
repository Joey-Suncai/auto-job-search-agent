# Ashby Education History helpers — spec (JSA-056, 2026-11-03)

Month names are English with a capital first letter (January … December). `want` / `got` in edu_same may be JSON strings or already-parsed values.

## education_entries(education)
Pure (tested). The profile's `education` list (newest first) → the entries for a structured Education History field: [{school, degree, major, start_month, start_year, end_month, end_year, current}] in the same order. degree = `degree_full` (else `degree`); major = `major` (else ''); a "YYYY-MM" `start` / `end` → the English month name and the year as strings ('' when missing or not YYYY-MM); current = True only when `current` is true. Entries without a school are dropped.

## edu_same(want, got)
Pure (tested). Education History read-back: `want` = the plan's JSON list of entries (the first is filled), `got` = the page's JSON {school, degree, major}. True when the page's school contains the wanted school (case-insensitive, whitespace collapsed; the page may show a longer official name) and degree / major equal the wanted ones when the entry has them (empty wanted parts are not checked). Unreadable JSON → False.
