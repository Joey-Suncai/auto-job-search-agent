# receipt_match — choose_mail(mails, since, company, role="", siblings=()) — spec (JSA-390, 2026-11-17)

After a Submit with no confirmation page the runner looks in Joey's inbox for the company's "application received" e-mail.
It used to match by company name only, so a receipt for ANOTHER application at the same company (a second internship, an
auto-reply) could confirm this one. The match now needs evidence about THIS job.

Inputs: `mails` = list of {"when": ISO time with offset, "from": str, "subject": str, "body": str or null (the message text;
null when it was not fetched)}; `since` ISO time; `company` the company name of this application; `role` the job title of
this application ("" when unknown); `siblings` = job titles of OTHER applications at the same company that were submitted
around the same time (a title may be "" when unknown). Returns the subject of the receipt mail, or null.

## Which mails qualify (unchanged rules)
- Sent at or after `since`; newest first; the first that qualifies wins.
- The company is named in From or Subject (letters and digits only, lower case; the full name or its first word, ignoring The / Inc / LLC / Co / A / An; keys shorter than 3 characters unused).
- The subject is not a security code, verification code, newsletter, job alert, interview, "unfortunately", "not moving forward" or "regret" mail.

## What reads as a receipt (changed)
- The subject says "thank you / thanks for applying", "thank you / thanks for (your) application", "application received / was received / has been received / was submitted / has been submitted", "we've received your application" or "received your application": a receipt.
- A subject that only says "thank you / thanks for (your) interest" (nothing about applying or an application) is a receipt ONLY when the body (not null) also says the application was received / submitted ("received your application", "application has been received", "successfully submitted your application", "we have received your application"). With a null or silent body it is not.

## Which application it belongs to (new)
Role words = the words of a title (letters and digits, lower case) without the generic words intern, internship, summer, fall, spring, 2025, 2026, 2027, the, and, of, a, an, for, at, co, op, program. A title "names" a text (subject + " " + body, body null = empty) when it has at least one role word and EVERY role word appears in the text as a whole word.
For each qualifying mail, newest first:
1. the text names `role` → return its subject;
2. else the text names any sibling title (and not `role`) → skip it (it belongs to another application);
3. else (names neither): if `siblings` is empty → return its subject (the company has no other application, so company + receipt is unambiguous); if `siblings` is not empty → skip it (ambiguous).
No mail left → null.
