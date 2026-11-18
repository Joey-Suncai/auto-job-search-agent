---
name: ats-oracle
description: Apply to an Oracle Recruiting Cloud job (Oracle Cloud HCM "Candidate Experience", `<tenant>.fa.<dc>.oraclecloud.com/hcmUI/CandidateExperience/<lang>/sites/<site>/job/<id>`) with the dry-run runner run_oracle.py — e-mail step and its consent box, one-time code from Gmail, section-by-section fill and read-back, stop before Submit — plus every Oracle problem type seen so far.
---

# Oracle Recruiting Cloud applications (platform skill)

Part of the job-search agent. Read with `skills/auto-apply/SKILL.md` (general rules) and the candidate's facts in `config/`.
Code: `skills/auto-apply/runner/run_oracle.py`. **After every Oracle batch, update §4**: add each new problem to its type
with the rule and the test that enforces it — the kind of problem, not the company; companies and dates go in the type's
`Seen:` line (private: the public export drops it).

## 1. Status (2026-11-03, JSA-048)

- **Dry-run only — there is no submit code path.** The runner stops at the button that reads "Submit" (`is_final`).
- Dry runs read back to the step before Submit on 3 tenants (2026-11-03): Ricoh 43 / 43, GuideWell 29 / 29, an employer 37 / 37
  (one-time code read from Gmail). A 4th, an employer, 38 / 38 after the candidate cleared hCaptcha.
- Tests: `scripts/test_oracle.py` (DeepSeek 30, pure helpers); rule cases in `skills/auto-apply/scripts/test/t_rules.js`;
  the shared Gmail reader `scripts/test_imap_since.py` (16) + `scripts/test_html_text.py` (18).


**Submit path (JSA-147, 2026-11-04, Joey 「tier C投递」 / 「开始补」):** `run_oracle.py --folder applications/<folder> --submit
[--wait-captcha 10]` (folder = job.json with id / url / track, the tailored resume and cover letter). The final button
("Submit") is pressed only when every section read back with nothing unknown, the folder is approved and not already
submitted; confirmed by the thank-you / applied page or the receipt e-mail → tracker row, every tab of the job closed
(`run_form.posting_key` knows Oracle: `<host>/job/<id>`). Dry-run tabs stay open (Joey 11-04). Tests:
`scripts/test_already_submitted.py` (Oracle key, DeepSeek 8).
**Common segments (JSA-186 / JSA-187, 2026-11-05) — `runner/runner_common.py` (+ `presubmit.py`):** the runner does the page work only. Opening checks: already submitted · materials gate (requirements.json seeded with resume + optional letter when missing) · the upload must be the folder's **tailored** resume from `materials_manifest.json`, never a library default — a problem in a `--submit` run stops it before filling (`blocked`, queued, `stopped_at: common_gate`). Submit gate: canon on what the page holds for the irreversible fields, every field read back, zero unknowns, batch approved; only a page-work status `dry-run` can lead to a press (captcha / needs-user / closed keep their name). Closing books: one results line (old keys + `phases` seconds, `stopped_at` = common_gate / platform_page, `tenant`), one `data/runner/fields/<YYYY-MM>.jsonl` line per field, sync_results, tabs closed, unconfirmed → queue + push; the log ends 「停在：公共关卡 / 平台页面」. Tests `scripts/test_presubmit.py`, `scripts/test_runner_common.py` (DeepSeek scenarios through the real main()).

## 2. Run
**Fast path (JSA-230):** `runner/batch_apply.py prepare | approve | submit <batch.json>` runs this platform inside a (mixed) batch — never waits in place for Joey; a CAPTCHA / sign-in / unknown goes to his queue and the next job starts. ≤ 5 per batch with a sign-in platform.

