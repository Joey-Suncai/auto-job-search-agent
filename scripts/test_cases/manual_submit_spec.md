# Lever hand-off sheet + manual record (JSA-042)

Lever forms are filled and checked by a runner, but Lever's CAPTCHA usually rejects the runner's browser, so the person
submits by hand. Two pieces:

## A. When the sheet is written (should_write)
Inputs: the form's ATS name, the run status, a list of problem strings, and the per-field check results (each has `ok`).
- A sheet is written only when the ATS is exactly "lever".
- Never when the status is "submitted" (already confirmed). Any other status ("dry-run", "unconfirmed", "captcha", "blocked") may get a sheet.
- Only when the problem list is empty AND there is at least one field result AND every field result has ok = true.

## B. Sheet content (sheet)
Inputs: the plan (its URL and its fields, each with a key and the FULL label), the per-field results in form order (each:
key, label — possibly cut short —, type, want = the answer the runner filled, ok), and the application folder's absolute path.
- One table row per answered field, numbered 1, 2, 3 … in the order of the results. The Field column shows the label from
  the plan's field with the same key; if the plan has no such key, the result's own label.
- Normal answer: the Answer column is the answer text, with line breaks turned into spaces and "|" escaped as "\|".
- File field (type "file") with a file name in want: the Answer column says upload plus the absolute path = folder path + "/" + file name;
  that path is also listed under a "## Files" section.
- File field with no file name, or a non-file field whose want is missing or empty/whitespace: no table row and no number;
  its label is listed under "## Leave blank".
- Long answer: an answer longer than 160 characters, or containing a line break, gets a table row that says
  "see answer N below" (N = its row number) and the full text, unchanged, in its own "## Answer N — <label>" section inside a code block.
- An answer of exactly 160 characters with no line break is a normal answer.
- The sheet always contains the form URL and, at the end, the command to record the hand submit:
  `sync_results.py --manual "<folder name>"` where folder name is the last part of the folder path.
- The sheet always tells the reader that Lever's "error verifying" message is not a failure: check Gmail for a confirmation before retrying.

## C. Recording the hand submit (manual_line)
Inputs: the folder name, the existing results log (list of lines, each with folder and status), url, ats, a timestamp, an optional note.
- If any existing line has this folder AND status "submitted", nothing new is recorded (result: none) — re-running is safe.
  Lines for the folder with other statuses ("dry-run", "unconfirmed", …) do not count; lines for other folders do not count.
- Otherwise the new line has: folder, url, ats, at = the timestamp, status "submitted", by "joey", and note = the given
  note, or "submitted by Joey by hand from manual_submit.md" when no note (or an empty note) is given.
