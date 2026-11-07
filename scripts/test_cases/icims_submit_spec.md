# iCIMS submit path — pure decisions (JSA-093, 2026-11-05)

The iCIMS runner walks an application step by step ("Step 1 of 4. Candidate Profile", "Step 2 of 4. Candidate
Questions", …). A button that may hand in the application is the "final" button. In a dry run the runner stops before it.
With `--submit` it may press it, but only when the gate below says so, and afterwards it decides from the page whether
the application went in. Four pure functions.

## 1. submit_gate(submit, no_advance, steps, consent) → [decision, reason]
Decides whether the runner may press the final button now. Returns a two-item list.
- `submit` (bool): `--submit` was given AND the application folder is in the approved batches AND it is not already
  submitted. `no_advance` (bool): the "fill this step only, press nothing" option.
- `steps`: list of the steps filled so far, in order, the current (last) step last. Each step is
  `{"fields": [{"label": str, "required": bool, "ok": bool}, …], "problems": [str], "unknown": [str], "errors": [str]}`.
  A field with `ok` missing counts as not ok. `errors` = error texts visible on that step's page.
- `consent` (str): "ok" or "ask" (see §3).
Checks, in this order — the first that applies decides:
1. `no_advance` true → `["dry-run", "no-advance"]`.
2. `submit` false → `["dry-run", "not-approved"]`.
3. any step has a non-empty `unknown` list → `["needs-user", "unknown"]`.
4. any step has a non-empty `problems` list, or any field in any step whose `ok` is not true → `["needs-user", "readback"]`.
5. no fields at all across every step → `["needs-user", "empty"]`.
6. the LAST step's `errors` contain a real error → `["needs-user", "page-error"]`. The inactivity notice
   "You will be logged out in N seconds due to inactivity" (any N, any case) is not a real error, and neither is an
   empty / whitespace-only string. Errors of earlier steps are ignored (those steps already moved on).
7. `consent` is not exactly "ok" → `["needs-user", "consent"]`.
8. otherwise → `["press", "ok"]`.

## 2. after_submit(url, text, before) → "done" | "next" | "refused" | "pending"
Classifies the page after the final button was pressed. `text` = the tab's visible text (main page and the iCIMS iframe
joined), `before` = the step number the button was pressed on (int), or null when that page had no step bar.
A step bar is text like "Step 3 of 4. Assessments (Current Step)" — "Step <n> of <m>. <name> (Current Step)"; other steps
in the bar are marked "(Incomplete Step)" / "(Complete Step)" / "(Completed Step)". The current step is the one marked
"(Current Step)"; a bar without a "(Current Step)" item counts as no step bar.
- **"done"** when the text contains a thank-you / submitted sentence (case-insensitive) — "thank you for applying",
  "thank you for your application", "thank you for submitting", "application has been submitted", "application was
  submitted", "application submitted", "application successfully submitted", "application has been successfully
  submitted", "application has been received", "application received", "application is complete", "submission has been
  received", "submission complete", "you have successfully applied" — AND either there is no step bar, or the current
  step is the last one (n = m), or the current step's name contains "thank", "confirm", "complete", "submitted" or
  "success". A thank-you sentence on an earlier, ordinary step (e.g. "Step 2 of 4. Candidate Questions (Current Step)")
  is not "done".
- otherwise **"next"** when there is a step bar and `before` is null, or its current step number is greater than `before`.
- otherwise **"refused"** when there is a step bar whose current step number is equal to or smaller than `before`
  (the page did not move forward); or when there is no step bar, `before` is a number, and the text contains an error
  word: "required", "please correct", "please check", "invalid", "error".
- otherwise **"pending"** (blank page, redirect, unrelated text, a login page) — the runner keeps waiting and then looks
  for the company's receipt e-mail.
"thank you for your interest" alone is not a thank-you sentence. `url` does not change the result by itself.

## 3. consent_gate(text, approved) → "ok" | "ask"
The e-mail step of some iCIMS tenants has a required consent box; its page text is saved. Before a real submit that
text must be one the candidate accepted.
- empty / whitespace-only / null text (no consent box) → "ok".
- "ask" when the text contains wording beyond the application (case-insensitive): "arbitration", "class action",
  "jury", "waive" (also "waiver"), "automated dialer" / "automated dialing" / "automated telephone dialing", "prerecorded", "artificial voice", "marketing",
  "promotional", "newsletter", "recruiting related messages", "talent community", "be bound by", or a consent / agreement
  to calls, text messages, texts or SMS ("I agree to receive text messages", "consent to SMS").
- … unless the text also contains one of the `approved` snippets (list of strings or of objects `{"contains": str}`),
  compared case- and whitespace-insensitively; an empty snippet never matches → then "ok".
- anything else → "ok": a privacy notice / data-processing consent for this application, and the interview terms the
  candidate accepted on 2026-11-03: no AI tools during interviews, photos or recordings in interviews, a background check.

## 4. posting_key(url) for iCIMS (shared tab-closing key)
- `https://<tenant>.icims.com/jobs/<id>/<anything>` (any path after the id: `/login`, `/job`, `/<slug>/candidate`,
  any query or fragment) → `"<tenant>.icims.com/jobs/<id>"` with the host lower-cased; `<tenant>` may contain letters,
  digits, dots and dashes (e.g. `careers-acme`, `uscareers-acme`).
- `login.icims.com/…` is not a posting: it falls through to the default rule (the URL without its query and fragment).
- Every other URL keeps its existing key; for an unknown site the default is the URL without its query and fragment.
