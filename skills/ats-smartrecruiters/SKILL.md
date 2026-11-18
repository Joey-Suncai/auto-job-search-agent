---
name: ats-smartrecruiters
description: SmartRecruiters (jobs.smartrecruiters.com / oneclick-ui) application flow, runner notes and problem types. Read before filling a SmartRecruiters form.
---

# SmartRecruiters applications (platform skill) — JSA-112 / JSA-153, started 2026-11-04

## 1. Status
Runner `skills/auto-apply/runner/run_smartrecruiters.py` (2026-11-04): first dry run 21/21 read back (an employer AI/ML
Engineer Intern, both pages). Bar (Joey 2026-11-04 「新平台的干跑改成直接提交吧」): **10 real submissions**, tier C/D
internships that pass the gate, every check passing, CAPTCHAs to Joey.

**Common segments (JSA-186 / JSA-187, 2026-11-05) — `runner/runner_common.py` (+ `presubmit.py`):** the runner does the page work only. Opening checks: already submitted · materials gate (requirements.json seeded with resume + optional letter when missing) · the upload must be the folder's **tailored** resume from `materials_manifest.json`, never a library default — a problem in a `--submit` run stops it before filling (`blocked`, queued, `stopped_at: common_gate`). Submit gate: canon on what the page holds for the irreversible fields, every field read back, zero unknowns, batch approved; only a page-work status `dry-run` can lead to a press (captcha / needs-user / closed keep their name). Closing books: one results line (old keys + `phases` seconds, `stopped_at` = common_gate / platform_page, `tenant`), one `data/runner/fields/<YYYY-MM>.jsonl` line per field, sync_results, tabs closed, unconfirmed → queue + push; the log ends 「停在：公共关卡 / 平台页面」. Tests `scripts/test_presubmit.py`, `scripts/test_runner_common.py` (DeepSeek scenarios through the real main()).

## Run
    ~/.job-agent-venv/bin/python skills/auto-apply/runner/run_smartrecruiters.py --url <posting url> [--resume <pdf>]   # dry run
    ~/.job-agent-venv/bin/python skills/auto-apply/runner/run_smartrecruiters.py --folder applications/<folder> [--submit]
A folder needs job.json (id / url), jd.md, the tailored resume PDF and cover.txt (`ds_materials.py` — the
"Message to the Hiring Team" box is a cover-letter slot and is always filled, Joey 2026-11-03). Essays → open_answers.md
by question id (the runner writes questions.json and stops when a draft is missing; it never drafts).

## 2. What the form is
**Fast path (JSA-230):** `runner/batch_apply.py prepare | approve | submit <batch.json>` runs this platform inside a (mixed) batch — never waits in place for Joey; a CAPTCHA / sign-in / unknown goes to his queue and the next job starts. ≤ 5 per batch with a sign-in platform.
- Posting API (public, no key): `https://api.smartrecruiters.com/v1/companies/<Company>/postings/<id>` → `uuid`, `applyUrl`.
- Apply page: `https://jobs.smartrecruiters.com/oneclick-ui/company/<Company>/publication/<uuid>?dcr_ci=<Company>` —
  `<Company>` exactly as the API writes it (`company.identifier`), never as the store URL spells it (problem type P).
- **DataDome** bot protection: the page's own XHRs work in the job Chrome; the same URLs from curl / urllib → 403. Never
  try to get past it outside the browser; read the form in the page.
