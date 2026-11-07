---
name: ats-icims
description: Apply to an iCIMS job (`<tenant>.icims.com/jobs/<id>/…`, Jibe front ends `*.jibeapply.com/jobs/<id>`, company career sites with `?icims=1`) with run_icims.py — e-mail step, hCaptcha hand-off, tenant profile / universal login, step-by-step fill and read-back, dry-run by default, `--folder … --submit` inside an approved batch — plus every iCIMS problem type seen so far.
---

# iCIMS applications (platform skill)

Part of the job-search agent. Read with `skills/auto-apply/SKILL.md` (general rules) and the candidate's facts in `config/`.
Code: `skills/auto-apply/runner/run_icims.py`. **After every iCIMS batch, update §4**: add each new problem to its type
with the rule and the test that enforces it — the kind of problem, not the company; companies and dates go in the type's
`Seen:` line (private: the public export drops it).

## 1. Status (2026-11-05, JSA-093)
- **Dry-run by default; submit path since 2026-11-05 (offline-tested, no live submit yet).** Without `--submit`
  `run_icims.py` enters the e-mail, parks the hCaptcha for the candidate, signs in / creates the tenant profile, fills
  every step with `answer_rules.js`, reads every field back, and stops **before** the button that hands in the
  application (the last step, or the step before a last "Assessments / Review / Confirm / e-Signature" step, or a bare
  "Submit" — `is_final`). With `--folder applications/<folder> --submit` it presses that button only when
  `submit_gate` says `press` (§3 b). JSA-093 stays open until 10 live submits.
- **Every iCIMS application needs the candidate at least once: hCaptcha at the e-mail step** (seen on all 4 tenants tried,
  classic and new login), and again at "Submit Profile" on a classic tenant. The runner pushes the hand-off
  (`human_check.py`) and waits `--wait-captcha` minutes. So iCIMS cannot reach the 95 % "no Joey" bar as it stands — it is
  a Lever-style platform (runner fills, the candidate clears the CAPTCHA).
- Supply (2026-11-03, `scripts/platform_counts.py`): 可投 icims 27 + jibe 20; A/B = 8 ICE internships (jibe), the rest C/D.
- Dry-runs 2026-11-03 (4 tenants, tier C): 2 classic tenants reached the form — one to step 2 of 4 (Candidate
  Questions; profile 20 / 20 read back, profile created, stopped on an authorization question the rules do not answer),
  one to step 1 (17 / 17 read back; "Submit Profile" kept failing the address check, type I); 2 new-login tenants stopped
  at `login.icims.com` (type G). 6 hCaptcha hand-offs in total, all solved by the candidate within minutes.

**Common segments (JSA-186 / JSA-187, 2026-11-05) — `runner/runner_common.py` (+ `presubmit.py`):** the runner does the page work only. Opening checks: already submitted · materials gate (requirements.json seeded with resume + optional letter when missing) · the upload must be the folder's **tailored** resume from `materials_manifest.json`, never a library default — a problem in a `--submit` run stops it before filling (`blocked`, queued, `stopped_at: common_gate`). Submit gate: canon on what the page holds for the irreversible fields, every field read back, zero unknowns, batch approved; only a page-work status `dry-run` can lead to a press (captcha / needs-user / closed keep their name). Closing books: one results line (old keys + `phases` seconds, `stopped_at` = common_gate / platform_page, `tenant`), one `data/runner/fields/<YYYY-MM>.jsonl` line per field, sync_results, tabs closed, unconfirmed → queue + push; the log ends 「停在：公共关卡 / 平台页面」. Tests `scripts/test_presubmit.py`, `scripts/test_runner_common.py` (DeepSeek scenarios through the real main()).

## 2. Two sign-in systems (check which one the tenant uses)
**Fast path (JSA-230):** `runner/batch_apply.py prepare | approve | submit <batch.json>` runs this platform inside a (mixed) batch — never waits in place for Joey; a CAPTCHA / sign-in / unknown goes to his queue and the next job starts. ≤ 5 per batch with a sign-in platform.
| | Classic tenant portal | New universal login |
|---|---|---|
| After the e-mail + hCaptcha | the Candidate Profile form, with **Login Name + Password + Re-enter** at the bottom = a new account for this tenant | a redirect to `login.icims.com/u/login/identifier?…` (Auth0, per-company page "登录 <Company>") |
| Account | the runner types the Keychain password (`jobagent-workday`; `-long` when the page asks ≥ 12 characters) into the profile; "Submit Profile" creates it | **one iCIMS account across tenants**: an e-mail that has applied through iCIMS before (the candidate has, in 2025 and 2026) already has a password the agent does not know → both Keychain passwords are rejected ("用户名或密码错误") → the runner stops `signin` |
| Social sign-in | buttons on the profile ("Connect your account") | "Continue with Google" works as a sign-in **only when the iCIMS account is already linked** to Google; otherwise the tenant page says "Unable to log in with the social account…" |

