# Character limit for a drafted answer to an open form question

Inputs: the question label and the field type ("text" = a single-line text box, "textarea" = a multi-line box, or none).
Output: the maximum number of characters the drafted answer may have.
1. If the label states a character limit, use that number: e.g. "(255 char limit)", "max 500 characters",
   "500 characters max", "Limit of 300 characters", "in 1000 characters or less" → 1000, "(150-character limit)".
   This wins over the field type.
2. Otherwise a single-line text box ("text") holds at most 255 characters → 255.
3. Otherwise (textarea or unknown type) → 1200.
A number in the label that is not a character limit (a year "2027", "3x per week", "10-20 hours", a word limit like
"200 words") is not a character limit and is ignored.
