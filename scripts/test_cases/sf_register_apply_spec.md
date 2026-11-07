# SuccessFactors register-form radios and the one-page register-and-apply form (2026-11-05, second batch)

An application runner fills SAP SuccessFactors candidate sites. Six small pure helpers.

## 1. Option text of a radio input — `option_text(c)` → string
Some register forms have radio inputs with no id and no `<label for>`; the option text sits elsewhere around the input.
`c` = {"label": text of the input's own label element, "labelledby": text of the elements named by aria-labelledby,
"aria": the aria-label attribute, "after": the text right after the input (or right after its wrapper), "wrap": the text
of the nearest wrapper element that holds only this radio, "value": the input's value attribute}. Any key may be missing
or empty.
- Take the FIRST of label, labelledby, aria, after, wrap (in that order) that is non-empty after whitespace is collapsed
  (runs of spaces / tabs / line breaks become one space, ends trimmed) and a leading required star "*" (with the spaces
  after it) is dropped.
- A candidate longer than 300 characters is not an option text: skip it and try the next one.
- When none qualifies, return the value (whitespace collapsed); "" when there is no value either.

## 2. How to find one radio input on the page — `radio_selector(opt)` → [css selector, nth] or null
`opt` = {"id", "name", "value", "idx" (its position in its group, 0-based), "dup" (true when another radio of the group
has the same value)}.
- It has a non-empty id → [`[id="<id>"]`, 0] (double quotes inside the id escaped with a backslash).
- Else, with no name → null.
- Else, when the value is a non-empty string and dup is not true → [`input[type=radio][name="<name>"][value="<value>"]`, 0].
- Else → [`input[type=radio][name="<name>"]`, idx] (idx missing = 0).
- Inside the attribute values a backslash becomes two backslashes and a double quote becomes backslash + quote.

## 3. Which page the site shows — `page_kind(sig)` → string
`sig` = {"app": the page text has "Expand all sections" or "My Documents", "account": a visible account e-mail box,
"apply_btn": a visible Apply submit button, "attach": a visible resume / CV attach icon, "upload": the text has "Upload a
Resume" / "Upload a CV" / "Upload your resume", "signin": a visible sign-in e-mail box}; missing keys are false.
- app → "application" (whatever else is true).
- else account AND (apply_btn OR attach OR upload) → "register_apply" (one page with the account fields and the
  application).
- else account → "register" (the account form alone).
- else signin → "sign_in".
- else "unknown".

## 4. The link to open and accept — `accept_link(text)` → true / false
True when a link's text is either
(a) a data-privacy link: a verb (read and accept / accept / open / view / review / read) followed within 30 characters by
    "privacy statement", "privacy agreement", "privacy policy" or "privacy notice" (optionally "data " before "privacy"),
    or a text that is exactly "Data Privacy Statement" / "Data Privacy Agreement"; or
(b) a terms link: "read and accept", "read & accept" or "accept" followed within 30 characters by "terms of use", "terms
    and conditions" or "terms of service" ("Read and accept terms of use").
Case and spacing do not matter. False otherwise — in particular "Terms of use" alone, "By creating an account you agree to
the Terms of use" (agree is not accept), "Danfoss Job Portal Terms", "Privacy policy" alone, "Cookie settings".

## 5. Was it accepted — `privacy_accepted(text, dpcs_value)` → true / false
True when
- the page text (whitespace collapsed, case ignored) contains "data privacy", "privacy statement", "privacy agreement",
  "terms of use" or "terms and conditions" followed — within 40 characters and without a sentence end (. ! ?) in
  between — by the word "accepted", AND that stretch does not say it must or still has to be accepted: "not accepted",
  "not been accepted", "must be accepted", "should be accepted", "needs to be accepted", "has to be accepted", "to be
  accepted", "be accepted" all do NOT count;
  e.g. "Data privacy statement has been accepted." and "Terms of use accepted" count;
- OR `dpcs_value` (the form's hidden privacy box) is a non-empty string after trimming.
Otherwise false ("Accepted file types: PDF" is not an acceptance; neither is "Please open the data privacy agreement and
accept it").

## 6. Did an account box keep its value — `account_ok(key, want, got)` → true / false
`key` is the box id. Whitespace in want / got is collapsed first.
- `fbclc_emailEnabled`, `fbclc_campaignEmailEnabled` (checkboxes that must stay off): true exactly when got equals want
  (want "" = off, got "" = off, "checked" = on).
- Any other key with an empty want → false.
- `fbclc_phoneNumber`: true when the last 10 digits of got equal the last 10 digits of want (other characters ignored).
- `fbclc_userName`, `fbclc_emailConf` (e-mail): equal ignoring case.
- Anything else: exactly equal.