Never use "Reset your password" (Joey 2026-11-03: keep his own password). The universal login uses his own password only
from the Keychain item `jobagent-icims`, which he creates himself (`security add-generic-password -a <gmail> -s jobagent-icims -w`);
without it the runner stops at `login.icims.com` and hands the sign-in to him. 2026-11-03: three refused sign-ins, then
the account locked after a manual try — iCIMS is skipped until the account is unlocked and the Keychain item matches.
Never retry a refused password in a loop: one try per stored password, then stop.

## 3. Flow
1. **Pick** 可投 rows whose `ats_url` / `url` is iCIMS or Jibe (`run_icims.login_url`), internship tier C/D for tests.
2. **Run** (Mac, live data from the main folder):
   `CX_DATA=~/Projects/job-search-agent/data/runner ~/.job-agent-venv/bin/python skills/auto-apply/runner/run_icims.py --url <posting> --resume resume/2026-10/Alex_Rivera_Resume_<Track>_A-Classic.pdf --wait-captcha 15 [--keep-tab]`
   - Jibe / `?icims=1` page → the runner reads its Apply link (`a#link-apply`) into `<tenant>.icims.com/jobs/<id>/login`.
   - E-mail step: e-mail + the required privacy box (`#accept_gdpr`, its text saved as `consent_text` in `form_check.json`) → Next → hCaptcha → the candidate.
   - `--attach <url text>` continues a tab that is already on a step (after a hand-off); `--no-advance` fills and reads back the current step only.
3. **Steps** (a classic tenant: 1 Candidate Profile · 2 Candidate Questions · 3 EEO · 4 Assessments): per step the
   runner extracts every field of the `icims_content_iframe`, answers them through `rules_bridge.js`, fills, reads back,
   presses the step's own button (`pick_button`: never a social button) and stops on: an unknown required answer
   (`needs-user`, listed in `form_check.json → unknown`), a read-back mismatch, a step that does not advance (its
   error texts are logged), a CAPTCHA not solved in time, or the final button.
4. **Unknowns** → ask the candidate once; his answers go into `config/profile.json` (a rule) or a one-off `--answers <json>`.
5. **Close the tab** when the dry-run ends (the runner closes it on `dry-run` unless `--keep-tab`).

### 3 b. Submit (`--folder … --submit`, JSA-093 2026-11-05)
`~/.job-agent-venv/bin/python ~/JobAgent/app/skills/auto-apply/runner/run_icims.py --folder applications/<folder> --submit [--wait-captcha 10]`
(folder = `job.json` with id / url (`ats_url` first) / track / company, the tailored resume, the cover letter if built;
out = the folder; `--wait-captcha` defaults to 10 minutes with `--submit`).
1. **Before the form:** the folder must be in `data/runner/approved_batches.json` (else: dry-run only, printed) and not
   already `submitted` in `results.jsonl` (`run_form.already_submitted` → `STATUS already-submitted`, nothing opened).
2. **At the hand-in button** `submit_gate(submit, no_advance, steps, consent)` decides, in this order: `--no-advance` /
   not approved → dry-run stop · any unknown answer → needs-user · any read-back problem or a field not `ok` →
   needs-user · no fields at all → needs-user · a real error on the current step (the "You will be logged out in 60
   seconds due to inactivity" notice does not count) → needs-user · the e-mail-step consent not approved (`consent_gate`,
   type H) → needs-user · else **press**. Every stop says `not submitted — gate <reason>`.
3. **After the click** `after_submit(url, text, before)` reads the top page + the iCIMS iframe (a Jibe front end may show
   its own thank-you page): `done` (a thank-you / submitted sentence and no step bar, or the last / a Thank-you /
   Confirmation step) → `submitted`, `confirmed_by: page`, `submitted_confirmation.png` in the folder · `next` (a later
   step: the bare "Submit" on a middle step only moved on, type O) → that step is filled, read back and gated again ·
   `refused` (same step, or error words without a bar) → needs-user, "did not go through (nothing sent)" · `pending` →
   the company's receipt e-mail (Gmail read-only, 180 s) → `submitted`, `confirmed_by: email`, else `unconfirmed`
   (queued in `data/runner/queue.md` + push). A hCaptcha after the click → the candidate (`--wait-captcha`), never solved.
