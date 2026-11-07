# Workday auto sign-in: why it failed after the create-account form (JSA-207, 2026-11-05)
The runner signs in to a Workday tenant with the candidate's Keychain passwords (a regular one and a long one); when the tenant has no account it submits the Create Account form, opens the tenant's verification link from Gmail when asked, and signs in again. When sign-in still fails it must say WHY, so the queue tells the candidate exactly what to do. The agent never changes or resets a password.

## Function 1: message_kind(text) -> "locked" | "exists" | "wrong_password" | "verify" | "none"
text = the error / alert messages the tenant shows on the sign-in or create-account page (may be empty). Case-insensitive. First matching rule wins:
1. "locked": the account is locked, disabled or suspended, or there were too many (failed) sign-in attempts ("Your account has been locked", "Account locked", "too many failed attempts", "temporarily disabled").
2. "exists": an account with this e-mail already exists ("already exists", "already in use", "already registered", "is already associated with an account", "An account with this email address already exists").
3. "wrong_password": the e-mail / username / password / credentials are wrong, invalid, incorrect or not recognised; "could not sign you in"; "no account" / "account doesn't exist" ("Wrong email or password.", "Invalid username or password", "The email address or password you entered is incorrect", "Sign in failed: check your email and password" counts as wrong_password, not verify).
4. "verify": the tenant asks to verify / activate the account or e-mail, or to check the inbox for a verification e-mail ("Please verify your account before you sign in", "We sent you a verification email", "Activate your account").
5. "none": empty text or anything else ("Sign In", "Loading", "Required", "Something went wrong").

## Function 2: failure_code(t) -> code
t = {"created": bool (the runner submitted the Create Account form in this run), "exists_msg": bool (the tenant said the account already exists), "verify_banner": bool (the tenant asked to verify the e-mail in this run), "verified": bool (a verification link was opened in this run), "error": "locked" | "wrong_password" | "none" | "other" (the tenant's answer to the LAST sign-in attempt; none = no recognisable message at all), "mails": [{"date": "YYYY-MM-DD", "kind": "verify" | "other"}] (mails from this tenant's Workday in the candidate's Gmail, any age: "verify" = a verify-your-account mail, "other" = anything else such as "Thank you for applying"), "agent_since": "YYYY-MM-DD" (the day the agent began creating accounts; mails dated before it come from the candidate's own earlier activity)}.
Rules, in order; the first that holds wins:
1. "locked" — error is "locked".
2. "old_account" — the candidate's own earlier account, which the Keychain passwords do not open: exists_msg is true, OR there is an "other" mail dated before agent_since and no "verify" mail dated on or after agent_since.
3. "agent_account_password" — a "verify" mail dated on or after agent_since exists (the agent created this account) and error is "wrong_password".
4. "no_verify_mail" — created is true, there is no "verify" mail dated on or after agent_since, and error is "wrong_password" or "none" or verify_banner is true: a new account whose verification e-mail never came.
5. "no_answer" — error is "none" (the tenant gave no recognisable answer).
6. "other" — anything else.
A date equal to agent_since counts as on/after it.
