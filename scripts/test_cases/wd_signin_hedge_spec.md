# Workday auto sign-in: a hedged "might be locked" is not a lock (JSA-334, 2026-11-12)
The runner signs in to a Workday tenant with the candidate's Keychain passwords: a regular one and a long one. Many tenants show ONE generic alert for every failed sign-in: "You may have entered the wrong email address or password or your account might be locked." That sentence does not say the account IS locked; it is the normal answer when the password is wrong or there is no account on this tenant. Only a definite statement counts as a lock. The agent never changes or resets a password; locked accounts and the candidate's own old accounts are handed to the candidate.

## Function 1: message_kind(text) -> "locked" | "exists" | "wrong_password" | "verify" | "none"
text = the error / alert messages the tenant shows (may be empty). Case-insensitive. First matching rule wins:
1. "locked": the text says definitely that the account IS locked, disabled or suspended, or that there WERE too many (failed) sign-in attempts ("Your account has been locked", "Account locked", "Your account is temporarily disabled", "Too many failed attempts. Try again in 30 minutes", "You have been locked out"). A hedged or conditional mention is NOT a lock: "might be locked", "may be locked", "could be locked", "may have been locked", "may be temporarily locked", "if your account is locked, contact support", "after 5 failed attempts your account will be locked" (a warning about the future).
2. "exists": an account with this e-mail already exists ("already exists", "already in use", "already registered", "An account with this email address already exists").
3. "wrong_password": the e-mail / username / password / credentials are wrong, invalid, incorrect or not recognised; "could not sign you in"; "sign in failed"; "no account" / "account doesn't exist"; AND any hedged or conditional lock mention from rule 1 (alone or with other words), e.g. "You may have entered the wrong email address or password or your account might be locked." and "Your account might be locked." are both wrong_password.
4. "verify": the tenant asks to verify / activate the account or e-mail ("Please verify your account before you sign in", "We sent you a verification email", "Activate your account").
5. "none": empty text or anything else ("Sign In", "Loading", "Required", "Something went wrong").
When a text contains both a definite lock and a hedged one, it is "locked".

## Function 2: after_wrong(s) -> "retry_long" | "old_account" | "create" | "give_up"
What the runner does after a sign-in attempt that the tenant answered with "wrong_password" (a definite "locked" never reaches this: it is handed to the candidate at once).
s = {"has_long": bool (a long Keychain password exists), "tried_long": bool (the long password was already tried in this run), "created": bool (the runner already submitted the Create Account form in this run), "mails": [{"date": "YYYY-MM-DD", "kind": "verify" | "other"}] (this tenant's Workday mails in the candidate's Gmail, read-only; "verify" = a verify-your-account mail, "other" = anything else such as "Thank you for applying"), "agent_since": "YYYY-MM-DD" (the day the agent began creating accounts; a mail dated before it is the candidate's own earlier activity; a date equal to agent_since counts as on/after it)}.
Rules, in order; the first that holds wins:
1. "retry_long" — has_long is true and tried_long is false: sign in again with the long password first.
2. "give_up" — created is true (the account form was already tried once in this run; never a second time).
3. "old_account" — there is an "other" mail dated before agent_since and no "verify" mail dated on or after agent_since: the candidate's own old account, which the Keychain passwords do not open → hand to the candidate, do NOT create an account.
4. "create" — otherwise: there is probably no account on this tenant → open Create Account.
