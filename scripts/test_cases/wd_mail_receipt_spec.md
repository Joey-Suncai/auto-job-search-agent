# wd_mail_receipt(meta, since, wait, waiter, log) — spec (JSA-306, 2026-11-17)

A Workday application was submitted (Submit clicked) but the page shows no confirmation (the Submit button is still there
and the URL did not change). The runner then waits for the company's application-received e-mail (Gmail, read-only) before
it calls the application unconfirmed. `meta` is the application's job record (a dict with the key "company" for
Workday jobs), `since` a time marker, `wait` the maximum seconds to wait (180 by default), `waiter(since, company, timeout=wait)`
the function that reads Gmail and returns the subject of the received e-mail, or None. `log(text)` records a line.

Returns the e-mail subject (a non-empty string) when the e-mail arrived, else None.
- `wait` is 0 / None → None; the waiter is not called.
- `meta` has no company, or the company is blank after trimming → None; the waiter is not called; one log line says why.
- Otherwise the waiter is called exactly once as `waiter(since_minus_30s, company_trimmed, timeout=wait)`: `since_minus_30s`
  is `since` minus 30 seconds (the receipt can be sent a moment before the click returns).
- The waiter returns a non-empty string → that string is returned.
- The waiter returns None or "" → None.
- The waiter raises any exception (Gmail down, no password, timeout) → None; one log line starts with "e-mail check failed".
- The function never raises.