```bash
CX_DATA=~/Projects/job-search-agent/data/runner ~/.job-agent-venv/bin/python skills/auto-apply/runner/run_oracle.py \
    --url <posting url> --track Data_Analyst [--out <dir>] [--wait-code 3] [--wait-captcha 10] [--consent-ok "<text>"] [--keep-tab]
```
Output (git-ignored): `data/runner/dryrun/oracle/<tenant>_<job>/` — `run_log.md`, `form_check.json` (every field: label,
kind, rule, want, page, ok), `section_<n>.png`; one non-submitted line in `data/runner/results.jsonl` (dry-run |
needs-user | code | captcha | consent | limited | closed | blocked).

## 3. Flow

1. Posting URL → `…/job/<id>/apply/email` (`apply_url`). E-mail address; a consent box on that step is judged by
   `email_consent` (privacy notice for this application → tick; anything more → stop for the candidate, §4 C).
2. Next → either the apply sections (new profile on this tenant) or a **one-time code page** (the address already has a
   profile on this tenant): the code is read from Gmail read-only (`gmail_code.find_code`) and typed.
3. Sections (Contact Information · Address · Application Questions · Supporting Documents · Diversity · Disability ·
   Agreements · E-Signature …): every field answered by `answer_rules.js` (`config/profile.json`), filled, read back;
   geography lists (Country → Postal Code → State / County / City) in `GEO_ORDER`.
4. Stop before "Submit". The tab closes after a finished dry run and stays open after a stop.

## 4. Problem types and the rules that keep them fixed
- **Confirmation from the form itself (JSA-299, all runners):** after Submit a page counts as the confirmation only when it changed (Submit button gone or URL changed, `confirm_page.judge`) and shows a success URL or a success sentence that is new since the click; "thank you for your interest" alone never counts (forms greet with it). No such page → the receipt e-mail. Oracle: `oracle_moved` — a done / applied page counts only when the URL changed, the final button went away, or the sentence is new.

