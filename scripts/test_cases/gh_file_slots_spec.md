# Greenhouse extra file slots and the after-submit outcome — spec (JSA-209, 2026-11-05)

A Greenhouse application form has two standard file slots (field names `resume` and `cover_letter`) and may have more file
slots that come from the posting's own questions (`question_<digits>`, type input_file). Problem seen: a REQUIRED extra
slot ("This role requires a brief research supplement … Please upload your resume and brief research supplement — as a
single PDF") was left empty, the runner pressed Submit, the form showed "This field is required", and the run was recorded
"unconfirmed" instead of failed.

## 1. slot_kind(name, label) → "resume" | "cover_letter" | "transcript" | "other_file"
- name "resume" → "resume"; name "cover_letter" → "cover_letter" — whatever the label says.
- Any other name (an extra slot) is classified from its label (case-insensitive):
  - document words: RESUME = resume, résumé, CV (as a word), curriculum vitae · COVER = cover letter, covering letter,
    letter of interest, motivation letter · TRANSCRIPT = transcript, academic record, grade report ·
    OTHER = supplement, writing sample, work sample, code sample, portfolio, project, research, paper, publication, essay,
    statement, certificate, recommendation, reference letter, case study.
  - combine words: merge, merged, combine, combined, single PDF / single file / single document, one PDF / one file /
    one document, together.
  - The label names exactly one of RESUME / COVER / TRANSCRIPT, no OTHER word and no combine word → that kind
    ("resume", "cover_letter", "transcript").
  - Everything else → "other_file" (no document word at all, an OTHER word, two kinds named, or combine wording).

## 2. file_slots(plan, folder) → list of extra slots, in plan order
Input: plan = {"fields": [{key, label, type, required, ...}]}; folder = a directory with files and maybe answers.json.
- Only plan fields with type "file" whose key is not "resume" and not "cover_letter".
- Each slot = {key, label, required (bool), kind = slot_kind(key, label), file = file name or null}.
- file:
  1. answers.json (a JSON object in the folder) has the slot's key and its value is the name of a file that exists
     directly in the folder → that name. A value that is not an existing file in the folder (missing, a sub-path, "..",
     an absolute path, or a plain text answer) is ignored. This rule wins over the ones below.
  2. kind "resume" → the first (sorted by name) file in the folder ending in .pdf (any case) whose name contains "resume"
     (any case); none → null.
  3. kind "cover_letter" → the first (sorted) .pdf whose name contains "cover_letter" (any case); none → null.
  4. kind "transcript" → "Transcript.pdf" when that file exists in the folder; else null.
  5. kind "other_file" → null (only Joey can supply it, via rule 1).

## 3. missing_file_slots(plan, folder) → the slots from file_slots that are required and have file null.
A required extra slot with no file stops the application BEFORE Submit and is handed to Joey (status needs-user, with the
slot's label); it is never submitted without the file. Optional slots without a file are never reported.

## 4. after_submit(confirmed, code_page, before, after) → {"status": ..., "fields": [...]}
After Submit is pressed. before / after = the form's visible validation errors read just before the click and after it:
lists of {"field": str, "msg": str}.
- confirmed (the confirmation page or a new thank-you text was seen) → status "submitted", fields [].
- otherwise, code_page true (the page asks for an e-mailed security code) → "unconfirmed", fields [] (a message on the
  code step is not a form validation error).
- otherwise, new errors = entries of after whose field does not appear as a field in before. Any new error → status
  "failed" (the form refused it, nothing was submitted), fields = the new errors' field names, each once, in order.
- otherwise → "unconfirmed", fields [].