4. A stop **after** a hand-in-like click already moved the application on (`maybe_in`) also checks the receipt e-mail.
5. `submitted` → tracker row (`sync_results`), every tab of the job closed (`run_form.posting_key` knows iCIMS:
   `<tenant>.icims.com/jobs/<id>`; the Jibe front-end tab too). Any other submit-mode stop is queued in `queue.md`.
6. Cover letter: a cover-letter slot gets the folder's `*Cover_Letter*.pdf` (upload, wait for the reload, read the name
   back); "Resume or cover letter" stays the resume slot; no letter → an optional slot is noted, a required one unknown.
Tests: `scripts/test_icims_submit.py` (DeepSeek 24: `submit_gate`, `after_submit`, `consent_gate`, iCIMS `posting_key`;
spec `scripts/test_cases/icims_submit_spec.md`) · `skills/auto-apply/runner/test/t_icims_submit_flow.py` (12 offline
flows with a fake tab: no click in a dry run, middle-step Submit, refused, unconfirmed, receipt e-mail).

## 4. Problem types and the rules that keep them fixed

**A. hCaptcha before the form.** iCIMS protects the e-mail step (and "Submit Profile") with hCaptcha; in the CDP-driven
job Chrome it always shows an image challenge. Rule: `hold_for_captcha` — visible `hcaptcha … frame=challenge` iframe
with a real size → `human_check.park` (push names the place) → wait `--wait-captcha` minutes → continue when it is gone;
never answered by a model.

**B. Fields the page names only "Type" / "Address" / "Number".** The phone and address blocks repeat generic labels.
Rule: `field_label` names standard profile fields from their id (`PersonProfileFields.PhoneType` → "Phone Device Type",
`AddressType` → "Address Type", `AddressStreet1` → "Street Address", `CountryCode` → "Phone Country Code", …) before the
answer rules see them; `address_type` rule in `answer_rules.js` (Home). Tests `scripts/test_icims.py`, `t_rules.js`.

**C. iCIMS dropdowns hold a hidden `<select>`.** `icimsdropdown-enabled` selects are hidden behind an `<a …_icimsDropdown>`
combobox with an ajax search box; a typed "(+1) United States" finds nothing, and an option read before the list settles
is detached by the time it is clicked (30 s timeout). Rules: `pick_dropdown` types the rule's `combo` text (or the value
without a leading "(+n)"), waits until two reads of the list agree, clicks the exact title; read back from
`<id>_fakeSelected_icimsDropdown`.

**D. Street address is a geolocation type-ahead.** `TypeToSearchTextFieldDropDown` suggests "1210 South Indiana Avenue,
Chicago, IL 62701" etc.; a suggestion could rewrite city / ZIP. Rule: `enter_manually` picks "— Enter Manually —" (the
field becomes a text box) and types the profile address.

**E. The resume upload posts the form.** The file input's `onchange` submits the page (`uploadResume=1`) and parses the
resume; anything typed before is lost. Rule: upload first, wait for `Resume_Loading` to go, re-extract, then fill; read back
from the hidden `<slot>_FileName`.

**F. Middle name.** The shared rule answers "N/A" for a middle *initial*; iCIMS asks an optional Middle Name → left empty
(the runner skips `middle_initial` on optional fields).

**G. New universal login with an existing iCIMS account.** See §2: wrong password → stop `signin`, the candidate signs in
(or approves a reset to the Keychain password). Google is only a sign-in for a linked account.

**H. Consent at the e-mail step that goes beyond the application.** First Citizens' required "I accept" also covers "no AI
tools in interviews", photos in interviews and a background check. It is required to continue, so the runner ticks it in a
dry-run and saves the text (`consent_text`); before any real submit the candidate approves such wording once (auto-apply
consent rule). Approved by Joey 2026-11-03 (「接受」) for interview terms of this kind — no AI tools in interviews,
photos in interviews, a background check; wording that adds anything else still goes to him first. Rule (submit path):
`consent_gate` → `ask` for arbitration / class action / jury / waiver / automated dialing / prerecorded / consent to
calls or texts / marketing / promotional / newsletter / recruiting messages / talent community / "be bound by", unless an
approved snippet (`config/profile.json → consents_approved[].contains`) is in the text; `ask` blocks the submit
(`gate consent`), the dry-run still ticks the box. Tests `scripts/test_icims_submit.py`.

