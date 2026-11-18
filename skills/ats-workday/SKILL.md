---
name: ats-workday
description: Apply to a Workday job (*.myworkdayjobs.com, myworkdaysite.com) with the local runner run_wd.py — the runner signs in / creates the account, fills page by page, Claude reads Review, and it submits on gates inside an approved batch — plus every Workday problem type seen so far and the rule that keeps it fixed.
---

# Workday applications (platform skill)

Part of the job-search agent; read with `skills/auto-apply/SKILL.md` and the candidate's facts in `config/`. Code:
`skills/auto-apply/runner/run_wd.py` (+ `wd_page.js`, `wd_signin.py`, `prep_wd.py`, `config/wd_profile.json`).
**After every Workday batch, update §2:** add the new problem to its type (or open a new type) with the rule and the test
that enforces it. Record *what kind of problem* and *how it is solved* — not which company showed it — that goes in the type's `Seen:` line (private: the public export drops it) (Joey 2026-11-02: a
company is rarely applied to twice; the company and date belong in the commit message and the session log).

Status: certified 2026-11-02 (JSA-050) — 50 submitted (56 after batch 5, 2026-11-03: 3 by the runner, 3 finished by Joey), 100 % without Joey, 0 recorded wrong answers, median 296 s
(`skills/auto-apply/references/platform_scorecard_2026-11-02_cert5.md`). Inside an approved batch the runner submits
(`--submit --ds-ok`) once its gates pass **and** Claude has read the Review page. **One application at a time; every run
closes its tab when it ends** (a tab stays open only while a question, Review check or CAPTCHA is handled right away).
Solve problems first; ask Joey only for new facts / preferences / consents / passwords / CAPTCHAs, in the session.

