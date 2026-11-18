# Workable date box (JSA-234) — spec

Workable's date questions are react-datepicker text boxes. The box has a placeholder that shows its input mask
(Syntiant: "YYYY/MM/DD"). A value typed in another order is mangled by the mask and cleared when the box loses focus.
The answer rules give dates in US form "MM/DD/YYYY" (e.g. "06/14/2027").

parse_date(s) → (year, month, day) as integers, or None.
- Accepts YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD (1- or 2-digit month / day).
- Accepts US MM/DD/YYYY with "/" "-" or "." (1- or 2-digit month / day). A slash date with the year last is always
  read month first, never day first.
- Accepts "June 14, 2027", "Jun 14 2027", "Jun. 14, 2027" and "14 June 2027" (month names, any case, first 3 letters count).
- Surrounding / repeated whitespace is ignored.
- Anything else (empty, "ASAP", "Summer 2027", 2-digit years, impossible dates such as 02/30/2027 or 13/01/2027) → None.

to_mask(value, placeholder) → the value written in the box's own format, or None when value is not a date (parse_date None).
- The mask is the first part of the placeholder made of three tokens, one each of year (YYYY or YY), month (MM or M) and
  day (DD or D), any letter case, joined by the same separator (any non-alphanumeric run, e.g. "/", "-", ".", " / ").
  Text around the mask in the placeholder is ignored ("Date (YYYY-MM-DD)" → mask "YYYY-MM-DD").
- YYYY → 4-digit year, YY → last 2 digits, MM / DD → zero-padded 2 digits, M / D → no padding.
- The output keeps the mask's token order and separator exactly, and nothing else.
- No placeholder, an empty one, or one with no such mask (e.g. "Select a date", or two different separators, or a token
  repeated such as "MM/MM/YYYY") → Workable's own "YYYY/MM/DD".

same_date(want, got) → True only when both parse (parse_date) to the same (year, month, day); False if either is None.
