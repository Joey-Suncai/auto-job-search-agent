# Async receipt confirmation for Lever and SuccessFactors (JSA-391)

After a Submit whose page shows no confirmation, the runner no longer waits for the company's receipt e-mail in place
(Lever 180 s, SuccessFactors 300 s). The e-mail is found later by receipt_confirm (it records `submitted`; 48 hours
without a receipt puts the application on Joey's list).

`receipt_plan(mail_wait, captcha_seen)` decides what the runner does when the page gave no confirmation:
- "joey": a CAPTCHA challenge was met on this run (captcha_seen true) — the submit probably did not go through and Joey
  must finish it (Edge hand-off, queue line, push). This wins over everything, also when mail_wait is positive.
- "wait": mail_wait is a positive number of seconds (the old in-place wait, only when asked for with --mail-wait N).
- "pending": otherwise (mail_wait 0, None or negative; no CAPTCHA) — record `unconfirmed` with receipt pending: no queue
  line, no push, no waiting; receipt_confirm confirms it later.

`unconfirmed_action(result)` decides what runner_common does for a result whose status is `unconfirmed`: "pending" when
`result["receipt_pending"]` is exactly true (log only: no queue line, no push); "joey" otherwise (queue line + push as
before) — also when the key is missing, false, null, 0, or the string "true".
