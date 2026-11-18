# "If other, please specify" follow-up questions in the prefetch question sheet (JSA-256)

A job application form is a list of fields in page order. Some fields are follow-ups of the field right before them and
only matter for one answer of it: "If other, please specify.", "If you selected Other, please explain", "Other (please
specify)", "If yes, select your most recent …" (a yes/no follow-up). The prefetch sheet asks the candidate the
questions the rules cannot answer; a follow-up asked alone has no context and the candidate cannot answer it.

For each unanswered field the sheet builder decides, using the preceding field (the previous field in page order):
- The field is an OTHER follow-up when its label starts with or contains "if other", "if you selected other",
  "if you chose other", "other, please specify", "other (please specify)", "other - please specify", "other: please specify",
  or is exactly "Other" / "Other:" / "Please specify" AND the preceding field is a choice field that has an option starting
  with "Other" (case-insensitive: "Other", "Other (please specify)", "Others"). A field with those words whose preceding field
  has no "Other" option is an ordinary question (not a follow-up).
- Follow-up and the preceding field was already answered with a value that is NOT an "Other" option (the form's own answer
  or a rule's answer): the follow-up is never shown on the form → DROP it from the sheet.
- Follow-up and the preceding field is still unanswered (it is itself on the sheet): DROP the follow-up now; it is asked in a
  later round once the answer to the preceding field is known and is Other.
- Follow-up and the preceding field was answered with an "Other" option: KEEP the question but with its context — the
  label becomes "<preceding label> — you chose <that option>: <follow-up label>".
- A field that is not an Other follow-up is never touched (kept as is).
"Preceding field" = the field immediately before it in the list, whatever its type; if the immediately preceding field is not
a choice field with an Other option, the field is not an Other follow-up.
