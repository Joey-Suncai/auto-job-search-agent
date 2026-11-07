# Workable submit confirmation (JSA-146, 2026-11-04)

After clicking "Submit application" the runner decides whether the application went in.

## confirmed_page(url, text) → bool
- True when the page text contains a thank-you / received sentence (case-insensitive): "thank you for applying",
  "thanks for applying", "thank you for your application", "thank you for your interest", "application submitted",
  "application was submitted", "application has been submitted", "application successfully submitted",
  "application received" / "has been received", "application sent", "we've received your application",
  "we have received your application", "your application is in", "your application is on its way";
  or when the URL contains "/apply/success", "/apply/thank" or "/confirmation".
- False for an unchanged form or an error page: text with "please fix", "please correct", "please complete",
  "is required" or "there was an error / there were errors" is False — unless a thank-you sentence above is also present.
- Anything else (empty text, the job description, "Submit application" button text) → False.

## posting_key(url) for Workable
- `apply.workable.com/<account>/j/<SHORTCODE>` (SHORTCODE = 6–12 hex characters, either case) → "<account>/j/<SHORTCODE>"
  exactly as written, whatever follows (/apply/, /apply/success, ?s=…).