**I. Address check on "Submit Profile".** "Current City, Zip Code and State combination was not able to be verified. Use
this address anyway? Yes" — a checkbox `name=override` (`id=address_-1`) inside the error. Rule: the runner ticks it (the
address is the profile's own) as `address_override`. Open: on one tenant the profile still did not go through after the
tick + a solved hCaptcha (the button stayed disabled) — next run: pick the geolocation suggestion that is the same
address ("1210 South Indiana Avenue, Chicago, IL 62701") instead of Enter Manually, and compare S/South, Ave/Avenue.

**J. A submit already in flight.** After a click (or a solved hCaptcha) the button carries
`iCIMS_loadingButtonOverlayImage` and stays `disabled`; a page reused from an earlier attempt keeps it disabled forever
(Next never enables). Rules: the e-mail step is always loaded fresh (`goto`), the runner waits for `:enabled` before
clicking, and after a step's click it polls up to 40 s (button enabled again or the step changed) before it judges
"did not advance". The e-mail iframe also reloads once after the first load (redirect adds `mobile=…&width=…`), so the
runner waits for a stable iframe URL and re-fills when the typed e-mail is gone.

**K. Authorization wording the rules do not know.** "Are you legally able to work in the United States?" matches neither
`authorized` nor `auth_today` — and the two give different answers for the candidate (authorized: Yes; authorized as of
today: No, CPT not yet effective). Rule: left unknown → `needs-user`; the candidate decides once, then a rule + t_rules case.

## 5. Dry-run log
Per run: `data/runner/dryrun/icims/<tenant>_<id>/form_check.json` and `run_log.md` (live data folder, not in the repo).
Each dry-run batch is summarised in the session log; company names stay out of this file except in the `Seen:` lines.

## 6. Answers that are easy to get wrong on iCIMS
Phone type = Mobile, address type = Home, phone country code "(+1) United States", Middle Name empty, Login Name = the
e-mail. Work authorization / sponsorship / EEO follow the shared rules (`config/profile.json`, `canonical.json`).

**Cover letter (2026-11-03, Joey):** an optional cover-letter upload slot gets the folder's cover letter by default, like a required one (dry runs: record the slot).

**L. A list that appears only after an answer.** "How did you hear about us? = Job Board" reveals a required "Please specify"
list (CareerBuilder / Craigslist / Indeed / LinkedIn / Monster) that the first field scan never saw, so "Submit Profile"
failed with "Please specify: required". After filling a step the runner scans again for new empty lists; a job-board list
gets `job_board.board_pick` (the row's own board, else the profile default LinkedIn; run with `--job <id>`).
Tests `scripts/test_job_board.py` (DeepSeek 24).

**M. "Finish Later" beside "Submit".** A step's button row is "Finish Later" (save the application and leave) then
"Submit". `pick_button` took the first one that matched "finish" — in a live run that would have saved and left instead
of moving on. Rule: the word "later" is never a forward button (`NOT_NAV`); bare "Submit" on a middle step still counts
as final (`is_final`), so a dry-run stops there. Tests `scripts/test_cases/icims_later_cases.json` (DeepSeek 16).

**N. Universal login vs a tenant profile for the same e-mail.** On 11-03 the Springs e-mail step went to the universal
login (`login.icims.com`); on 11-04, after the hCaptcha, it opened a new Candidate Profile with "Create a login", and the
runner created the tenant account with the Keychain password (20/20 read back). The universal "reset password" for this
e-mail sent no mail and "Continue with Google" answered "Unable to log in with the social account" → no universal account
is linked to this e-mail. Rule: take the tenant profile when it is offered; on the universal login try each stored
password once, then stop (never loop — the account locked on 11-03).

**O. "Submit" on a middle step.** A bare "Submit" on step 2 of 4 (EEO) is treated as the hand-in (`is_final`) because it
may be one; with `--submit` it may also just move on to "Assessments" / "Review". Rule: the click is gated like the
real hand-in; `after_submit` = `next` → the next step is filled, read back and gated again (`maybe_in`: a later stop
also checks the receipt e-mail, since the application may already be in). Tests `t_icims_submit_flow.py`.
