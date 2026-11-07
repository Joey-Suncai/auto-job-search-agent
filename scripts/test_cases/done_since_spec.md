# done_since.py — spec (JSA-126)

Tracker rows are dicts like {"job_id": "J00862", "company": "a Workday employer", "title": "Data Scientist Intern",
"status": "Applied", "action_done": [...]}. `action_done` is a list of entries {"on": "<ISO date>", "action": "<text>"}
(oldest first); entries carry ONLY on and action — job_id, company and title are fields of the ROW, not of the entry
(any other keys inside an entry are ignored). An entry becomes the tuple (row job_id, entry on, …) written as
(on, job_id, company, title, action), all strings; a row missing job_id / company / title, or an entry missing action,
gives "".

## entries(rows) → list of tuples
Every entry of every row, as the tuple above. A row with no `action_done` key, null, or an empty list gives nothing.
An entry that is not an object, or whose "on" is missing / empty / null, is skipped. Order: by "on" (as text), then by
job_id (as text), then by the entry's position inside its row's list (earlier first).

## since(rows, day) → list of tuples
The entries(rows) whose "on" is on or after `day` (both ISO dates "YYYY-MM-DD", compared as text), same order.

## new_since(before, rows) → list of tuples
`before` is an earlier entries() result. Return the entries of entries(rows) that are not in `before`, counting
duplicates: if `before` holds one copy of an entry and rows now give two identical copies, one of them is new.
Entries that were in `before` but are gone now (an undo) are simply not returned. Same order as entries(rows).
