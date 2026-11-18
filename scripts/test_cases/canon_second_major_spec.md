# Spec: second major / minor answers in the canonical-answer audit, and known-mismatch records (JSA-293)

## A. `canon.audit(records)` on a second-major / minor question
The audit checks what an application form says against the candidate's facts and returns a list of mismatches
(empty list = fine). The candidate has ONE major per degree (M.S. Applied Data Science; B.A. Economics) and NO second
major and NO minor on file. His decision: a "second major / minor" question is left EMPTY (or answered with a none-like
option).

A record is {"label", "value", "required": true}. A label may be "Section (entry): Field", e.g.
"Education (UIUC): Secondary Major" — only the part after the colon is the question.

A label is a SECOND-major question when it contains (case-insensitive) "second", "secondary", "double", "additional",
"2nd" or "other" directly followed by "major", "discipline", "field", "field of study" or "concentration"; or the word
"minor"; or "major 2" / "major #2" / "major two". BUT a label that asks "major and minor" / "major(s) & minor" /
"major / any minor" or contains "in addition to" asks the MAIN major, not a second one.

Expected results (only consider mismatches whose key is "education_field"; ignore other keys):
1. Second-major question, value empty or none-like ("None", "N/A", "n/a", "NA", "Not applicable", "No minor",
   "No second major", "-") → no education_field mismatch.
2. Main-major question (e.g. "Major", "Field of Study", "What is your major and minor?") with an EMPTY value → an
   education_field mismatch with reason "empty".
3. Main-major question with "Data Science" or "Applied Data Science" → no education_field mismatch.

## B. `replay.load_reasons(path)` — the decision records of the form replay
A JSONL file; each line {"key", "status", "value", "reason", optional "kind": "canon"}. The function returns
{key: record}, the LATEST line per key wins, except: when an earlier line for the same key has kind "canon" and a later
line WITHOUT kind "canon" has the same status AND value, the returned record is the later line with kind "canon" added
(a plain reason must not erase an accepted canon mismatch for the same answer). If the later line has a different status
or value, it wins as is (no kind "canon"). A later line with kind "canon" always wins as is. Malformed lines are skipped.
