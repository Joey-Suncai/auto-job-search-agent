# Spec: the question text of a SuccessFactors form field (JSA-232)

SuccessFactors application forms are HTML tables: one row per field, with the field's label in a header cell and the
input in a data cell. Many company templates put the real question in its OWN text-only row (no input in it) directly
above the field's row, and give the field itself a generic placeholder label such as "Please select one of the
options" (dropdowns with options No / Yes). Example:

    row A (text only):  Are you at least 18 years of age?
    row B (field):      label "Please select one of the options*"   [dropdown: No Selection / No / Yes]

Function `question_label(label, rows)` returns the question text the answer rules should see.

Inputs:
- `label`: the field's own label text as read from the page (may carry a leading or trailing required star "*" and a
  trailing colon; whitespace may be irregular).
- `rows`: the texts of the text-only rows directly above the field's row, NEAREST FIRST. The walk upward stops at the
  previous row that holds a field, so every text in `rows` belongs to this field. May be empty or missing (null).

Rules:
1. Clean the label: collapse whitespace, drop a leading "*" and a trailing "*", drop a trailing colon.
2. If the cleaned label is empty, return "" (an unlabeled box is skipped elsewhere; rows are NOT used for it).
3. If the cleaned label is a real label (anything that is not a placeholder), return the cleaned label unchanged —
   rows are ignored.
4. Placeholder labels (case-insensitive, after cleaning, whole label): "select", "choose", "please select",
   "please choose", each optionally followed by " one", " one of the options", " one of the following", " an option" or
   " from the list"; also "no selection" and a run of dashes ("---"). Example placeholders: "Please select one of the
   options", "Please Select One of the Options", "Please Select", "Select one", "Choose an option", "No Selection".
   NOT placeholders: "Please select your gender", "Select your country of residence", "Please select the date you can start".
5. For a placeholder label: ignore rows with no letters (fewer than 2 consecutive letters). Each row text is cleaned like
   the label (rule 1). Return the NEAREST row whose cleaned text is at most 300 characters long.
6. If every lettered row is longer than 300 characters (e.g. a whole legal notice): take the nearest row; if it
   contains a question sentence (text ending in "?", sentences split at . ? !), return the LAST such question sentence,
   cleaned (whitespace collapsed, trimmed), provided it is at most 300 characters; otherwise return the first 300
   characters of that row with trailing spaces removed.
7. If there are no lettered rows, return the cleaned placeholder label itself.
