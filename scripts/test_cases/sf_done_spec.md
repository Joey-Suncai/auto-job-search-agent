# Did the application go in? (SuccessFactors, after pressing Apply — 2026-11-04)

A checker gets two page texts: BEFORE (the application form just before Apply was pressed) and AFTER (the page a few
seconds after). It says "submitted" only when AFTER contains a success phrase that was NOT already in BEFORE.

Success phrases (case-insensitive): "thank you for applying", "thank you for your application", "thank you for your
interest", "application has been submitted / received / sent", "application was submitted / received / sent",
"application successfully submitted", "you have applied", "you have successfully applied".

Rules:
- A success phrase that appears in BEFORE as well (for example a form whose intro says "Thank you for your interest in
  this position.") does not count when it is still in AFTER; only a phrase new in AFTER counts.
- Wording that is not one of these phrases (e.g. "Please correct the errors below", "Your profile was saved", "Thank you
  for visiting") never counts.
- If BEFORE is empty, any success phrase in AFTER counts.