## 1. Flow
1. **Pick + read the live JD** (prefilter → `prep_wd.py` reads the public CXS API into `jd.md`). Check season and length,
   class year (rising junior/senior only, bachelor's only), "must not require sponsorship now or in the future", the
   Workday header's **Time type** (part-time) and a 404 (closed). See §2 type N.
2. **Prep** (Mac): `~/.job-agent-venv/bin/python skills/auto-apply/runner/prep_wd.py data/runner/batches/<name>.json` →
   folder, `wd_job.json`, `jd.md`. Workday questions are not public: they are found page by page.
3. **Materials**: `ds_materials.py <folder> --track <Track>` (one at a time — parallel LibreOffice runs collide). Materials
   are final before the first run (type E: no resume swap later). The runner uploads the resume only.
4. **Run**: `~/.job-agent-venv/bin/python -u run_wd.py "<app folder>" --attach <url text>` in the job Chrome (CDP 9222).
   Resume a stopped run with `--attach <job req id or tenant host>`; the runner continues from the current page. Wait on
   the folder's `status.txt` (`needs-user | handoff | review | done | captcha | signin-timeout`); read only compact files
   (status.txt, wd_needs.json, verify.json) — never whole pages.
5. **Sign-in** is automatic (`wd_signin.auto_signin()`, Keychain `jobagent-workday`, `jobagent-workday-long` where a tenant
   needs a longer password): sign in → else Create Account → e-mail verify link from Gmail (read-only, this tenant's
   link only) → sign in. CAPTCHA / failed sign-in → wait for Joey (`--login-wait-min`, the batch driver passes 0 and
   parks the role); the queue line says why (`failure_code`, type C) and `signin.json` keeps the tenant's message. The password is never printed, logged or seen by a model. See type C.
6. **Page loop** (Autofill with Resume → My Information → My Experience → Application Questions → Voluntary Disclosures →
   Self Identify → Review): read fields → answer → fill with real clicks / keys → re-read each field. Ladder:
   - fixed questions → `answer_rules.js` (answers from `config/profile.json`);
   - a picker whose answer is not offered → the runner collects the **complete** option list, `pick_by_prefs()` picks
     along the profile's preference order, DeepSeek only when no preference matches, NONE + required → Joey;
   - a required question with no rule → DeepSeek triage maps it to a saved fact (`ds_answers.json` + `ds_used.json`);
     essays / opinions / anything not in the facts → UNKNOWN;
   - UNKNOWN → `wd_needs.json` + `status.txt = needs-user`; the runner **keeps the tab and waits** for `answers.json`
     Before a batch (JSA-189): `collect_batch.py <batch> --run` dry-runs every folder with `--wait-min 0 --login-wait-min 0`
     (it stops at the first unknown page, never waits) and lists all `wd_needs.json` questions on one sheet; a general
     answer goes through `qa_add.py` (every later form), `answers.json` only for a question of that one company.
     (`{"<answer_key>": "<exact option>"}`, written on the Mac) and continues on the same page;
   - other wrong fields → DeepSeek click fix (max 3) → `handoff.json`.
7. **Every page is checked before it is left** (canonical audit of that page's answers; on an experience page each
   school's block: entry present, degree level, its own GPA; and every education / work block box against the entry of
   its block, by code — `runner/block_check.py`, JSA-294). A failure stops **on that page**: fix `answers.json`, rerun
   `--attach` — it re-fills the same page, no Back.
8. **Review gate**: `verify.json` (every recorded answer + essentials: legal name, phone digits, every profile company /
   school / language where the tenant has that section) + the **canonical audit** (`canon.json`: recorded answers vs the
   candidate's facts, evidence-backed — a mismatch blocks even when the Review text looks right). `verify.json.deepseek_answers`:
   Claude spot-checks each against the profile (`--ds-ok`). Then submit.
9. **After submit**: Candidate Home shows the req + "Date Submitted" → `save_confirmation.py <url text> <absolute folder>`
   **before** the tab closes; tracker row through `scripts/store/sync_results.py`.

**`--keep-tab`** leaves the tab open whatever the status — only when Joey works in that page right away (2026-11-03).

**L3 — a field the runner could not fix (`handoff.json`)**: look first (`handoff_show.py "<app folder>"`, read-only);
change only the listed fields — no Submit, no Back, no sign-in, no CAPTCHA; one actor per tab (`status.txt` not
`running`); hand back with `run.py "<app folder>" --resume --attach <url text>` — `verify.js` + `canon.py` decide;
cannot fix → `l3_log.md` + `data/runner/queue.md`, tab left for Joey.

## 2. Problem types and the rules that keep them fixed
- **Confirmation from the form itself (JSA-299, all runners):** after Submit a page counts as the confirmation only when it changed (Submit button gone or URL changed, `confirm_page.judge`) and shows a success URL or a success sentence that is new since the click; "thank you for your interest" alone never counts (forms greet with it). No such page → the receipt e-mail. Workday: `wd_done` — the footer Submit button gone or the URL changed (…/jobTasks/completed/application, /userHome). 
- **Rerun resumes (JSA-392):** every saved page is recorded in `checkpoint.json`; a rerun clicks the progress bar to the first page not saved yet (`resume_target`, `jump_to_step`), so My Experience is not saved again (it can drop the second school, JSA-032); a bar that cannot be clicked → every page is walked as before; `--no-resume` forces the full walk; the jump is forward only, each saved page's answers go to `wd_answered.json` at once, and a Review problem deletes the checkpoint.
- **No page confirmation (JSA-306):** `wd_mail_receipt` waits `--mail-wait` s (180) for the company e-mail (Gmail read-only): mail → submitted, `confirmed_by: email`; none → unconfirmed + queue line (JSA-306).
**Fast path (JSA-230):** `runner/batch_apply.py prepare | approve | submit <batch.json>` runs this platform inside a (mixed) batch — never waits in place for Joey; a CAPTCHA / sign-in / unknown goes to his queue and the next job starts. ≤ 5 per batch with a sign-in platform.

**A. The page is not ready / not what it seems.** Workday renders late and lazily, re-renders whole blocks after each
change, may show a draft ("Continue Application" instead of Apply), redirect to Candidate Home after sign-in, follow the
browser language, show the sign-in form seconds after the progress bar, or expire a session left idle (~20 min →
"Something went wrong", 0 fields).
Rules: always open `/en-US/`; decline the cookie banner; wait for `adventureButton` / `progressBar` and re-read until the
field count is stable (`settle()`); relocate fields by block + label and retry once; after filling, re-read for
conditional questions — **up to 8 levels**; fall back to "Continue Application"; rerun `start_apply()` when outside the
wizard; wait ≤ 12 s for a late sign-in form; wait until the Review text length is stable before checking it; retry a
stopped run **fresh** (new tab) instead of attaching to a tab idle > 20 min; a crashed tab → rerun fresh. Success toasts
use `role=alert` too — `__wdErrors()` ignores them.
- *An experience page that plans 0 fields* (JSA-065) is classified by `zero_field_experience()`: a Workday error page
  ("Something went wrong", expired session) → stop: rerun fresh, and if it repeats Joey withdraws the draft in Candidate
  Home; **only a résumé upload** (no work / education / language section, upload done) → nothing to check, continue —
  Review then has no school / company essentials; sections present but empty → stop, never advance unchecked.
- *Save and Continue that does not take* (JSA-071): a step counts as changed only when the new step is non-empty, differs,
  the old page's fields are gone, and that holds on two reads (`step_changed()`); otherwise Save is clicked **once more**
  (never on a step labelled Review). Review counts only when the progress bar says Review **and** no form field is left
  (`is_review_page()`); a "Review" bar over the old page waits 9 s, then stops with a handoff instead of reading it as Review.
Tests `t_wd_logic.py`, `scripts/test_wd_fixes_1103.py` (DeepSeek cases `wd_zero_fields_*`, `wd_review_step_*`).
- *Error page right after sign-in*: Apply → sign in over a saved draft starts a second application ("Something went wrong"); the runner reopens the job and takes Continue Application.

**B. Never submit by accident.** On Review the footer "next" button **is** Submit, also on non-English pages.
Rule: `next_page()` reads the button label and refuses anything matching `SUBMIT_RX` (submit / 提交 / …) and any
`is_review()` page (locale-proof); only the submit gate at the end of `main()` may click Submit (`t_wd_logic.py`).
A page-advance helper must never be able to submit.

**C. Sign-in and account creation.** Social chooser before the form (sometimes two copies of "Sign in with email" — click
each visible copy, lowest first); `noCaptchaWrapper` is not a CAPTCHA; "signed in" must hold twice, off `/login`, with no
verify banner; account-terms box that will not tick (check → force → label → JS click, else Joey); Create Account that
needs the click on the `click_filter` overlay; e-mail verification (the link host must be **this** tenant —
`verify_pattern()`, look back 24 h, newest 60 mails; parallel runs once took another tenant's link); a late login page after
the verify link (wait 15 s); the in-wizard "Create Account/Sign In" step (run `auto_signin` again); tenant password
length rules (`choose_password()` → the long Keychain item); a lingering "verify your account" after one fresh retry →
skip the role (Joey's rule); "wrong password / locked" on a tenant where Joey had an old account → Joey. Tests
`t_wd_signin.py`, `test_verify_pattern.py`, `test_verify_mail.py`, `test_choose_password.py`. The agent never changes Joey's passwords.
- *Degree option "<abbreviation> - <full name>" refused by the canonical audit* (JSA-282). Symptom: My Experience not
  left — `degree_level = 'B.A. - Bachelor of Arts' (want level he holds …)`, a true answer (UIUC B.A.) handed to Joey
  (Vanguard 2026-11-10). Cause: the accept patterns are anchored at the start ("^bachelor of arts") or end ("^b.a.$"),
  so a short prefix broke both. Rule: for `degree_level` (`canon.ABBR_PREFIX`) a prefix of 1–6 letters with dots, then
  `- – : / |`, is cut off (`canon.abbr_rest()`) and the full name is judged by the same accept rules; reject patterns
  (Technology, MBA, doctorate, associate) still see the whole text. Test `scripts/test_degree_abbr.py` (DeepSeek cases).
- *Wrong degree picked from a prefixed list* (JSA-282, same run). Symptom: UChicago block's Degree = "M.S.T. - Master of
  Science in Taxation" (dry run, not submitted). Cause: (1) `degree_rank()` was anchored too, so every "<abbr> - …"
  option ranked the same and page order won; (2) a "Master of Science in <another field>" counted as his M.S. Rule
  (Joey 11-10): rank on the full name (`degree_full()`); an option that names a field is his only for his fields
  (`canon.degree_field_ok()`: master → data science / applied data science / analytics / statistics / computer science;
  bachelor → economics) — any other field is never picked and the canonical audit refuses it; order plain M.S. →
  plain Master's → M.S. in his field → the rest. Test `scripts/test_degree_field.py` (DeepSeek cases + the Vanguard list).
- *"Please provide your immigration status" answered CPT* (JSA-287). Symptom: Application Questions not left —
  `immigration_status = 'CPT' (want F-1)` (Vanguard 2026-11-10, "If no, please provide your immigration status in the
  U.S."). Cause: `immigration_status` (F-1) knew only "current / what is your immigration status"; the bare
  "immigration status" at the end of `auth_kind` (CPT) took the rest. Rule (Joey 11-10): any fill-in that asks the
  immigration status is F-1 (not a yes/no question, not sponsorship, not how long / number of / petition); `auth_kind`
  never matches "immigration status". Test `scripts/test_imm_status_rule.js` (DeepSeek cases + the Vanguard label).
- *Verification mail from the tenant's own HR domain* (JSA-274). Symptom: "waiting for the verification e-mail" → 3 min →
  `no_verify_mail`, though the mail is in Gmail (Vanguard 2026-11-10: `CrewCentral_noreply@vanguardhr.com`, "Verify your
  candidate account", link on `vanguard.wd5.myworkdayjobs.com`). Cause: the search asked IMAP for `FROM workday` only.
  Rule: the sender is a signal, not a filter — `wait_verify_link()` reads every INBOX mail since the account form
  (− 2 min clock margin; `gmail_code.recent_mails()`, headers first, bodies only for mails in the window) and
  `choose_verify_link()` takes a **tenant link** (host match `verify_pattern()`, or `*.myworkday.com/<tenant>/…`) on its
  own; a mail without one counts only with a verify subject AND a sender domain naming the tenant / company (folder
  name); preference tenant link > verify subject > newest. `tenant_mails()` (failure diagnosis) also counts the tenant's
  own domain. Spec `scripts/test_cases/verify_mail_spec.md`, test `scripts/test_verify_mail.py` (DeepSeek cases + the
  real Vanguard mail).
- *Sign-in still fails after the create-account form* (JSA-207). Symptom: "account form submitted → credentials submitted →
  sign-in failed after creating the account", the queue only said "sign in / create the account". Cause: three different
  cases looked the same — (1) **Joey's own old account** on the tenant (he applied there before; the create form says
  nothing or "already exists" and the Keychain passwords do not open it), (2) **a new account whose verification e-mail
  never came** (or an earlier run's account still unverified), (3) **a tenant-specific answer** the runner does not read
  (locked, no message). Rule: after every create / sign-in submit the runner keeps the tenant's alert text
  (`_messages()`, e-mail masked, never a password) and `message_kind()` reads it (locked > exists > wrong_password >
  verify > none; "check your email and password" is a wrong password, not a verify request); a slow tenant gets a second
  wait. Before giving up on a fresh-created account it opens **this tenant's** verify link from Gmail (14 days back, host
  match `verify_pattern()`) once and signs in again. Then `failure_code()` decides from the trace + this tenant's Workday
  mails in Gmail (`tenant_mails()`, read-only, headers only): `locked` · `old_account` (a mail from before
  `AGENT_SINCE` 2026-10-28, no agent verify mail — or the tenant said it exists) · `agent_account_password` · `no_verify_mail`
  · `no_answer` · `other`. The code + Joey's to-do (`JOEY_TODO`) go into the log, `signin.json` and the queue line
  ("WORKDAY SIGN-IN: … [old_account] — Joey: sign in with your old password (or Forgot your password?) …"). The agent
  never resets a password: old accounts and locked accounts are Joey's. Tests `t_wd_signin.py` (mock modes oldacct /
  lateverify / locked), `scripts/test_wd_fixes_1105.py` (DeepSeek cases `wd_signin_fail_*` + the 11-05 traces).
  a Workday employer (agent account verified 11-01, no readable answer on 11-05 — needs a live look) 11-05
- *Generic "…or your account might be locked." read as a lock* (JSA-334). Symptom: first sign-in on a new tenant →
  "failure type locked", handed to Joey with `tried_long: false` and no Create Account try. Cause: Workday's one generic
  alert for every failed sign-in ("You may have entered the wrong email address or password or your account might be
  locked.") matched `LOCKED`. Rule (Joey 11-12, fix B): only a **definite** lock is `locked` ("has been locked", "is
  temporarily disabled", "too many failed attempts", "locked out"); hedged / conditional / future mentions ("might / may /
  could be locked", "if your account is locked", "after 5 failed attempts your account will be locked") are removed
  first (`HEDGED`, `WARN`) and mean `wrong_password`. After a wrong password `after_wrong()` decides: the long Keychain
  password once → this tenant's Gmail mails (`tenant_mails()`, read once per run) — an old-account mail (before
  `AGENT_SINCE`, no agent verify mail) → `old_account` to Joey **without** creating an account → otherwise Create
  Account (one try per run) → still failing → `failure_code()` as above. Never a password reset. Tests
  `t_wd_signin.py` (mock modes generic / longacct), `scripts/test_wd_fixes_1105.py` (DeepSeek cases `wd_signin_hedge_*`).

**D. Résumé autofill blocks.** The parser invents blocks (projects / clubs as jobs), mixes descriptions, adds or drops
languages, names blocks "Work Experience N", "Professional Experience N", "Your Experience N" or "Academic Experience N".
Rules: blocks are matched to `config/wd_profile.json` **by company / school name**, never reusing a taken entry; empty new
blocks get the next unused entry; everything else is deleted; missing entries are added with Add / Add Another;
`block_kind_of()` checks education (educat / academic) **before** work; languages count as entries too (named blocks keep
their language, empty ones take the unused profile languages, Mandarin before plain Chinese, never Cantonese); the
description is always the approved résumé wording from the profile. Tests `test_block_kind.py`, `test_language_blocks.py`.

**E. Back over My Experience loses education entries.** On most tenants only the entry saved last survives a Back.
Rules (JSA-032): get every education field right on the first pass; check each page before leaving it; `wd_goto_step.py`
refuses a Back over My Experience (`--allow-education-loss` only on Joey's decision, then re-check every block); a fix on a
page after My Experience may go back; no resume swap once the wizard started (withdraw the draft and start fresh).

**F. Education fields.** Degree and field-of-study pickers rarely have the exact name; GPA and degree were once copied
from one school's block into the other by a shared label; schools are spelled differently per tenant; some tenants have
no education section at all.
Rules: the master's picks **Master of Science** first, never Technology / MBA-only / law / executive / education specialty
masters (`master_options()`); the bachelor's picks B.A. → plain Bachelor's → combined Arts, never a specialty or a lone
B.S. (`bachelor_options()`); level-only lists (Graduate / Post Graduate / Undergraduate) map by level; level-worded bachelor options ("Bachelor's Level Degree", "4-year Degree (Bachelor's)") count as a plain Bachelor's, and a post-graduate option that lists PhD as an example ("Post-Graduate Degree (Master's, PhD, JD, etc.)") is the master's level for the block check; field of study
follows the profile's `Field_prefs` order through `pick_by_prefs()` (exact → the closest of the substring-with-≥-2-real-words / all-token matches, JSA-283),
the model only when nothing matches, optional + nothing fits → empty; per-school values only (GPA '' stays empty; required
+ empty → "N/A"), no shared-label fallback; `School_alts` for tenant spellings; schools are essential on Review only where
the tenant has an education section (`has_education_section()`); per-application overrides `edu:<School>:Field|GPA|Degree`.
**School search by alias (JSA-370, an employer 2026-11-12):** a tenant's school prompt may answer the profile's full name with "No items"
(the list spells UIUC differently or searches word starts). `fill_one` therefore searches every name from `school_queries()` —
the facts' `School`, its `School_alts`, the general `SCHOOL_ALIAS_TABLE` names for that school (UIUC, "…at Urbana-Champaign",
"Illinois Urbana-Champaign") — and accepts an option by `same_school()` (same words in any
order, ignoring of / at / the / punctuation; "University of Illinois Chicago" or "Urbana University" never match). Only when no
alias finds the school does the field go to DeepSeek / Joey. The table holds only well-known short names of schools the profile
lists; never add a school the facts do not name. Review's "education entry" check keeps its substring test for the facts' names only; aliases match by `same_school()` (a bare "Chicago" must not pass for UChicago).

**"Required" on a box we filled (JSA-369, Micron Self Identify 2026-11-11):** the CC-305 Name box read back "<the profile name>" yet the
page answered "The field Name is required and must have a value" (the value sat in the input but not in the form's state, or the
error was stale). `filled_but_rejected()` picks text boxes we filled with a real answer that the page names in a required error;
the loop types them again key by key (`_typed`) and presses Save once more, once per page. Zero answers stay with
`zero_rejected()`; boxes we left empty are not retried. Not replayed on a live Micron page: the retry is the generic recovery.

**0 fields on a page after a rerun (JSA-371, Midland 2026-11-01 / a Workday employer 2026-11-12):** `--attach` / a rerun reads "My Information"
as 0 fields while it is still rendering, then Save fails with "no Save and Continue button". `reread_empty_page()` waits 3 s and reads
(`extract()` only — never `do_page`, which uploads the résumé again) a non-autofill, non-file, non-experience, non-Review page up to 3 times, then `do_page` runs once; experience pages keep their own stricter
re-read and `zero_field_experience()` verdict. Still 0 fields after the waits → the old path (Save / its error) decides.

**Skills box takes one skill per search (JSA-372, a Workday employer 2026-10-30 / a Greenhouse employer ePro, a Workday employer 2026-11-12):** the qa answer for "Type to Add
Skills" is a list ("Python, SQL, R, …"); typed whole it finds nothing. `skill_items()` splits it (only on a label with "skill"), `fill_one`
searches and picks each skill on its own (`_one_of`: the chips already added are never cleared; a skill the tenant does not offer is
logged and skipped — partial is accepted on purpose, none added at all = failure; chips that are not one of the skills are cleared first, a skill already shown counts as added on a rerun), and `check_one` reads the chips back: every added skill must be shown
(`skills_present()`: whole-name match, "Python (Programming Language)" counts for "Python", "R" is not "Rust"). Not replayed on a live
tenant page.

**Assessment step = Joey's task (JSA-374, EMC / Copart / Allison / Centene):** a wizard step named like a third-party assessment ("Take Assessment",
questionnaire, WOTC — `joey_step()`) is never clicked (Save on it only says "page did not change"). The run stops with status
`assessment` (`joey_step_result()`: state `needs-user`, no `failed` entry, no handoff.json) and queues one line "JOEY TASK: … open the saved draft
(Continue Application — the tab is closed after the run) and take it, then rerun". Every rerun that stops on the same step queues the line again (queue is append-only). Before this it was logged as a failed handoff.

**Résumé-parsed values in a block (JSA-294):** the résumé parse writes UIUC's "Overall Result (GPA)" = the major GPA 3.85
(want 3.60), Hyde Park's Job Title = "Job Searching Agent" (the side project) and its Role Description = the project text;
a fill that does not take would leave them. Rule: before a page is left, `block_problems()` reads
every education and work block box as the page shows it and compares it with the entry of its block (`block_check.py`:
school, degree level, field, from / to, GPA — overall 3.60 · major 3.85 · institution 3.81 · none for the M.S.; job title,
company, location, dates, "currently work here", description); a wrong box stops on that page. Test `scripts/test_block_check.py`.
Tests `t_wd_logic.py`, `test_pick_by_prefs.py`, `test_degree_rank.py`, `test_bachelor_rank.py`, `test_edu_section.py`.
Seen (JSA-294, parse values before the fill — the fill overwrote them, Review screenshots show 3.60): a Workday employer ×4, Jain ×4, an employer, BJ's, a Workday employer, a Workday employer 11-01 – 11-10 (GPA); a Workday employer, a Workday employer (Job Title). Note: run_wd's wd_log / fields.jsonl record that pre-fill value as the page value (JSA-320).

**G. Dates.** Real inputs are hidden behind a display element; tenants split dates into parts; month-year answers land in
MM/DD/YYYY boxes. Rules: click the visible `dateSection…-display` and type digits; compare dates as numbers; date fields
stay type `date` through the bridge (no options sent) so the rule's date is used, never a season text; month + year into a
box with a day → the first of the month (`date_digits()`). Tests `test_date_digits.py`, `test_bridge_date.py`.

**H. Name, phone, address, country.** "Phone Extension" matched the phone rule; Workday-only questions (device type,
country phone code); middle-name fields print inside the name; the Preferred Name group's sub-fields are labelled just
"First Name"; the country list has "United States Minor Outlying Islands" before "United States of America"; Review prints
the phone with "+1" and no county. Rules: phone excludes "extension" and the extension stays empty (Review fails on it);
phone values compare by digits; device type = Mobile / cell / **Cellular** ("Home Cellular" beats "Home"; a list with no
mobile option asks Joey, never plain Home / Landline; "Phone Type" is the same question — JSA-185, `scripts/test_phone_device.js`);
middle name always empty; `preferredName` fields get the
"Preferred" prefix; country picks are exact (`United States (of America)`, US/USA), Review fails on "Minor Outlying";
county is not checked on Review.

**I. Work authorization, sponsorship, immigration status** (the answers come from `config/profile.json`; for a restricted
status such as F-1 / CPT the traps are): "authorized for **any** employer" is not "authorized" (`any_employer` wins);
"authorized **as of today** / effective now" can differ from "authorized"; "currently on OPT" is its own question; "Yes,
with restrictions" wins when offered and an unrestricted / permanent / citizen Yes is never picked; "sponsorship now"
must not match a label that mentions "future" anywhere; "please provide details / describe your visa status" is a
free-text question (`visa_details`), not the status pick; a status list without the plain status → the closest one, never
a status the candidate does not hold; statements like "I require sponsorship to work in this country" are valid answers
in both audits; "type of sponsorship you require" and "details of your work permit (type / expiry)" are not yes/no
questions. **JSA-310 (Joey 2026-11-11, `work_auth.claim_authorized`): every authorization question = Yes** — "for any employer" /
"without restriction" / "as of today" too; the unrestricted / any-employer Yes wins, "with restrictions" / "require
sponsorship" only when no plain Yes is offered, never "not authorized"; "…any employer WITHOUT sponsorship" = the
sponsorship question (No); "permanently authorized" = No; never a citizen / PR / no-sponsorship Yes. Tests `test_jsa310_auth.js`, `test_auth_restrict.js`, `test_imm_answer.py`, `test_immigration_label.py`, `test_spons_statement.py`,
`test_spons_canon_label.py`, `test_work_permit_label.py`.

**J. EEO questions.** Veteran options that start like the right answer but are not ("…just not a protected Veteran",
"…but am a Military Spouse"); many valid wordings of the same answer (suffixes, quotes, a leading "No,", "Not Applicable");
gender / disability questions phrased without the topic word; a "Hispanic" sentence above a race list; the whole VEVRAA
paragraph as one label. Rules: veteran picks anchored (`^I am not a (protected )?veteran\.?$` first; spouse / but /
dependent refused), the audit accepts the known valid wordings; gender rule also "your gender" / "the gender you…";
CC-305 "check one of the boxes below" = disability rule; a race list under a Hispanic label is the race question;
labels > 300 characters: answer the last sentence first, else the rule whose topic is in the options. Tests
`test_veteran_canon.py`, `test_race_hispanic.js`, `test_long_eeo.js`.
- *An optional free-text box that lists protected categories blocks the Review gate* (JSA-206). Symptom: "EEO question
  left empty on Review: race, religion, national origin…" — the box was "Please list professional, trade, business or
  civic activities … (Exclude those which would reveal sex, race, religion, … disability or other protected status)",
  optional and rightly empty. Cause: the Review check searched the flat page text for a topic word within 140 characters
  before "No Response". Rule: only a **real EEO question** blocks (`eeo_left_empty()`: label line + "No Response"; topic
  gender / sex / race / ethnicity / Hispanic-Latino / veteran / disability); a do-not-disclose instruction ("exclude",
  "do not include / list / mention …", "which would reveal", "other protected status" up to ")" or the sentence end) is
  not searched, and a field the runner recorded as a free-text box (textarea / text) is never EEO; an equal-opportunity
  statement in front of a real question still counts. Test `scripts/test_wd_fixes_1105.py` (DeepSeek cases
  `wd_eeo_review_*` + the Central Hudson Review fixture). Seen: Central Hudson 11-05

**K. "How did you hear about us".** Tenant-specific, often two levels (category → site), sometimes on a non-English
tenant or as a second question. Rules (Joey 2026-11-01): never an option that claims a person / contact / referral /
event / school / employer / agency (`source_option_ok()`); neutral channels (company website / job board / social /
Other) first (`source_pick()`); if every option is a claim, stop — never fall back, and never let DeepSeek triage pick one
(`no_triage`). Put a chosen source in `answers.json` so reruns keep it. The question is not always a menu (JSA-067): a
**checkbox / radio list** ("How did you learn about the opportunity") is picked from its read options at plan time; a
select is opened by its button (its hidden text input does not open it) and placeholders ("Select One", "选择一个")
are not options — a required menu with **no real options** (the tenant's list is empty, in every locale) → stop and ask
Joey (skip the role or contact the company). Tests `test_source_option.py`, `t_wd_logic.py`, `scripts/test_wd_fixes_1103.py` (`wd_source_pick_*`).

**L. Answers that need care.** Reruns compare with the runner's own answer — anything changed by hand must also go into
`answers.json`; checkboxes are answered with their exact option text; multi-select answers may be a list or "a | b";
prompts take one value per search (search the text before " (" when Workday finds nothing); salary text boxes keep digits
only (`salary_number()`); contact details of past employers = "available upon request", may contact = Yes (Joey); new
standing answers go into the profile with a test, never only into one folder; a known fact asked in a new wording
("certify whether you are a previous employee", "date available to begin employment") is a rule gap — widen
`answer_rules.js` with DeepSeek cases (`scripts/test_answers_1103.js`), not only `answers.json`. Test `test_salary_number.py`.
"Do you meet the years of experience required for this position?" (and "minimum / required years of experience … for this role") is a yes/no about the JD's requirement, not the years-of-professional-experience picker — DeepSeek triage once mapped it to "No prior experience" (VSP 11-03). Rule `yoe_meets` (JSA-105) answers it from `<folder>/jd.md` (plan_build passes the JD to the rules): no years asked (or 0 / "0-2") → Yes; any number of years, required or preferred, or no `jd.md` → a need for Joey with `no_triage` (DeepSeek never answers it). A rule that must read the JD returns `ask: true`; keep that hand-off, never a profile default. Tests `t_rules.js`, `t_plan_ats.py` (yoe), `scripts/test_yoe_meets.js` (DeepSeek cases).

**M. The audits must stay strict and be widened only with a test.** Verifying Review against our own plan cannot catch a
wrong plan — the canonical audit compares recorded answers with the candidate's facts and blocks on a mismatch. Its false
positives (a right answer in an unexpected wording, a label that only looks like the audited topic — "institution",
"high school", "diploma", "majority owned", a "sponsors" clause in an arbitration agreement) are fixed by widening the
accept list or adding `label_not` **with DeepSeek cases**, never by weakening the gate. A value confirmed by Joey outside
the patterns → `canon.py --learn <tenant> <key> "<option>"`.

**N. The JD said more than the gate read.** School-year or 6-to-12-month internships, part-time campus jobs (Workday
"Time type"), "no sponsorship of any kind" only on the form, year-round postings, closed postings (CXS 404). Rule: read
Duration / Timeframe / Time type and the form's own statements before the batch; drop and mark 不可投 / 已关闭.

**Q. Files beyond the résumé** (JSA-068). Some tenants want a cover letter (a "Cover Letter" field, or a question "I have
uploaded both my cover letter and resume" after My Experience — too late to go Back, type E). Rules: `file_kind()` names
each file field (cover / reference / transcript / résumé); `files_for_field()` uploads the résumé only when the field shows
no file yet, plus the folder's cover-letter PDF into a multi-file résumé field when the application wants one (JD mentions
a cover letter, or `answers.json` `"files:cover_letter": true|false`), and the cover letter into a cover-letter field;
`uploads.json` records it, and only then the "uploaded both" question is answered Yes. Reference letters and transcripts
are Joey's documents (needs, never triaged). Tests `t_wd_logic.py`, `scripts/test_wd_fixes_1103.py` (`wd_files_*`).
**Upload box text is not a document name** (JSA-368). A Workday file box shows the file it already holds
(`<First>_<Last>_Resume_X.pdf` — underscores defeat `\bresume\b`) and the widget's own words ("Upload a file (5MB max)",
"Drop files here", "Select files"). The materials gate (`materials_gate.wd_slot_kind`) strips both before naming the
box: nothing else left → the résumé box the runner fills (never `other_file`, whatever its position on the page); a
named other document — in the heading or in the held file name (cover letter, transcript, writing sample, unrecognised text) — keeps its kind and still stops; bare widget words with no file stay other_file (only the page's first box is exempt).
Test `t_materials_gate.py` §16b. Seen: a Greenhouse employer BI 11-12.

**O. Handed to Joey by design.** CAPTCHAs and "verify you are human" questions (skip the role), WOTC / tax-credit
assessments and other third-party questionnaires, letters of recommendation, consent boxes not yet in the profile,
passwords, essays that no Confirmed story answers. The agent never answers these itself. A wizard **step** that is an
assessment / questionnaire ("Take Assessment", WOTC, skills test) is recognised before anything is clicked
(`joey_step()`) and stops with a handoff; the draft keeps the filled pages for Joey (test `scripts/test_wd_fixes_1103.py`,
`wd_joey_step_*`).
**CAPTCHAs and human checks are always Joey's — never filled by a model or a rule**: a label matching `HUMAN_CHECK_RX` is never sent to DeepSeek triage (FHLBank Indianapolis 11-03: triage had answered "count the t's" with 4; tests `t_wd_logic.py`, `scripts/test_wd_fixes_1103.py` `wd_human_check_*`). **Hand-off (JSA-106, 11-03)**: the runner does not wait on the page; it parks the check (`human_check.park()` → `data/runner/human_checks.jsonl` + queue + one push with the question text and options), keeps the tab and the batch driver goes on to the next role. After Joey answers in the tab, `run_wd.py <folder> --attach <req id>` takes **his** value into answers.json and continues. After the batch: `human_check.py --list --push`. `--wait-human` keeps the old wait-in-place. Essays: a draft goes into the box only when a Confirmed story answers that exact question (M4 for "which value do you connect with"); a "why this internship" with no confirmed motivation stays empty for Joey. Joey may skip such roles (11-03: the assessment and essay roles).

**P. Operations.** One run at a time and close every finished tab (`tab_should_close()`; too many tabs once made CDP time out);
save the confirmation before the tab closes, with an **absolute** folder path; keep only Claude in Chrome as an extension
in the job Chrome; read compact files, not whole pages (cost: ≈ 16–30 k Claude tokens per clean application,
`data/runner/usage_2026-10-30_workday.md`). A runner script that adds a wrong `config/` folder to `sys.path` runs in one
checkout and fails in the release (`No module named 'paths'`): every config insert must reach the repo's `config/`
(`scripts/config_path_check.py`; `scripts/test_config_paths.py` imports each entry module the way `python <script>` does, JSA-184).

**Q. Recert round 11-10 (JSA-267, 269, 270, 271).**
- A canonical pick must apply the "…without sponsorship…" inversion: use `canon.pick_for(key, label, options)` /
  `canon.judge(...)`, never `canon.pick` alone. Otherwise the plain sponsorship answer (Yes) replaces the rules' right No.
- Review prints the state inside the address ("<City>, <ST> <ZIP>"): `state_on_review()`.
- Review folds a long multi-select behind "MORE (n)": `expand_review()` clicks it before reading.
- A run with no open question deletes the old `wd_needs.json`.
- "Schools Attended N" is an education block. When an Add click does not raise the block count (`blocks_of()`), the run stops
  and records a failure instead of piling up blocks.
- `batch_apply approve` accepts a folder whose only open item is the DeepSeek spot-check; `submit --ds-ok` still needs it.
- The plan's block test uses `block_kind_of()` too (JSA-272): before, "Schools Attended N" fields were answered as plain
  questions (every block got University of Chicago) and leftover blocks were never deleted. Now they are matched by school name
  and the extras deleted (an employer: 13 deleted, UIUC added, Review clean).
- Some tenants keep digits only and count **0 as empty** on a required box ("current annual salary", BCBS NE: "0", "0.00" →
  "000" all refused). `zero_rejected()` turns that page error into needs-user ("Joey decides: another number, or skip") —
  no true number fits, so the runner never types another one.
- A page can render its fields late (NCR Voluntary Disclosures: 1 of 5 fields for 0.7 s; the Hispanic question was left
  empty and caught on Review). `settle()` now wants the same field count on 3 reads. When Save and Continue does not take
  and fields the plan never saw are on the page (`unplanned_fields()`), the page is read and filled again (once per step)
  instead of clicking Save a second time.


**Text answers the box's own limits refuse (JSA-312, shared with Oracle).** A dry run's read-back does not run the page's
checks. Rule: `wd_page.js` reads each text box's maxlength / minlength / pattern / type and hint text; `run_wd.limit_gate`
completes a bare address in a url box with `https://` (`field_limits.fix_url`) and turns an answer that is still too
long / too short / not a url into a question for the candidate (required) or an empty box (optional) — never typed in,
never cut. Tests: `scripts/test_field_limits.py`.

**The run log kept the page value from before the fill (JSA-320).** `wd_log.json` used to keep each field's `value` as
first read, before the runner typed anything. On many tenants that is the résumé parse: the UIUC Overall Result held the
major GPA 3.85, and a work block's Job Title held "Job Searching Agent". The audit and the replays took it as the submitted
answer and logged 8 wrong answers (a Workday employer ×4, Jain ×2, an employer; a Workday employer's title and description). The Review
screenshots show 3.60, Business Analyst Intern and the Hyde Park bullet. Rule: `check_one` keeps the read-back and
`record_field` writes it as `page` (and `value`), with the first-read value as `before`. A field fixed after its last
check is read again before the page is logged. Old logs: `scripts/learn/convert_fields.wd_field` takes the answer as the
page for a filled field outside `failed`, because it passed the read-back check. The 8 lines moved to
`data/runner/wrong_answers_withdrawn.jsonl`. Tests: `scripts/test_wd_record.py`.

## 3. Review checklist (what Joey and Claude look at before Submit)
Every value matches the candidate's facts in `config/profile.json` / `config/canonical.json` / `config/wd_profile.json`: legal +
preferred name, address, e-mail, phone (Mobile, **no extension**) · Work: exactly the profile's jobs, no projects / clubs as
jobs · Education: the profile's schools, the master's as the **Master of Science** option, the bachelor's level right ·
Languages: every profile language, Fluent · work authorization as in the profile (type I) · immigration status = the
profile's plain status · every `verify.json.deepseek_answers` item matches the profile · EEO answers = the profile's (type J).

## 4. Open items
- None open from JSA-065 / 067 / 068 / 071 (fixed 2026-11-03; see types A, K, Q).
- History: the per-company problem table (#1–#144, 2026-10-28 → 11-02) is in git history before this rewrite.

**Text box listing the countries that need sponsorship (2026-11-10, JSA-279).** Symptom: "For those locations or
countries … indicate all locations or countries for which you now, or in the future, require sponsorship … If this does
not apply, indicate N/A" (HPE) was answered "Yes" by `spons_future`; canon `sponsorship_countries` stopped it before the
page was left. Rule: a list / indicate / which-countries question about sponsorship → rule `spons_countries` (high-risk,
work_auth group), answered from the profile's sponsorship facts: needs it now or later → "United States", needs it neither
→ "N/A"; a question that opens with Do / Will / Are / Would you stays the Yes / No `spons_future`. "Name the countries …"
is not the full name. Same day: "Without sponsorship, are you legally permitted to work in the country where this job is
located?" (Ankura) is the FUTURE question → No; a "without sponsorship" question is the now one only with now / this
internship / this position wording or OPT / CPT named as an example (= canon `NOW_ONLY_RE`). Tests: `t_rules.js` (JSA-279 cases), `scripts/test_cases/spons_countries_*` (DeepSeek cases +
verdicts).

**Sponsorship "now … or at any time after graduation" (2026-11-04, JSA-159).** Symptom: a sponsorship question that says
"now" and also a future time ("at any time after graduation", "later", "upon graduation") was answered No. Cause: canon
`sponsorship_now` / rule `spons_now` keyed on "now" only. Rule: any future wording = the future question = Yes; "now"
alone (also "currently", "at this time", "to begin this internship", before or after "sponsorship") = No. Test:
`scripts/test_spons_now_future.py` (DeepSeek cases, rules + canon). Seen: a Workday employer 11-04 (dry run).

**Work-history and bonus boxes (2026-11-04).** A text box "Employer 1: list your work history … dates, contact information,
may we contact" gets company, title, city, dates and "May contact this employer: Yes" — no supervisor contact is on file
and none is invented (Joey 「Yes to both」). "Bonus expectations" bands → the lowest band (rule `bonus`, t_rules). Seen: a Workday employer 11-04.
A tenant where a fresh account cannot sign in and no verify e-mail arrives (gaig twice) → park the role for Joey (type C;
since JSA-207 the queue names the case).

**R. Critical answers taken from the wrong part of the question (JSA-281, audit 11-10).** A rule or a saved qa entry matched the wrong part of a critical question, or one merged entry covered two different
questions; the page matched the plan, so nothing stopped it. Rules: the **fact gate** (`runner/fact_gate.py`, called by
`canon.audit` before every submit, on the page records and the plan's full-label records) checks conviction,
any-employer authorization, degree level (completed vs once graduated / pursuing), major (undergrad = Economics, a
second major / minor = none), the internship start date, a value that is a regex (`^agree$`) and the user's saved
answer for the exact question (when answers.json wrote the value) against config/profile.json — a mismatch blocks the
submit and goes to Joey (an exception he confirms: `canon.py --learn <tenant> fact:<key> "<value>"`). In the rules:
`conviction` (answers.conviction; the asking sentence decides, not a "criminal background check" notice), `any_employer`
also for "any U.S Employer", `majorWhich` (undergrad / second major / minor), `name_pronunciation` also misspelled,
`comp` also "(salary and bonus)", `applied_before` from the tracker (never a saved fixed answer; Joey 2026-11-10). The
prefetch keeps wordings with different marks apart (`form_prefetch.sense`). Tests: `scripts/test_fact_gate.py`
(DeepSeek 45 + the audit's 9), `scripts/test_jsa281_rules.js` (DeepSeek 40), `scripts/test_prefetch_sense.py` (25).
