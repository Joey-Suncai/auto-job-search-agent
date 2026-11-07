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
   school's block: entry present, degree level, its own GPA). A failure stops **on that page**: fix `answers.json`, rerun
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
`t_wd_signin.py`, `test_verify_pattern.py`, `test_choose_password.py`. The agent never changes Joey's passwords.
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
  Invesco (agent account verified 11-01, no readable answer on 11-05 — needs a live look) 11-05

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
B.S. (`bachelor_options()`); level-only lists (Graduate / Post Graduate / Undergraduate) map by level; field of study
follows the profile's `Field_prefs` order through `pick_by_prefs()` (exact → substring with ≥ 2 real words → all tokens),
the model only when nothing matches, optional + nothing fits → empty; per-school values only (GPA '' stays empty; required
+ empty → "N/A"), no shared-label fallback; `School_alts` for tenant spellings; schools are essential on Review only where
the tenant has an education section (`has_education_section()`); per-application overrides `edu:<School>:Field|GPA|Degree`.
Tests `t_wd_logic.py`, `test_pick_by_prefs.py`, `test_degree_rank.py`, `test_bachelor_rank.py`, `test_edu_section.py`.

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
questions. Tests `test_auth_restrict.js`, `test_imm_answer.py`, `test_immigration_label.py`, `test_spons_statement.py`,
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

## 3. Review checklist (what Joey and Claude look at before Submit)
Every value matches the candidate's facts in `config/profile.json` / `config/canonical.json` / `config/wd_profile.json`: legal +
preferred name, address, e-mail, phone (Mobile, **no extension**) · Work: exactly the profile's jobs, no projects / clubs as
jobs · Education: the profile's schools, the master's as the **Master of Science** option, the bachelor's level right ·
Languages: every profile language, Fluent · work authorization as in the profile (type I) · immigration status = the
profile's plain status · every `verify.json.deepseek_answers` item matches the profile · EEO answers = the profile's (type J).

## 4. Open items
- None open from JSA-065 / 067 / 068 / 071 (fixed 2026-11-03; see types A, K, Q).
- History: the per-company problem table (#1–#144, 2026-10-28 → 11-02) is in git history before this rewrite.

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
