# Checking the format of hand-given answers for date boxes and multi-selects (prep time)

Two pure functions check a value a person wrote into an application's answers file before any form is filled.

## date_answer(value) → [result, why]
A date box on the form accepts only MM/DD/YYYY. Returns [the value to type, null] or [null, a non-empty reason].
- Surrounding and repeated spaces are ignored.
- "MM/DD/YYYY" or "M/D/YYYY" (slashes, 4-digit year): result is zero-padded MM/DD/YYYY. When the first number is
  greater than 12 it is a day-first date → refused (null + reason), never swapped.
- "YYYY-MM-DD" (ISO, 1- or 2-digit month/day allowed): converted to MM/DD/YYYY.
- "<Month> <day>, <year>" or "<Month> <day> <year>" (comma optional, ordinal suffix st/nd/rd/th allowed on the day) and
  "<day> <Month> <year>" / "<day> <Month>, <year>": converted. Month = full English name, 3-letter abbreviation (optionally
  with a dot) or "Sept", any letter case.
- "<Month> <year>" (no day, e.g. "December 2027"): kept exactly as written (after space normalisation), not refused.
- A date that does not exist (02/30/2027, 13th month in ISO form, day 0, "Smarch 3, 2027") → refused.
- Anything else → refused: seasons ("Summer 2027"), "ASAP", "2027", "06/14/27" (2-digit year), "06-14-2027",
  "06.14.2027", empty string.

## multi_answer(value, options) → [result, why]
A multi-select (checkboxes) needs a set of exact option texts. Returns ["A | B", null] (parts joined with " | ", in the
order given, duplicates removed keeping the first) or [null, a non-empty reason].
- value may be a list of strings or one string. A string containing "|" is split on "|". Each part is trimmed and inner
  runs of spaces collapse to one space; options are compared after the same normalisation (case-sensitive).
- When the string has no "|" and is not itself an option, but contains commas and EVERY comma-separated part is an
  option, it is read as that list. (An option that itself contains a comma, given whole, stays one part.)
- Empty parts are dropped; nothing left → refused.
- When options is a non-empty list, every part must be one of them, else refused (the reason names the missing part).
- When options is empty or missing, any non-empty parts are accepted.
