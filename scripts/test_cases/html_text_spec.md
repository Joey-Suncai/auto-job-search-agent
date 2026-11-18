# html_text(h) and extract_code(text) together — spec (gmail_code.py, 2026-11-03)

html_text(h): `h` is the HTML body of an e-mail (string, may be empty or None → treat as ""). Remove every <style>…</style>
and <script>…</script> block including its contents (tag names case-insensitive, attributes allowed, blocks may span
lines). Then replace every remaining tag (anything from "<" to the next ">") with a single space. Text between tags is
kept as is (HTML entities are NOT decoded).

extract_code(text): find the first trigger — the whole word "code", "passcode", "pass code", "one-time password" /
"one time password" or "OTP" (case-insensitive; added 2026-11-05: an employer writes "one-time passcode: 710027") —;
in the 200 characters right after it, take the
first token of 6–10 letters/digits that is not part of a longer letter/digit run, contains at least one digit, and is
not an 8-digit YYYYMMDD calendar date — except that the token right after the trigger word ("code: …", "code is …") is the code whatever it looks like (JSA-297, spec of extract_code: scripts/test_cases/extract_code_spec.md). Try the next trigger when none is found; return None
when no code is found anywhere.

The test runs extract_code(html_text(h)) on a whole HTML mail and compares with the expected code (or null).
