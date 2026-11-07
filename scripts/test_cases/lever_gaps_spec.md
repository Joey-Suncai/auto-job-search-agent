# Lever form gaps (JSA-144, 2026-11-04)

Three Lever forms showed questions the agent left empty: a Lever employer's required "LinkedIn Profile URL" box
(`name="urls[LinkedIn Profile]"`), ShopBack's "Github / Portfolio URL" (`urls[Github / Portfolio]`), and a Lever employer's optional
"Where do you currently live? (City, State)" and "What is the coolest thing you have ever built using AI?".

## lever_urls(page_html) → list of {key, label, required}
- Every `<input … name="urls[X]" …>` on the page becomes one field, in page order, key = `urls[X]` (X exactly as in the
  page, HTML entities decoded, e.g. `&amp;` → `&`). A name seen twice is listed once.
- label = X with spaces normalised; when X does not already contain the word "url", "link", "website" or "profile"
  (case-insensitive, whole word) " URL" is appended: "Github / Portfolio" → "Github / Portfolio URL", "LinkedIn Profile"
  stays "LinkedIn Profile", "Personal Website" stays "Personal Website".
- required = the tag carries the attribute `required`.
- Inputs whose name is not `urls[…]` are ignored.

## optional_essay(field) → bool
- field = {type, label, required?, survey?, consent?, demographic?}. True only for an optional (`required` false/missing)
  `textarea` whose label contains "?" or starts with "Describe", "Tell us", "Share", "Explain" or "Walk us through"
  (case-insensitive, leading spaces allowed) — and not a survey / consent / demographic field, and the label does not
  mention a referral ("referred", "referral", "who referred") or pronouns. Any other type (text, select, …) → False.

## city_state rule (answer for a question label)
- "Where do you currently live? (City, State)", "Where do you live?", "Where do you reside?", "Location (City, State)"
  → "Chicago, IL" (rule city_state).
- Not this rule: labels that also mention zip / postal code, country, relocation, willingness or commuting.
