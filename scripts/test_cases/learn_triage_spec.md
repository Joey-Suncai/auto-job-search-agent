# learn triage — model classification helpers — spec (JSA-400, design learn-model-triage.md approved by Joey 2026-11-17)

`learn.py` collects problem candidates (a question the runner could not fill, a wrong answer, a stop of the runner). A model
(DeepSeek) now decides each candidate's CATEGORY and which candidates are the same problem. The model only classifies; these four pure
functions keep it honest.

Categories: fact, rule, qtype, page, runner, ignore, and unsure (the program's own bucket).

## trial_folder(name, existing=None) -> bool
True when a folder is a trial / test run that must not count as evidence: its name starts with "dry_" or "test_", or equals "out",
or `existing` (a set of the folder names that really exist under the data home's applications/, or None = unknown) is given and `name` is not in it.
An empty / None name is a trial folder (True). Otherwise False.

## validate_item(item, material_text, ids) -> dict
`item` = the model's answer for one candidate: {"id", "category", "group_with": [ids], "evidence": str, "confidence": str}.
`material_text` = the text that was sent to the model for that candidate; `ids` = the set of candidate ids in the same batch.
Returns {"category", "group_with", "evidence", "confidence", "reason"}:
- category must be one of fact, rule, qtype, page, runner, ignore. Anything else (missing, other words, wrong case counts as wrong) → category "unsure", reason "bad category".
- evidence must be a string of at least 8 characters (after stripping) that appears in `material_text` (compare case-insensitively with all whitespace runs collapsed to one space; the evidence is stripped first). Otherwise → category "unsure", reason "evidence not in the material".
- group_with keeps only ids that are in `ids` and different from the item's own id (order kept, no duplicates); anything not a list → [].
- confidence is kept when it is one of high, medium, low, else "low".
- A valid item keeps its category and reason is "".
- `item` not a dict → {"category": "unsure", "group_with": [], "evidence": "", "confidence": "low", "reason": "not an object"}.

## combine_reads(first, second) -> str
`first`, `second` = the category strings of two independent reads of the same candidate (second may be None when it was not read).
- first is not "fact" → first (a second read is only made for "fact").
- first is "fact" and second is "fact" → "fact".
- first is "fact" and second is anything else (including None) → "unsure".

## merge_groups(items) -> list of lists of ids
`items` = [{"id": str, "group_with": [ids]}], the model's grouping claims (validated). Candidates are in the same group when they are linked by
claims in either direction (A names B, or B names A), transitively. Ids named in group_with but not present in `items` are ignored.
Return the groups as sorted id lists, each group sorted, groups sorted by their first id; candidates without a link form a group of one.


(JSA-400 review additions, not part of the generated cases: `material_text` is built only from the question, options, notes and errors of a candidate — never from the program's own words such as found_by / fact_library — and a quote shorter than 8 characters is no evidence. Notes and errors sent to the model are redacted: profile values, e-mail addresses, links and long numbers are hidden.)
