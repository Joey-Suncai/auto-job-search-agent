# Whole-question re-read: two false stops (JSA-292)

A form is a list of fields in page order; the re-read gives the model a field's label, its options and CONTEXT = the labels of
the (up to four) fields just before it. A block of the form (an education entry, a job entry) starts with its first box.

## block_context(label, context) → the context list actually shown to the model
A BLOCK STARTER label is, ignoring case, surrounding spaces and a trailing ":" or "*": "School", "School name", "University",
"College", "Institution", "Company", "Company name", "Employer", "Employer name", "Name of school", "Name of employer".
- When the field's own label is a block starter, the previous fields belong to the PREVIOUS block → context = [].
- Otherwise, when the context holds a block starter, context = the context from the LAST block starter in it (that starter
  included) to the end; context without a block starter is unchanged.
- Empty strings in the context are dropped first; the order of the labels never changes.
Example: label "School", context ["High School Name", "Graduation year", "Do you have a degree?"] → []. Label "Degree", context
["Company", "School", "Start date"] → ["School", "Start date"]. Label "GPA", context ["Phone", "Email"] → ["Phone", "Email"].

## same(a, b) additions (free-text answer comparison; both sides plain texts, several parts written "x | y")
Two answers match when, after lower-casing and dropping punctuation, one is a contiguous run of whole words of the other and
the shorter has at least two words ("Data Science" matches "Applied Data Science"; "Science" does not match "Data Science";
"Economics" does not match "Applied Economics" because the shorter has only one word). Parts that are "none", "n/a" or "no
minor" (a none-like part) on the side that has MORE parts are ignored when the other side has no none-like part, so
"Applied Data Science | None" matches "Data Science". Everything that matched before still matches; answers that differ in
content ("Data Science" vs "Economics", "University of Chicago" vs "Springtown No.2 High School") still do not match.
