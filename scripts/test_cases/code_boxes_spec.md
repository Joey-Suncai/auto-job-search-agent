# Where to type an e-mail security code on an application form

After Submit, some forms (Greenhouse) ask for a code e-mailed to the candidate. Given the visible inputs on the page
(each: id, name, aria-label, autocomplete, maxlength) and the code length n, return the ids of the inputs to type into,
in order:
1. If the page has boxes with ids `security-input-0`, `security-input-1`, … (one character each), return all of them
   ordered by their number (0, 1, 2 …), whatever order they appear in.
2. Otherwise return the FIRST single input that is clearly the code box: autocomplete "one-time-code", or id/name/label
   mentioning "security code", "verification code", "one-time code", "confirmation code", "access code", "OTP", or a
   field whose id/name/label is exactly "code". Only one id is returned.
3. Never an input about something else that merely contains the word "code": ZIP code, postal code, post code, promo
   code, referral code, coupon / discount code, country code, area code, phone, invite code — even when it is the only
   input with "code" in its label. If nothing qualifies, return an empty list.
