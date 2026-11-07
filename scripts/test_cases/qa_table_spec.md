# The user's question-and-answer table (form filling, 2026-11-04)

Form questions are answered by built-in rules. When no built-in rule can answer a question, the filler looks it up in
the user's question-and-answer table: entries the user gave earlier, each {question, answer}, optionally with a regex
that also matches other wordings. The answer is one of: a text, Yes / No, or an option to pick.

Built-in rules exist for the standard questions — first / last name, e-mail, phone, city, work authorization, visa
sponsorship (now / in the future), gender, race / ethnicity, veteran status, disability, how did you hear about us,
willingness to relocate. For those the table is never used, even when it holds the same question; the rule's answer stands.

Matching a table entry (only for questions no rule answers):
- The form's question equals the saved question after normalisation: case ignored, punctuation ignored, curly
  apostrophes = straight ones, "*" and the word "required" / "(required)" ignored, runs of spaces collapsed.
- A saved question at least 40 characters long (after normalisation) also matches a form question that starts with it
  and adds more text after it (help text).
- An entry with a regex also matches any form question the regex finds.
- Anything else (a shorter or different question, a question that only contains a short saved question in the middle)
  does not match.

The answer given:
- A list (options): the saved pick option (case-insensitive exact text); else the option equal to the saved text; else for
  a Yes/No answer the option that starts with "Yes" / "No". No such option → no answer (left to the user).
- A text box (no options): the saved text, or "Yes" / "No".
