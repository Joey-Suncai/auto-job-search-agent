# Spec: was the application really handed in after the Submit click? (JSA-299)

An application runner clicks the final Submit button of a job application form, then looks at the page every two
seconds. For each look it must decide: CONFIRMED by the page (true) or NOT confirmed (false). Not confirmed is the safe
answer: the runner then waits for the company's receipt e-mail instead. A wrong "true" records a refused or unfinished
submit as handed in — the worst error.

The check gets two snapshots of the page — BEFORE (just before the click) and AFTER (now) — each with:
- `url`: the page address,
- `text`: the visible page text,
- `form`: true when the form's Submit button is visible, false when it is not, null when unknown.

Rules:
1. The page must have changed after the click. It changed when the URL is different (ignoring the part after `#` and a
   trailing slash), or when the Submit button was visible before (form true) and is not visible now (form false). A
   `form` of null never counts as "gone". No change → not confirmed, whatever the text says.
2. Error text on the AFTER page ("please fix", "please correct", "please complete", "is required", "required field",
   "there was an error", "there were errors", "error verifying", "something went wrong", "could not be submitted") →
   not confirmed, unless a success sentence is new since the click AND the Submit button is gone.
3. Success sentences: "thank you for applying", "thanks for applying", "thank you for your application", "thank you for
   submitting (your application)", "application submitted/received/sent/complete" (with optional "your", "was", "has
   been", "is", "successfully"), "we have received your application" / "we've received your application", "your
   application is in" / "is on its way", "you have (successfully) applied", "successfully submitted".
4. "Thank you for your interest" / "Thanks for your interest" is NOT a success sentence — job forms greet the candidate
   with it. A page whose only success-like text is that greeting is not confirmed, even if the page changed.
5. With a change (rule 1) and no error (rule 2), the page is confirmed when ANY of:
   a. the URL changed and the new URL is a success URL: it contains `/confirmation`, `/thanks`, `/thank`, `/thank-you`,
      `/apply/success`, `/success` or `application-submitted`;
   b. a success sentence is on the AFTER page that was not on the BEFORE page (compared case-insensitively, sentence by
      sentence);
   c. the URL changed, the Submit button is not visible (form false), and the AFTER page has a success sentence (even
      one the BEFORE page also had — it is a new page).
   Otherwise not confirmed. Note: a Submit button that only went away while the URL stayed the same (a spinner in its
   place) is confirmed only by rule 5b — a sentence the form already showed does not count.

Example that must be NOT confirmed (the real incident): BEFORE = the form, text includes "Again, thank you for your
interest in our internship opportunity", form true; AFTER = same URL, same text plus "Submitting…", form true or false.
Example that must be confirmed: BEFORE = the form (form true); AFTER = new URL `…/apply/success`, text "Thank you for
applying! We have received your application.", form false.
