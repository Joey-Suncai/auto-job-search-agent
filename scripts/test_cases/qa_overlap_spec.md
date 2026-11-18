# Saved question-and-answer table: overlap check and newest-first answers (JSA-277)

The candidate's profile holds a table `qa` of saved answers to form questions. Entry fields: `q` (the question as a form
wrote it), optional `match` (a JavaScript regex literal like "/currently attending/i"), and exactly one answer kind:
`text` (string), `yes` (true/false) or `pick` (list of regex literals choosing an option; `text` then holds the plain
option too). Entries are numbered 1, 2, 3 … in table order; a higher number is newer.

## When an entry catches a question label
An entry catches a label when EITHER its `match` regex finds the label (regex search, not full match), OR its normalised
`q` equals the normalised label, OR its normalised `q` is at least 40 characters long and the normalised label starts
with it. Normalising: lower case; curly apostrophes → '; the word "required" (optionally in parentheses) and "*" removed;
every run of characters other than a-z, 0-9 and ' becomes one space; trimmed.

## Answering a field (qaAnswer)
Every entry that catches the field's label is tried, newest first. For a field with options: the first `pick` regex that
matches an option (trimmed) chooses it; else an option whose normalised text equals the normalised `text`; else for a
`yes` entry the option meaning Yes / No; else (yes = true, a checkbox with exactly one option) that option. A found
option → {status: "ok", value: option, rule: "qa:<n>"}; none → status "unknown" (a miss) for that entry. For a field
without options: `text` → ok with the text; `yes` → ok with "Yes" / "No".
The first entry giving "ok" is the answer. If no entry gives "ok", the answer is the miss of the NEWEST catching entry.
No entry catches the label → no answer (null).

## Saving a new entry (qa_add.py)
Before a new entry is saved, it is placed at the end of the table (it is the newest) and checked against every other entry:
- the other entry catches the new entry's `q` ("catches it"), or
- the new entry catches the other entry's `q` ("it catches").
Any such other entry → the save stops, nothing is written, and those entries are named by number. An entry with the same
normalised `q` as the new one is a duplicate and is refused earlier (unless --replace); it is not part of this check.
The user's choice then: `--replace-entry N` (the new entry takes entry N's place; N is no longer checked), `--narrow-entry N
--narrow-match "/re/i"` (entry N's regex becomes the given one, then the check runs again), or `--add-anyway` (saved
with the overlap).
`--check-overlaps` lists, for every entry, its own `q` when 2+ entries catch it; 0 listed = clean.

## A pattern-only answer on a field without options
An entry saved from a list may hold only regex picks; its `text` is then the first pick's pattern without the slashes and
flags (pick "/^yes$/i" → text "^yes$"). On a field WITHOUT options such an entry gives a miss (status "unknown"), never
the pattern as the answer — so an older catching entry with a plain text or yes answer may still answer. An entry whose
`text` is plain words (pick "/^University of Chicago$/i" with text "University of Chicago") still answers a text field
with its text. On a field WITH options the pattern picks work as usual.