**A. The one-time code mail was not found.** Three causes, all fixed in the shared reader or the runner: (1) IMAP `SINCE`
takes a bare date and Gmail compares it in its own zone — from 18:00 Chicago the UTC date is tomorrow and the fresh mail
fell before it → `gmail_code.imap_since` searches from the day before, the exact time filter follows (`test_imap_since.py`);
(2) the HTML template's `<style>` held ".containerWidth code {…}" and a CSS number was taken as the code →
`gmail_code.html_text` drops `<style>` / `<script>` first (`test_html_text.py`); (3) the mail's Date was a second before
our click → the runner waits for mails from 60 s before Next; (4) the mail does not say "code" as a word ("Please confirm
your identity using the one-time passcode: 710027") → `extract_code` also starts after "passcode", "pass code",
"one-time password" and "OTP" (whole words; `scripts/test_html_text.py`, DeepSeek 14 more cases).

**B. "Too Many Attempts. Try again in 30 minutes."** Each code request counts; several dry runs in a row lock the e-mail
on that tenant. `classify` → `limited`; the runner stops with the wait time and fills nothing. Rule: one code request per
tenant per half hour; never retry in a loop.

**C. Consent box on the e-mail step that goes beyond the application.** Some tenants make the candidate agree to calls /
texts from an autodialer, marketing, or the site's Terms of Use before Next. `email_consent` → `ask`: the runner does not
tick it and stops (`consent`) with the text; the candidate approves that wording once (`--consent-ok`). A plain privacy /
data-processing notice is ticked.
Approved wording is kept in `config/profile.json` → `consents_approved[].contains` (`consent_approved`, DeepSeek 16): such a box is
ticked on every later run (GuideWell: Joey 2026-11-03 「以后默认勾选」).

**D. hCaptcha at the e-mail step.** Some tenants protect Next with hCaptcha → `captcha`, handed to the candidate
(`--wait-captcha <min>` keeps the tab waiting); the runner never answers it.

**E. "Other" source needs a follow-up.** "How did you hear about us?" has no job-board option → `Other`, which reveals a
required "If other, please specify" (text → the profile's `how_heard` text "Online job board") or a list ("Other not
specified"). `is_other_followup` + the previous `how_heard` answer decide it.

**F. Question wordings the shared rules did not know.** "…may consist of phone interview … Are you willing to participate?"
was taken as the phone number (rule `phone` now excludes "phone interview / screen / call"); "Select the races you identify
with." (`race` accepts "races"); "Which statement best applies to you today?" with "I have never worked for <Co>…"
(rule `employee_statement`, picks only a never-worked option); "previously worked in any <Co> establishment"
(`prev_employed`). Cases in `t_rules.js`.

**G. Phone country code.** The phone row has its own country-code select; a read-back without "+1 / United States" is a
failure even when the digits match (`same` compares the last 10 digits; the code is checked separately).

**H. The e-mail step opens in phone mode.** After a run that left "Use SMS for communication" on, the tenant remembers it
and shows a phone box ("Do you want to communicate by email instead?") — the runner clicks that link first.

**I. Contract-work question.** "Are you currently on assignment, as a contractor or consultant … at any affiliated <Co>
companies?" → No (rule `on_assignment`, t_rules).

**J. Tenant-specific questions (an employer 11-03).** "Are you currently enrolled in a degree seeking college …?" hit
`enrolled` + `gpa` (the label mentions GPA) → `gpa` now excludes "are you (currently) enrolled"; the military-spouse
self-disclosure → `military_status` (None of the above apply); bond declined → `bond_declined` (No); "Career
Communicatees/Job Boards" → `job_board.board_pick` (row's board, else LinkedIn, else Indeed). Open: the "Intern Proof of
Enrollment" upload slot was not detected (no row in form_check) — `upload_enrollment` sends the profile transcript once the
slot's label is found; check the label on the next an employer run.

**K. Fields of a later section time out (30 s) while the page shows them.** The extractor numbers the visible rows
`data-ox=0…n` on every read; rows of an earlier section stay in the page (hidden) with the numbers of the earlier read, so
`[data-ox="6"]` matched two rows and the hidden one came first → click / scroll timed out on text boxes and lists of
section 2. Rule: `EXTRACT` removes every `data-ox` / `data-oxfile` before numbering. Test:
`skills/auto-apply/runner/test/t_oracle_extract.py` (headless Chrome, two sections; fails on the old extractor).
Also seen in the same run: "…please indicate the number of months (1-36) you have remaining…" was answered as the visa
kind — `auth_kind` now skips "number of months / how many" questions (unknown → the candidate).

**L. Conditional boxes: shown or hidden by an earlier answer, and boxes the shared rules over-answer.** Symptom: in one
section "If you currently hold … please indicate your current visa type" (list) and "If you indicated F-1 visa … number
of months (1-36) you have remaining" (text) timed out after 30 s; on the next run they were not on the page at all, and
"Please provide a secondary email." got the main address. Cause: these rows show only for some answers — the work-auth
answer earlier in the same pass hid them after the extract had numbered them, so the click waited for a hidden element;
a box an answer reveals ("If 'Other' please specify") is only seen by a later extract. Rules (`fill_section`): before each
fill `Oracle.shown(key)` checks the row is still visible — a hidden row is skipped (`gone`), and a row no longer on the
page at read-back is not missing (the page does not send it); up to 4 fill passes re-extract the section and fill the rows
an answer revealed; a row that appears after the last pass is read back too (required + empty → the candidate). Per box
(`box_plan`, before the rules' answer; the candidate's own `qa:` answer always wins):
- **secondary / alternate / backup e-mail** → `contact.secondary_email` in `config/profile.json` when it is set and not
  the main address; else optional → left empty, required → the candidate (never the main address typed twice);
- **"If 'Other' please specify"** → only when the nearest earlier choice question (`related_question`) was answered Other:
  a how-heard source → the profile's source text ("Online job board") or the list's single Other option; Other on any
  other question (race, visa type …) → the candidate; not Other → left empty (required → the candidate);
- **a number asked** ("number of months / years", "how many", "how long") in a text box while the rules gave words (the
  F-1 months box got "F-1") → the candidate.
Tests: `skills/auto-apply/runner/test/t_oracle_conditional.py` (headless Chrome: a "No" hides two rows, an "Other" reveals
the specify box; fails on the old filler with two 30 s timeouts) · `scripts/test_oracle.py` ← `test_cases/oracle_cond_cases.json`
(DeepSeek 28, spec `oracle_cond_spec.md`). Open: Goldman's "Are you legally authorized … or can you obtain … (e.g. F-1
OPT)?" was answered No (rule `on_opt`) on 11-05, which is what hid the visa rows — a shared-rules question, not the runner's.

**KeyError 'key' right after the uploads; the e-mail step's Next.** (JSA-220, an employer / an employer / an employer / an employer 11-05.)
- Symptom: "runner error KeyError: 'key'", 0 fields read back, on every tenant with a resume slot. Cause: the upload
  rows (resume / cover letter / transcript) carry no `key`; `related_question` (JSA-174) read `r['key']` over all rows.
  Rule: rows are looked up with `r.get('key')` (also the "revealed after the last pass" check).
- Symptom: stuck on the e-mail step, the box empty (an employer, first run). Cause: the SPA re-rendered after the address was
  typed. Rule (`email_value_ok`): the box is read before Next and typed again when it does not hold our address; one more
  Next when the page is still the e-mail step.
- Symptom: "Locator.click: Timeout 30000ms" on Next (an employer fa-ewgu). Cause: the legal-disclaimer dialog has a hidden
  footer button also labelled Next, first in the DOM. Rule (`next_button`): the pagination's visible Next, never a
  dialog footer button.
- Symptom: a radio answered (want No) but read back empty (an employer "employed by the ACE Group"). Cause: the sponsorship
  Yes revealed a box above it and the block re-rendered while the click landed. Rule (`needs_retry`): a filled row whose
  answer the next extract no longer shows (no error, not gone, not a geo list) is filled once more.
Tests: `scripts/test_oracle_1105.py` ← `test_cases/oracle_1105_cases.json` (DeepSeek 26, spec `oracle_1105_spec.md`) +
a headless page for `next_button`. After the fix all four tenants run to the questions no rule answers (needs-user).

**Existing profiles: cards to fix, the one-time code, amount boxes.** (JSA-226, an employer / an employer / an employer / an employer 11-05.)
- Symptom: dry run all read back, `--submit` refused ("education card did not save: The Degree field is required";
  an employer "You have 1 issue"). Cause: an existing profile's imported education cards need a Degree; they sit on an
  earlier section (an employer section 3, hidden once the runner moved on, so the final check never saw them) or in the
  "Work and Education History" timeline marked only by a red "!" (an employer); the Degree is a cx-select list (an employer,
  an employer) or "Education Level" (an employer), not pills. Rule (`fix_tiles`, `fix_education_cards`, `degree_option`): every
  section's visible cards that need fixing are fixed in the dry run too (row "Imported education cards"); Degree /
  Education Level from the list ("Master's Degree"), Graduated checkbox, an empty School box (a card that names no
  school is matched by level + end month — `edu_fill` fallback; split letters "U NIVERSITY OF C HICAGO" match); a card
  still needing a fix anywhere before Submit → needs-user. A refused Submit now screenshots `submit_refused.png` and
  names what the page marks (`refusal_issues`) before the tab closes.
- Symptom: "verification code step not passed" (an employer). Cause: the newest code mail in the window was an employer's from a
  minute earlier (an employer's arrived seconds later). Rule (`tenant_id`, `code_mail_ok`): only a code from this pod's
  sender (`<pod>.fa.sender`), or a company sender whose mail names the company; a refused code → "Send New Code" and
  one more try with a newer code; boxes typed key by key; Verify = the apply-flow dialog's button, never a cookie /
  terms dialog button (an employer's 30 s timeout), Enter as the fallback.
- Symptom: an employer's optional "Salary Expectations" cut to "Open / per interns". Rule (`box_fit`): words in an amount box
  (structured work-preferences salary / type number) or an answer longer than maxlength → optional: left empty,
  required: the candidate. Never cut.
Tests: `scripts/test_oracle_1106.py` ← `test_cases/oracle_1106_cases.json` (DeepSeek 30, 3 verdicts) + a headless page
for `fix_tiles` / `refusal_issues`.
- Symptom: "an imported card needs fixing and matches no profile entry: Unnamed License Fields to fix: 1" (an employer 11-06).
  Cause: an earlier run left an empty License card in the tenant profile. Rule (`blank_card`, `delete_card`): a card
  titled "Unnamed …" holds no data and is deleted (the Delete button's own click — an iCloud-password popup lay over it;
  hovers are best effort). The same tenant kept "Open / per interns" in the optional Salary Expectations box from an
  old run: words left in an amount box are emptied (rule `clear_not_number`); then Currency Code / Pay Frequency are not
  shown at all. Verify on the code step is clicked by script when a cookie bar covers it. an employer dry run 41/41.
  Tests: `oracle_blank_cases.json` (DeepSeek 12) + a headless delete under a popup, in `scripts/test_oracle_1106.py`.

**Open prose questions no rule answers (JSA-298, an employer 11-11).**
- Symptom: a required textarea such as "Would you please share some details about your future career aspirations?
  Anything you'd like the hiring review team to know …" read back empty → needs-user, although the folder's
  `open_answers.md` already held a draft. Cause: `run_oracle.py` had none of the SR / Workable flow; it never read drafts.
- Rule (`open_drafts`, `read_drafts`, `open_id`): after the shared rules, every essay box (`run_workable.essay_like`: a
  textarea with a label > 100 characters or Describe / Tell us / Share / Explain / Why / "how did you … check") whose
  answer is not ok gets its `open_answers.md` draft — by the stable id `oq_<8 hex of the cleaned label>`, else by the
  heading's label (so a draft written under another id still counts). A rule answer is never replaced. No draft →
  `questions.json` (`run_workable.write_questions`, limit = the box's maxlength, else 1500), the row stays unknown and the
  run ends needs-user: run `scripts/ds_materials.py` on the folder, then rerun — the runner never drafts. A draft longer
  than the box's maxlength → the candidate (`box_fit` too_long). The draft is typed and read back like any text box.
- Tests: `scripts/test_oracle_open.py` ← `test_cases/oracle_open_cases.json` (DeepSeek 26) + an offline mock of
  `fill_section` (no draft → questions.json; draft by id; draft under another id; ASK; a rule answer untouched).

**The page's own limits: a 51/51 read-back that Submit still refuses (JSA-312, an employer 11-11).**
- Symptom: the dry run read back 51/51; Submit then said "You have 4 issues that need to be fixed": a minor "None" (the
  box needs at least 5 characters), a 1086-character career answer (the box allows 200; `questions.json` had guessed
  1500), Link 1 / Link 2 "linkedin.com/…" / "github.com/…" ("Enter Link 1 in the format: http://example.com").
- Cause: the read-back compares only what was typed. Oracle's textareas carry no `maxlength`; the limits live in the
  page's own question data, and the page checks them only at Submit.
- Rule (`field_limits.py`, shared with Workday / SF): the runner listens to the page's REST answers
  (`recruitingCEQuestions`: Prompt + MinimumLength / MaximumLength; `recruitingCECandidateProfileBlocksMetadata`:
  MaximumLength; the name block: Length) and joins them with each box's attributes, hint text ("4 out of 50
  characters", "at least 5 characters", "format: http://example.com") and a bare link label (Link 1, Website, LinkedIn
  Profile …) — the tightest wins (`box_limits`). Before typing: a bare address in a url box gets `https://` (same
  address, `fix_url`); a rule answer that is still too long / too short / not a url → required: the candidate is asked
  (unknown), optional: left empty (`box_fit` → too_long / too_short / not_url). A draft that breaks the limit (or the
  1500 fallback) is not typed: `questions.json` gets the page's limit and min (`limit_from` says where it came from; a
  guess never replaces a known limit) with a `redraft` note, and `ds_materials` writes to that limit (min enforced
  too). After the fill and blur, any row the page marks invalid, or whose value breaks its limits, fails the section
  (`page_verdict`) — the run stops there instead of at Submit. `JSA_DUMP_REST=<dir>` saves the REST answers for a look.
- Tests: `scripts/test_field_limits.py` ← `field_limits_cases.json` (DeepSeek 26, through the Oracle / Workday / SF
  readers; 7 verdicts), `scripts/test_oracle_limits.py` ← `oracle_limits_cases.json` (DeepSeek 24, the an employer replay
  + REST shapes seen live), `scripts/test_fix_url.py` ← `fix_url_cases.json` (DeepSeek 18).

## 5. Answers that are easy to get wrong on Oracle

- Salary range list → the lowest range (shared `comp` rule); EEO → the profile's answers; "Use for communication" /
  SMS flags as the page sets them unless a rule says otherwise.
- Optional cover-letter slot → upload the folder's cover letter (Joey 2026-11-03); in a dry run with no letter, record
  the slot.

**Imported education cards with "Fields to fix" (JSA-147).** A tenant where the e-mail already has a profile imports its
old education entries; new required boxes (City, "Did you graduate?") are empty, and Submit answers "You have 2 issues
that need to be fixed before you can submit your application" — nothing is sent. Rules: `submit_refused` reads that toast
(and "Fields to fix: N") → never "waiting for the e-mail" again; `fix_education_cards` opens each such card, fills City /
graduated / Degree from config `education` (`edu_fill`: match_re, current / end month; schools' `city` added to the
profile) and presses SAVE, then Submit once more. Tests `scripts/test_oracle_cards.py` (DeepSeek 22).

**After Submit: My Profile instead of a thank-you page (JSA-147).** Ricoh's tenant went straight to `/my-profile` →
"Active job applications … Ricoh Careers 8491 … Applied on 11/04/2026"; the runner waited for a thank-you / e-mail and
logged "unconfirmed" though the application was in. Rules: `classify` → 'done' for `/my-profile` with "Applied on <date>";
`submit_final` accepts it only when `profile_lists` finds this job's number (whole number) or title. Tests
`scripts/test_oracle_cards.py` (+12 DeepSeek, 1 verdict). Seen: Ricoh 11-04

**A school / enrollment question caught by the yes/no "enrolled" rule (JSA-296).** "What university are you currently
enrolled with?" (a text box) matched `enrolled` ("currently enrolled") and came back "yes/no rule on a text box". Rule: a
wh-question is never `enrolled`. "What / which / name of the school … you are currently enrolled / attending / studying"
= the `school` rule ("University of Chicago"). "Please indicate your current enrollment status:" with Fulltime / Parttime
Schedule = `enrollment_status` → the full-time option (answers.enrollment_status pick). "What year are you currently at in
your studies:" = `college_year_current` ("(5) Masters Program"). Tests `scripts/test_rules_edu_text_jsa296.py`. Seen: an employer
11-10 (qa 216 / 220 / 221, retired 11-11; minor "Not applicable" stays a saved answer, Oracle needs ≥ 5 characters).

**A required profile list with no item (JSA-328, Dell 11-11).** Symptom: dry run all read back ("ready"), `--submit`
refused: "You need to add at least 1 Education item." Cause: the tenant shows an "Education *" block
(`.apply-flow-block--tile-profile-items`, title `apply-flow-block__title--required`) with no card, only ADD EDUCATION;
the runner fixed imported cards but never added one, and the dry run did not look at required lists. Rule (Joey
2026-11-11 「自动添加 + dry-run 检查」): on every section, a required, empty Education list gets one item per config
`education` entry — Degree button (`degree_pill`: "Masters" / "Bachelors", never Postdoctorate), Major (`major_pick`:
the major, else wd_profile Field_prefs, else "Other - Field of Study Not Listed"), School (`school_pick`: exact or the
one option holding all the school's words — "University of Illinois at Urbana-Champaign" — else "Other - School Not
Listed"), Start Date, Graduated (+ Date Acquired when graduated); saved and checked as a card. A required list still
empty (any section, also hidden ones) keeps the run from "ready" (`empty_required_lists`). Tests:
`scripts/test_oracle_add_edu.py` (DeepSeek 32 + the Dell lists); live: Dell dry run 55/55 with both cards saved.
