# Combined "terms + SMS" checkbox (JSA-382)

The rules answer job-application form questions for one candidate. A checkbox label is the question; the answer is "Yes"
(checked), "No" (left unchecked) or "unknown" (the candidate is asked).

## Decision (Joey 2026-11-17)
Some forms have ONE checkbox that combines agreeing to the terms (terms of use / terms and conditions / privacy policy /
user agreement) with agreeing to receive SMS / text messages / WhatsApp (e.g. "I agree to the terms & to candidacy updates
by SMS/WhatsApp to my # if provided, unless I opt out."). Without agreeing to the terms the form cannot be submitted, so
such a combined box is ALWAYS answered "Yes" (checked), whatever the candidate's SMS preference is.

## Not covered by this rule
- A box that is ONLY an SMS / text-message opt-in ("Use SMS for communication", "I agree to receive text messages about my
  application") keeps its own rule: expect rule "sms" (its answer follows the candidate's SMS preference, which is Yes now).
- A box that is only the terms / privacy agreement without any SMS / text / WhatsApp wording: expect rule "terms" or "data_consent"
  (not the combined rule).
- A combined box of terms + MARKETING emails (no SMS) is out of scope; do not write cases for it.

## Cases to write
Real wording from forms: "I agree to the terms & to candidacy updates by SMS/WhatsApp to my # if provided, unless I opt out."
Write ~12 combined-box variants (different phrasings: "terms and conditions", "terms of use", "privacy policy", "text messages",
"SMS", "WhatsApp", the SMS part first or second) with expect "Yes" and expect_rule "terms_sms"; ~5 SMS-only variants with
expect_rule "sms"; ~4 terms-only variants with expect_rule_not "terms_sms".
