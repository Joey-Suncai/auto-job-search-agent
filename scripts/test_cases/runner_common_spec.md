# runner_common — the three segments every application runner shares (JSA-187)

A platform runner (one per job site) does the page work: open the form, sign in, fill fields, read them back, press the
final submit button. The common module does three things around it, the same way for every platform.

## 1. Opening checks (before the browser fills anything)
- An application folder that already has a `submitted` result is never run again: the run prints "already submitted" and
  stops; nothing is written to the results ledger.
- Materials check (only when the run has an application folder): the folder must have materials whose tailored resume
  is the file about to be uploaded. If this fails:
  - in a SUBMIT run: the run stops before filling; ONE results line with status `blocked`, `stopped_at` = `common_gate`;
    the folder is queued once for Joey; the form is never opened; nothing is pressed.
  - in a DRY run: the problem is kept and reported at the end, the form is still filled and read back; nothing is queued.

## 2. Submit gate (after the page work, before the final button)
The platform hands over its result: `status`, `problems` (its own page problems), `unknown` (questions no rule could
answer) and the field list (question, planned value, value on the page, ok = read back correctly).
The gate adds the common checks:
- canonical audit of the irreversible fields (work authorization, sponsorship, degree, EEO …): a mismatch is a problem;
- read-back: any field whose `ok` is not true is a problem; a result with no fields at all is a problem;
- in a submit run, the folder's batch must be approved (approved_batches); not approved is a problem.
Decision:
- any platform problem or unknown question → do not press; `stopped_at` = `platform_page`;
- otherwise any common problem → do not press; `stopped_at` = `common_gate`;
- a dry run never presses (decision `dry-run`); a clean dry run has `stopped_at` = null;
- a submit run with no problem at all → `press` (the platform presses the button).
- In a submit run that does not press, the folder is queued for Joey once. The status becomes `blocked` when the page work
  was ready (`dry-run`) and a check stopped it; a page-work status of its own (`captcha`, `needs-user`, `closed`, `blocked`)
  keeps its name, and a `closed` posting is not queued. Only a page-work status `dry-run` (= ready) can lead to a press.
- Some platforms press the button inside their own page loop; for them the same canonical audit + approval check runs
  right before that button, and a failure means the button is not pressed (status `blocked`, `stopped_at` = `common_gate`).

## 3. Closing books (always, exactly once per run)
- Exactly ONE results line per run with: status, mode (`submit` / `dry-run`), problems (platform + common, unknown
  questions included, at most 8), number of fields, number of fields not read back (`bad`), total seconds, per-phase
  seconds (`phases`, e.g. open / page / submit / close), `stopped_at`, the site's host name (`tenant`), and
  `confirmed_by` when there is one. The old keys keep their names.
- One fields-log line per field (question, planned, page value, source, type, required, ok, and `canon` = "mismatch" for
  a field the audit blocked).
- Status `submitted` → a confirmation screenshot exists in the folder, the tracker row is written (sync), every tab of
  that posting is closed.
- Status `unconfirmed` (button pressed, no confirmation page, no receipt e-mail) → queued for Joey and pushed to him.
- Any other non-final status in a submit run (blocked, needs-user, captcha …) → queued once (never twice for the same
  run). A `closed` posting is not queued. A dry run is never queued.
- A run that stopped prints its layer: 「停在：公共关卡」 for `common_gate`, 「停在：平台页面」 for `platform_page`.
- An error while closing (e.g. the tab cannot be closed) never loses the results line: it is written first.
