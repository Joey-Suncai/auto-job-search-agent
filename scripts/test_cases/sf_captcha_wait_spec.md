# How long the SuccessFactors runner waits for the candidate's reCAPTCHA tick — spec (2026-11-05, Erie)

Function `captcha_wait(submit, given)` returns the number of minutes (a float) the runner waits for the candidate to tick
a reCAPTCHA (on the sign-in page, the register page, or above Apply).
- `submit` is True for a real submit run, False for a dry run.
- `given` is the number typed after `--wait-captcha` on the command line, or None when the option was not given.
Rules: when `given` is a number, that number is used (in a dry run too — the candidate may be at the screen). When `given`
is None: 15 for a submit run, 0 for a dry run (an unattended dry run never waits). A negative number becomes 0. Integers
and floats are both accepted; the result is a float (15 → 15.0).