- Page config: `GET /oneclick-ui/api/company/<companyId>/publication/<uuid>/config` (read from the page's response) →
  `fieldSets`: firstAndLastName, email, placeOfResidence (CITY), phoneNumber, experience, education, socialProfiles,
  resume, messageToHiringManager — each `{required, visible}`.
- Web components (`spl-*`) with **open shadow roots**: Playwright CSS pierces them. The id sits on the host *and* the inner
  input → target the inner element: `input#first-name-input`, `input#last-name-input`, `input#email-input`,
  `input#confirm-email-input`, `input#linkedin-input`, `input#website-input`, `input[type=tel]` (country code defaults
  to +1), `textarea#hiring-manager-message-input`, resume = `input#spl-dropzone-file-input-1` (the other dropzone is the
  Easy Apply parser — never use it).
- City: autocomplete — type "Chicago", then click `spl-select-option` with text `<City>, <ST>, US`; a typed value alone
  fails validation ("Please provide your place of residence").
- Buttons are `spl-button` (Next / Back / Submit), not `button`.
- Page 2 "Preliminary questions": company screening questions (radio Yes/No, autocomplete selects for state / gender /
  race / citizenship, text boxes for postal code), export-compliance block, diversity block, veteran radio, privacy
  checkbox, then **Submit**. `inner_text('body')` does not show them (shadow DOM) — read through the components.

## 3. Problem types
- **A degree / school question typed into a text box (JSA-296, all platforms).** The "Other (free text)" box under a
  BA / BS / Ph.D / Other list asks the parent question again as text. The degree rule could only pick from options, so the
  required box stayed empty. Rule (answer_rules `degree_full`): a typed "which degree are you pursuing / please confirm your
  current degree" = "Master of Science in Applied Data Science, University of Chicago", built from the current education
  entry. "Can / could you (please) confirm …" is a request, not a yes/no question (`REQ_Q`). Tests
  `scripts/test_rules_edu_text_jsa296.py`. Seen: Bosch 11-10 (qa 222, retired 11-11).
- **Confirmation from the form itself (JSA-299, all runners):** after Submit a page counts as the confirmation only when it changed (Submit button gone or URL changed, `confirm_page.judge`) and shows a success URL or a success sentence that is new since the click; "thank you for your interest" alone never counts (forms greet with it). No such page → the receipt e-mail. SmartRecruiters (Bosch 11-11: "CONFIRMED by page" while the form was still spinning; the form says "Again, thank you for your interest…"): `sr_snap` + `W.page_done`.
**A. Autocomplete options are deep in the shadow root.** `locator(...).filter(has_text=…)` finds the `spl-select-option`
elements but never matches their text, so the click times out. Rule: find the option by its whole normalised text in JS
(`OPTS_JS`), scroll it into view and click its centre with the mouse; type the answer first when the list is long. Test:
live dry run (21/21). Seen: an employer 11-04.

**B. "If you selected Other …, please enter it below."** An optional follow-up box got the state name from the `state`
rule. Rule: an optional question matching `IF_OTHER` stays empty. Test: `scripts/test_smartrecruiters.py`. Seen: an employer 11-04.

**C. "Available to work during the work period specified in the posting?"** No rule → unknown. Rule `work_period` = Yes
(batches hold only roles whose JD period is the target summer). Test: t_rules. Seen: an employer 11-04.

**D. Page-2 labels are not in `inner_text('body')`.** Read the `sr-question-field-<type>` wrappers through the shadow
roots (`READ_Q`); the privacy checkbox sits outside them (`READ_CONSENT`). Seen: an employer 11-04.

**E. Stale tabs.** (Superseded 2026-11-05: every run now closes its tab when it ends, dry runs included — only a parked CAPTCHA stays; `runner/tab_policy.py`, Joey 「以后干跑结束也要把标签关掉」.) Before that every dry run left its tab open; when probing a page
by hand, pick the tab that has `sr-screening-questions-form`, not the first `oneclick-ui` tab.

**F. The message box refuses ';'.** Symptom: Next did nothing; the page said "This field cannot contain following
characters: ;". Rule: `message_text()` turns every ';' into ',' before filling the box. Test: `scripts/test_sr_message.py`.

**G. Buttons are `spl-button` with their text inside the component.** `filter(has_text=…)` timed out on Submit. Rule:
`click_button(page, '^submit$')` finds the visible spl-button by its text in JS and clicks it with the mouse; any error in
the submit step → unconfirmed + queue, never a crash. Seen: an employer 11-04 (nothing was submitted).

**H. A page-2 that never opened was reported clean.** Rule: after Next the runner waits for `sr-screening-questions-form`;
missing → problem "page 2 did not open" with the page's error text. Seen: an employer 11-04.

**I. An answer opens a new required question (Submit refused).** Symptom: Submit clicked, no thank-you, no e-mail; the page
showed "This field is required." on "Do you hold Citizenship or Permanent Residency status from any of the following
countries…?", which appeared only after the export-control answer. Rule: page 2 is read again after each round of answers
until nothing new appears (≤ 4 rounds); after Submit, field errors on the page (`FIELD_ERRORS`) → status refused / blocked
at once (nothing went in), not a 180 s wait. Rule `citizenship_country` answers the country list from
config/profile.json → citizenship_country (the candidate's country of citizenship). Tests: t_rules, `scripts/test_sr_followup.py`.

**J. Optional follow-ups stay empty.** "If your selection is not your most recent Citizenship…", "If yes, …", "If you
selected Other …" (optional) → empty, never drafted (`IF_OTHER`; the Workable short-answer guard skips answers marked
`leave`). Test: `scripts/test_sr_followup.py`. Seen: an employer 11-04.

**K. Expired postings.** The posting API said active but the form opened `…/expired` ("该招聘广告已过期"). Rule: `/expired`
in the URL or an expired sentence → status closed. Seen: Master Lock 11-04 (an employer 11-04 was type P, not expired).

**L. One-page forms.** No screening questions → page 1 ends with Submit, no Next. Rule: no Next but a Submit → skip page 2.

**M. Required Education entry.** "Please provide at least one education entry" blocked Next. Rule: when page 1 has
"Add education entry" and none is saved, add the current school from config education (institution and school location
from the autocomplete, major, degree, From month via the month picker — `pick_month`, "I currently attend"), then Save;
read back from the saved entry. Seen: an employer, Spring Venture 11-04.

**N. Company-specific question sets** (Bosch / an employer / Spring Venture 11-04): degree lists without a master's option
→ Other; class standing → Other; GPA bands → the band holding the profile GPA; "(MM/YY)" dates → 12/27, internship start / end
06/27 - 09/27; hours per week → 40; attestation boxes (certify / "information … is true"); enrollment status → master's;
"employed by <X> in the last N months" → No (never for a resume employer); a referral-name box is never his own name;
"file a petition … employment-based visa" = future sponsorship = Yes; an employee ID for a company he never worked at →
N/A (for a resume employer → Joey). Tests: `scripts/test_rules_batch1104.py` (31 DeepSeek cases), t_rules.

**O. EEO block and "Other (free text)" follow-ups.** `sr-question-field-eeo` holds two lists (`<id>_gender`,
`<id>_ethnicity`) → two select questions. Picking "Other" in a list opens a required "Other (free text)" box → filled
with the same fact as text (degree → "Master's Degree", class standing → "5th year (first year of the M.S. …)"); answers
are kept across re-read rounds. Test: `scripts/test_sr_eeo.py`. Seen: Bosch 11-04.

**P. Company id in the wrong case → a live posting opens `/expired`.** Symptom: status closed ("posting closed / form
unavailable") for a posting the API calls active. Cause: the store URL spells the company `m3usa` / `winsupply1`; the posting
API accepts any case, the oneclick-ui form does not (`an employer`, `Winsupply1` open the live form). Rule: `apply_url` always asks
the posting API (by numeric id or uuid) and builds the form URL from `company.identifier` (else the first path part of
`applyUrl` / `postingUrl`, else the store's spelling); a oneclick-ui URL whose lookup fails keeps its own company and uuid.
Test: `scripts/test_sr_1105.py` (DeepSeek 10 form_url cases). Seen: an employer 11-04 / 11-05, an employer 11-05.

**Q. "For individuals under 18 … please provide your date of birth. Otherwise, you may skip this question."** Symptom:
rule `age18` typed "No" into the optional text box. Rule `dob_minor` (date of birth / birth date / DOB + minors / under
16–21): a free-text or date box stays empty (`leave`, not unknown — he is over 18); the same question with Yes / No
options → No. Tests: t_rules, `scripts/test_sr_1105.py`. Seen: an employer 11-05.

**R. The truthfulness certification as a Yes/No radio.** "I certify that all information provided in this form and in my
resume is truthful, complete, and accurate." is a required radio here, not a checkbox, and the `certify` pattern
(`certify … {0,60} true`) missed the long wording → unknown. Rule: `certify` also matches "certify that (all) (the)
information / answers / statements … true / truthful / accurate / correct / complete" → Yes (the certify checkbox's
answer); "certify whether you are a previous employee" stays `prev_employed`. Tests: t_rules, `scripts/test_sr_1105.py`.

**S. "Are you eligible to work … WITHOUT (required) sponsorship now or in the future?"** Symptom: answered Yes by
`spons_future` (the question asks the opposite). Rule: a sponsorship question whose own sentence asks about working
*without* sponsorship (and does not first ask whether he requires it) gets the profile's sponsorship answer flipped →
No (future) / Yes (now only). Tests: t_rules, `scripts/test_sr_1105.py`. Seen: an employer 11-05 (dry run, nothing submitted).

**T. "If not, type N/A" read as a visa-type question.** Symptom: "Did someone from our company suggest you apply? If so,
please provide their name – if not type N/A." got "CPT" (`auth_kind` matched "if so … type"). Rule: `auth_kind` never
takes a label where "type" is the verb ("if not type", "type N/A") — such a box is unknown → Joey (or his qa answer).
Tests: t_rules, `scripts/test_sr_1105.py`. Seen: an employer 11-05 (dry run).

**U. Yes/No radios no rule covers** ("Are you able to independently perform the essential functions …?", "Are you
currently attending a college or university?") stay unknown → needs-user; Joey's answers go into the qa table
(`qa_add.py`), never an invented rule. Seen: an employer 11-05.

**V. A collapsed Education section: "Add" below the fold.** Symptom: "Locator.click: Timeout 30000ms … spl-autocomplete
[label=Institution] input", 0 fields read back. Cause: the "Add education entry" button's coordinates were read without
scrolling; it sat below the window (y 944 of 900), so the mouse click landed nowhere and the entry form never opened.
Rule (`open_entry`, JSA-221): the button is scrolled to the middle first (`ARIA_SCROLL_JS`), then clicked; the
Institution box is awaited 6 s, one more click if it did not open, then the entry is reported not saved (never a 30 s
hang). Save is clicked the same way. Test: `scripts/test_sr_open_entry.py` ← `test_cases/sr_open_entry_cases.json`
(DeepSeek 12; headless page, button in a shadow root). Seen: an employer 11-05.

**W. Required work experience blocks Next; month pickers never read as set (JSA-233).** Symptom: "page 2 (Preliminary
questions) did not open after Next" with no reason, and "education: From month not set" on every run. Causes: (1) the
form config (`…/publication/<uuid>/config` → `fieldSets.experience.required: true`, SyngentaGroup) requires at least one
work experience entry — the page said "Please provide at least one work experience entry" in a `validation-summary-entry`
list the old error reader (class *error* only) did not see; the runner only ever added Education. (2) The From / To month
picker box holds an ISO date (`2026-09-01`), the runner compared it with `09/2026`. Rule (Joey 2026-11-10, option
「必填时自动填两段经历」): the runner reads the config from the page's own response; **only when Experience is required**
it adds every `config/wd_profile.json → work` entry (the same entries Workday uses: Title / Company / Office location
autocompletes — click the option that is the typed text, the location option "<city>, …" via `location_option`, never
"Cannot find your city?" — Description, From / To months, Save), oldest first so the most recent ends on top; each entry
is read back from the saved list, a failed entry is cancelled, never saved half-filled. If the config was not read and
the page names the missing experience after Next, the entries are added and Next pressed once more. Month pickers:
`pick_month` steps the year until the cell "<Month> 1, <year>" exists and checks the box with `picker_ym`. "Page 2 did not
open" now quotes the page's validation messages (`validation_text`). Tests: `scripts/test_sr_experience.py` ←
`test_cases/sr_experience_cases.json` (DeepSeek 30); live dry run SyngentaGroup Agronomic Research Intern 24/24 (the
Syngenta Data Scientist Intern posting itself expired before the fix). Seen: Syngenta 11-06.

**X. Required employment declarations no rule covers (JSA-326).** Symptom: three required single-option checkboxes on page 2
stayed unticked (`unknown`): the release of past-employment information ("I hereby grant permission to any person, firm or
corporation to release …"), the at-will understanding ("… nothing contained in the application … employment contract …
at-will basis") and the I-9 notice ("all persons hired will be required to verify identity and eligibility to work …").
They are acknowledgements of the hiring process, not facts about the user; Joey agreed to tick them (JSA-326). Rule:
`run_smartrecruiters.declaration_rule` / `apply_declarations` answer exactly these three kinds (single option, required,
not negated) after the rules ran; everything else stays with the rules. Tests: `scripts/test_sr_declaration.py` ←
`test_cases/sr_declaration_cases.json` (DeepSeek 26). Not covered: the "How did you hear … select all that apply" list
(`spl-autocomplete#q4` was not found, 30 s timeout) — separate row.

**Y. "Select all that apply" lists are `spl-multiselect-autocomplete` (JSA-387).** Symptom: "How did you hear about this position?"
timed out (`spl-autocomplete#q4 input` not found) and `source_channel` read back empty. The control is its own component: an
empty `input#question_<uuid>` (role combobox), a menu of `spl-select-option`, and each pick shown as a tag in an
`spl-tags-list`, all inside its shadow root; `READ_Q` did not list it among the controls, so the question got the fallback
key `q<idx>`. Rules: `READ_Q` names `spl-multiselect-autocomplete` as a control, the autocomplete locators and `OPTS_JS` accept
both tags (`AC`), the read-back is the tags (`TAGS_JS`) and matches when the wanted option is one whole tag
(`multi_has`), and a control that cannot be found keeps its wrapper's markup in the row (`dom`). Tests:
`scripts/test_sr_multiselect.py` (DeepSeek 20 + a headless mock of the component); live dry run Arista 11-17: 26/27, the
only open question is the sponsorship radio (the user answers each one).
