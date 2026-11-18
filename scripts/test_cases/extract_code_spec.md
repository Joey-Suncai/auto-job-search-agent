# Read the one-time code out of an e-mail text

An application site e-mails a one-time verification code. Given the mail's text (subject + body, plain text) and
optionally `n` (the expected code length = the number of code boxes on the page; when not given, 8), return the code as a
string, or null when there is none.
- The code follows a trigger word: "code", "passcode", "pass code", "one-time password" or "OTP" (case-insensitive,
  whole word). The trigger words may appear several times; earlier occurrences are tried first.
- A code is a whole token of 6 to 10 letters/digits (no other characters inside it).
- **Code block (tried first, anywhere in the mail):** a line that contains a trigger word and ends with a colon, followed
  (after optional blank lines) by a line that holds only one token (spaces around it allowed). That token is the code —
  this wins over any token earlier in the mail, including one in the subject (e.g. "Security code for your application
  to a Greenhouse employer" in the subject must not give "a Greenhouse employer" when the body has the code block).
- **Right after the trigger word:** the token separated from the trigger only by spaces, a colon, a dash, or the word
  "is" (e.g. "code: 204518", "code is 204518", "passcode - 1987AB"). That token is the code even when it looks like a
  year or a date.
- In those two code positions (code block, right after the trigger) a token with digits always counts. A token with NO
  digit counts only if ALL of: its length is exactly n (8 when n is not given); it has an upper-case letter somewhere
  after its first character; and it has a lower-case letter (e.g. "FTyAUMIB", "jbeRmAeA", "UBqOtnKi"). So an ALL-CAPS
  word ("REQUIRED", "IMPORTANT"), an all-lower-case word ("password") or a Capitalized word ("Required", "Alex") is
  never a code, even in a code position. A letters-only token of the wrong length is not a code.
- **Otherwise:** the first token that contains at least one digit within 200 characters after the trigger word — but a
  token that is a real calendar date written as 8 digits YYYYMMDD (year 1900–2099, month 01–12, day 01–31, e.g.
  20261110) is not a code and is skipped. Letters-only tokens are never taken in this fallback.
- A 6-digit code that starts with 19 or 20 (e.g. 201734, 198822) IS a code — it must be returned, in any position.
- Nothing qualifies → null.
