# SuccessFactors register form helpers (2026-11-05)

An application runner creates candidate accounts on SAP SuccessFactors career sites. Three small helpers decide what to
do on the "Create an account" form.

## 1. Password length rule — `pw_limits(text)` → `[min, max]`
`text` is the whole visible page text. Return the minimum and maximum password length the page states; each is a number
or null when the page does not state it.
- A range: "between 8 and 18 characters", "8-18 characters", "8 – 18 characters", "8 to 18 characters" → [8, 18].
- A maximum alone: "must not be longer than 18 characters", "no longer than 18 characters", "no more than 18 characters",
  "at most 18 characters", "up to 18 characters", "a maximum of 18 characters", "maximum 18 characters", "cannot exceed 18
  characters", "must not exceed 18 characters", "18 characters maximum", "18 characters or less" → max 18.
  "fewer than 19 characters" / "less than 19 characters" → max 18 (strictly fewer).
- A minimum alone: "at least 8 characters", "a minimum of 8 characters", "minimum 8 characters", "no fewer than 8 characters",
  "8 characters minimum", "8 characters or more" → min 8.
- When the page states both a range and a separate maximum, the smaller maximum wins; a separate minimum and a range → the
  larger minimum wins.
- Case and extra spaces / line breaks do not matter. "chars" counts as "characters".
- A number not followed by "characters" / "chars" (e.g. "at least 1 uppercase letter", "18 years of age") is not a length rule.

## 2. Which stored password to use — `pick_password(text, items)` → `[name, password]` or null
`items` is an ordered list of `[name, password]` pairs (the regular stored password first, then a longer one). Return the
FIRST pair whose password length fits the rule from `pw_limits(text)` (length ≥ min when min is stated, ≤ max when max is
stated; both bounds inclusive). An empty password never fits. When nothing fits, return null. With no rule on the page,
the first non-empty password is used.

## 3. Data privacy link — `privacy_link(text)` → true / false
True when a link's text is the register form's data-privacy link that must be opened and accepted. Both wordings count:
"Read and accept the data privacy statement" and "Read and accept the data privacy agreement"; also "View the privacy
policy", "Review our privacy notice", "Open the data privacy agreement", "Accept the privacy statement", and a link that is
exactly "Data Privacy Statement" or "Data Privacy Agreement". Case and spacing do not matter. False for text that does not
name a privacy statement / agreement / policy / notice (e.g. "Terms of use", "Read the job description", "Create an
account", "Privacy" alone, "Cookie settings").

## 4. The question of a radio group with no label — `radio_question(texts, options)` → string
A radio group (e.g. "Make My Profile Visible to" with the options "Any Acme recruiter worldwide", "Any Acme recruiter in my
country/region", "Only recruiters managing jobs I apply to") sometimes has no label element. `texts` are the visible texts
of the group's enclosing elements, innermost first; `options` are the option texts. Go through `texts` in order; remove
every option text from it (longer options first), then drop a leading required star "*", a trailing colon and extra
whitespace. The first text that still contains a word of two or more letters and is at most 250 characters long is the
question; return it. Return "" when no text qualifies (all empty, only option texts, or every remaining text longer than
250 characters).
