# Which stored password to use on a Workday create-account form

The candidate keeps two passwords in the macOS Keychain: a regular one (used everywhere so far) and a long one (20
characters) for sites with a stricter length rule. A function receives the visible text of the create-account page, the
regular password and the long password, and returns the one to type.
- The page may state a length rule such as "A minimum of 12 characters", "at least 14 characters" or
  "8 characters minimum" (case-insensitive; the number has 1-2 digits). Use the first such rule on the page.
- No length rule on the page → the regular password.
- Regular password at least as long as the rule → the regular password.
- Regular password too short and the long one long enough → the long password.
- Both too short → the regular password (the site will refuse and a human takes over).
- If the long password is empty, always return the regular password.
Return the chosen password string.
