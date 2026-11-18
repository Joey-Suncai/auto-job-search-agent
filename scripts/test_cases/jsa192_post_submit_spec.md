# After-submit review: qa proposals from verified DeepSeek triage answers, and doubts that wait too long (JSA-192)

Nothing here writes to the saved question-and-answer table (qa): it only PROPOSES; the candidate decides.

## Field lines
The fields corpus has one line per form field of a run: {folder, question, planned, page, source, options, ok}. `source`
"ds_answers.json" = the answer came from the DeepSeek triage (a saved-fact mapping). `page` = what the runner read back
from the page after filling; `ok` true = the page value matched the plan.

## Audit items
The independent audit (after a submit) has one item per checked answer: {folder, question, check, judged}. An item is
VERIFIED RIGHT when `judged` is "right", or when `judged` is empty (null) and `check` is "right". `judged` "wrong" or
(`judged` empty and `check` "wrong") = WRONG. Anything else (check "unsure" with no judgment) = pending.

## qa proposals
A proposal is made for a (question, answer) pair when, counting each folder once:
- at least 3 DIFFERENT folders have a field line with source "ds_answers.json", the same normalised question and the same
  normalised planned answer, with ok not false and page equal to planned (case-insensitive, trimmed; an empty page counts
  as equal only when planned is empty), AND
- for at least 3 of those folders the audit item for that folder and question is VERIFIED RIGHT, AND
- no audit item for that question and that answer is WRONG in any folder, AND
- the question is not already covered (the caller passes the set of normalised questions the qa table or a rule already
  answers; a proposal for a covered question is not made).
Normalising a question or an answer: lower case, every run of characters other than a-z and 0-9 becomes one space, trimmed.
A proposal = {question (the original text of the first folder's line), answer (original planned text of the first folder),
options (the first non-empty options list seen), folders (sorted, the verified-right ones only), n (their count)}.
Proposals are sorted by n descending, then question ascending.

## overdue doubts
An audit item is a DOUBT when it is not verified right and not wrong, i.e. pending (check "unsure" or "wrong" with
judged empty counts as WRONG above, so only check "unsure" / missing with no judgment). A doubt is OVERDUE when its audited
date (YYYY-MM-DD) is at least 2 days before today. overdue(items, today) returns the folder + question of every overdue
doubt, sorted by audited date then folder; items with no audited date are never overdue.

## Review changes (2026-11-17)
- Three proposals witnesses must be three DIFFERENT companies (tenant, else the first word of the folder name after the date), not three folders.
- run() never proposes risky questions (work authorization, record, EEO, contact; scripts/field_class.py), asks the rules as the forms showed the question, and carries status (open / declined / added) and first_seen over between runs.
