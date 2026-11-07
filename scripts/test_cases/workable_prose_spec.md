# Workable runner: prose boxes and required fields (JSA-151)

A field is a dict {key, label, type, required}. type is one of text, textarea, radio, select, file.
An answer is a dict {status: "ok"|"unknown", value?, rule?}. Answers are keyed by field key.

## essay_like(field) -> bool
True when the field wants prose: type is "textarea", the key is NOT "cover_letter" and NOT "summary", and the label either
- starts (after leading spaces) with one of: Describe, Tell us, Share, Explain, Walk us through (case-insensitive), or
- contains the word "why", or
- contains "how did you" / "how do you" / "how would you" followed within 80 characters by one of the words check, decide,
  approach, solve, fix, handle, "find the", know, verify, or
- is longer than 100 characters.
Any other type (text, radio, select, file) is never essay-like.

## guard_short_answers(fields, answers) -> answers
For every essay-like field whose answer has status "ok" and a value shorter than 60 characters, the answer becomes
status "unknown" (a fact rule answered an essay by mistake, e.g. "Online job board" for "How did you find the root cause").
Other answers are unchanged. Long values (60+ characters) stay.

## apply_drafts(fields, answers, drafts, cover) -> (answers, missing)
drafts = {field key: drafted text}; cover = the cover letter text or null.
- The field with key "cover_letter" and type textarea: if cover is non-empty, its answer becomes {status ok, value: cover}
  (whether the field is required or optional). If cover is null/empty, the field is added to missing.
- Every essay-like field whose answer is not status "ok": if drafts has a non-empty text for its key, the answer becomes
  {status ok, value: that text}; otherwise the field is added to missing. This applies to required AND optional fields.
- Essay-like fields that already have an ok answer are left alone and are not missing.
- Non-essay fields are never touched and never missing.
missing is a list of {id: field key, label, limit}; return the list of ids in field order for the cases.

## required_empty(rows) -> list of labels
rows are fields after filling, each with "page" = the value read back from the page ("" or missing when empty).
Returns the labels, in order, of rows with required true whose page value is empty or only whitespace.
Optional rows are never returned, empty or not.
