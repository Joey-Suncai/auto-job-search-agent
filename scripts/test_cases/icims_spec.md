# iCIMS runner helpers (run_icims.py, JSA-093) — spec

Six pure functions. Whitespace in inputs is collapsed (runs of spaces / newlines count as one space) before matching.

## login_url(url) → [kind, url]
- `https://<tenant>.icims.com/jobs/<digits>/<anything>` (any path after the id, any query) → `["icims", "https://<tenant>.icims.com/jobs/<digits>/login"]`.
  The host is lower-cased; `http://` becomes `https://`; the query string is dropped. `/jobs/<digits>` with nothing after it also counts.
- `login.icims.com` is not a tenant: → `[null, null]`.
- A Jibe front end `https://<x>.jibeapply.com/jobs/<digits>…` → `["jibe", <the url unchanged>]`.
- Any other host whose path starts `/jobs/<digits>` AND whose query has `icims=1` as one of its parameters (e.g. `https://careers.medpace.com/jobs/13026?icims=1`) → `["jibe", <url unchanged>]`.
  `icims=10` or `xicims=1` do not count.
- Anything else (no `/jobs/<digits>` path start, `/jobs/search`, a Greenhouse / Workday URL, empty, not http(s)) → `[null, null]`.

## field_label(fid, label) → str
- When `fid` contains `PersonProfileFields.<Name>` or `PortalProfileFields.<Name>` (an optional prefix like `-1_` may come first) and `<Name>` (case-insensitive) is one of:
  PhoneType → "Phone Device Type", CountryCode → "Phone Country Code", PhoneNumber → "Phone Number", PhoneExtension → "Phone Extension",
  AddressType → "Address Type", AddressStreet1 → "Street Address", AddressStreet2 → "Address Line 2", AddressCity → "City",
  AddressZip → "Zip", AddressCountry → "Country", AddressState → "State", AddressCounty → "County", Login → "Email", Email → "Email",
  FirstName → "First Name", MiddleName → "Middle Name", LastName → "Last Name" — return that, whatever the label says.
- Otherwise return the label with whitespace collapsed, a trailing "required." / "required" word removed, and a leading or trailing `*` removed, then trimmed.
  Example: "Are you 18 or older?*  required." → "Are you 18 or older?".

## parse_steps(text) → {current, total, name, steps} | null
The step bar reads like `Step 1 of 4. Candidate Profile(Current Step) Step 2 of 4. Candidate Questions(Incomplete Step)`;
the state in brackets is one of Current / Incomplete / Complete / Completed followed by "Step" (case-insensitive); the
full stop after the number and the spaces are optional. `steps` = list of the step names in order 1..total ("" for a number
that does not appear); `current` = the number whose state is Current; `name` = its name; `total` = the largest "of N".
No step bar, or no step marked Current → null.

## is_final(button, steps) → bool
`steps` is a parse_steps result or null. True (pressing the button may hand in the application) when ANY of:
1. steps.current ≥ steps.total;
2. steps.current = steps.total − 1 and the last step's name contains (case-insensitive) assessment, review, confirm, submit, e-sign / esign, signature, complete or thank;
3. the button text matches (case-insensitive) "submit application", "submit my application", "submit your application", "finish", "complete application" (also with my / your), "apply now", "send application", or is exactly "Submit";
4. steps is null and the button text contains "submit".
Otherwise false — e.g. "Submit Profile", "Next", "Save & Continue" on step 1 of 4 whose last step is "Candidate Questions".

## pick_button(buttons) → button | null
`buttons` = list of {id, text}. Return the FIRST button whose text (non-empty) does NOT match any of: "log in with", "login with",
"sign in with", "signin with", "continue with", "connect", google, facebook, linkedin / linked in, apple, indeed, microsoft, dropbox, onedrive,
"replace resume", the word "back", "previous", "cancel", "withdraw", "save as draft", "save draft", "save for later", "add more", exactly "search",
or the word "later" ("Finish Later", "Save and Finish Later", "Complete Later" save the application and leave — JSA-143, 2026-11-04)
(all case-insensitive) — AND does match one of: the word "next", "continue", "submit", "save and continue", "save & continue", exactly "save",
"proceed", "finish", "apply". None qualifies → null.

## classify(url, text) → str
In this order:
1. url contains `login.icims.com`: text says "wrong email or password", "wrong username or password", "incorrect username/email/password" or the Chinese "用户名或密码错误" / "密码错误" → "bad_password"; else url contains `/password` → "universal_password"; else "universal_login".
2. text contains "unable to log in with the social account" → "social_error".
3. text says the application / submission has been (or was) (successfully) submitted / received / complete, or "thank you for applying / your application / submitting" — and the text has NO "Step N of M" → "done".
4. text has "Step N of M", or the url contains `/candidate`, `mode=apply` or `/question(s)` → "form".
5. url contains `/login` or text says "enter your email" / "enter your information" → "email".
6. otherwise "unknown".
