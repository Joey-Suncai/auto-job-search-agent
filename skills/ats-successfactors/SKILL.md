---
name: ats-successfactors
description: SAP SuccessFactors (career sites careers.<company>.com/job/…, career4.successfactors.com) application flow, runner notes and problem types. Read before filling a SuccessFactors form.
---

# SAP SuccessFactors applications (platform skill) — JSA-092 / JSA-153, started 2026-11-04

## 1. Status
**Fast path (JSA-230):** `runner/batch_apply.py prepare | approve | submit <batch.json>` runs this platform inside a (mixed) batch (≤ 5 per batch with a sign-in platform); a CAPTCHA / sign-in goes to Joey's queue and the next job starts. Job-Specific labels read as the placeholder: fixed (type AG, JSA-232).
- Eligibility gate reads SuccessFactors career-site pages since 2026-11-04 (reader v6, `successfactors_page`):
  40 可投 after the first run (they were all 待核实 UNREADABLE before), 14 of them tier C/D internships.
- Runner `skills/auto-apply/runner/run_successfactors.py`: an employer dry run **33/33** (2026-11-04).
      ~/.job-agent-venv/bin/python skills/auto-apply/runner/run_successfactors.py --folder applications/<folder> [--submit]
  The folder needs job.json (url = the career-site job page), jd.md, the tailored resume PDF and the cover letter PDF. Bar (Joey 2026-11-04): 10 real submissions, tier C/D internships,
  every check passing, CAPTCHAs to Joey.

**Common segments (JSA-186 / JSA-187, 2026-11-05) — `runner/runner_common.py` (+ `presubmit.py`):** the runner does the page work only. Opening checks: already submitted · materials gate (requirements.json seeded with resume + optional letter when missing) · the upload must be the folder's **tailored** resume from `materials_manifest.json`, never a library default — a problem in a `--submit` run stops it before filling (`blocked`, queued, `stopped_at: common_gate`). Submit gate: canon on what the page holds for the irreversible fields, every field read back, zero unknowns, batch approved; only a page-work status `dry-run` can lead to a press (captcha / needs-user / closed keep their name). Closing books: one results line (old keys + `phases` seconds, `stopped_at` = common_gate / platform_page, `tenant`), one `data/runner/fields/<YYYY-MM>.jsonl` line per field, sync_results, tabs closed, unconfirmed → queue + push; the log ends 「停在：公共关卡 / 平台页面」. Tests `scripts/test_presubmit.py`, `scripts/test_runner_common.py` (DeepSeek scenarios through the real main()).

## 2. What the site is (discovery, an employer 11-04 — nothing created or submitted)
- Job page: `careers.<company>.com/job/<slug>/<id>/` (RMK career site), server-rendered; JD in `itemprop="description"`.
- "Apply now »" → `/talentcommunity/apply/<id>/` → redirects to the legacy candidate site
  `https://career4.successfactors.com/careers?company=<companyId>` → **Sign In** (email + password, per company).
  Opening the apply link directly (no session from the job page) lands on the career home page — always start from
  the job page.
- "Create an account" → `career4.successfactors.com/career?company=<id>&…&login_ns=register…` with the standard
  `fbclc_` form: `fbclc_userName`, `fbclc_emailConf`, `fbclc_pwd`, `fbclc_pwdConf`, `fbclc_fName`, `fbclc_lName`,
  `fbclc_ituCode` (select, country calling code), `fbclc_phoneNumber`, `fbclc_country` (select), checkboxes
  `fbclc_emailEnabled`, `fbclc_campaignEmailEnabled` (optional marketing — leave unticked).
- Account password = Keychain (`jobagent-workday`, else `jobagent-workday-long`), typed by the script, never seen by a
  model (same rule as Workday, CLAUDE.md "Runtime prerequisites").
- Account creation (an employer 11-04, Joey's yes): fill the fbclc_ form, open "Read and accept the data privacy
  statement", press **Accept inside `#sfOverlayMgr`** (the page's other buttons are blocked by the overlay shim until
  then), then `#fbclc_createAccountButton`. No e-mail verification: the application page opens at once.
- Application page (one page, "Expand all sections"): My Documents (attach icons `[id$="_attachIcon"]`: 0 resume,
  1 cover letter, 2 additional — the icon opens a dialog in `#sfOverlayMgr` whose `input[type=file]` uploads on its own;
  the file name then shows in the section), Profile (name / e-mail / phone prefilled from the account; address, city,
  state, zip), yes/no and choice questions as **combo boxes** (`input[role=combobox]`, options `li[role=option]` in the
  list named by `aria-owns`, first option "No Selection"), compensation, source ("Other Source" + "If Other Source,
  specify here"), agreements (confidentiality / non-compete / other restriction), "I Acknowledge" (no third-party
  secrets), EEO (Gender, Ethnicity, Race — Race is reset when Ethnicity changes), Veteran, "I certify." checkbox,
  Electronic Signature (full name), then **Apply**.

## 3. Problem types
- **Confirmation from the form itself (JSA-299, all runners):** after Submit a page counts as the confirmation only when it changed (Submit button gone or URL changed, `confirm_page.judge`) and shows a success URL or a success sentence that is new since the click; "thank you for your interest" alone never counts (forms greet with it). No such page → the receipt e-mail. SuccessFactors: `sf_done` (an employer 11-04 had the same greeting on the form).
**A. Combo lists load late / stay open.** Reading or setting the next combo right after another failed (no options →
the rule fell back to Yes). Rule: `_open` waits until the list has real options and reopens once (Escape + click).

**B. Dependent EEO lists.** Race was empty after Ethnicity was set. Rule: after all answers, refill every combo whose
read-back is empty, then read back again.

**C. Resume already on the account.** With a file attached the icon is a *delete* button ("Are you sure you want to
delete this file?"); the open dialog then blocked every click and the run hung. Rule: read the attached name
(`attached_name`); same file → keep; another file → confirm delete, then upload; any leftover dialog is cancelled; the
page's default timeout is 10 s so a blocked click can never hang a run. Test: `scripts/test_successfactors.py`.

**E. A list input without role=combobox.** Race had no `role` until Ethnicity was set, so it was read as a text box and
typed into (ignored). Rule: an input whose `aria-owns` names a `_listSelect` (or with the paginated-select class) is a
combo; `combo_set` verifies the value stuck and reopens a reloading list up to 3 times. Seen: an employer 11-04.

**D. New rules from this form:** travel bands → "Up to 25%"; source list without a job-board option → "Other Source" +
"Online job board" in the follow-up box; confidentiality agreement = No (`nda`); contractor / temp / consultant of the
company = No (`contractor_here`); "I certify." box = certify. Tests: t_rules, `scripts/test_rules_sf1104.py`.

**F. Never close the cookie banner.** Closing an employer's banner ("Close") made "Apply now" do nothing (the form never
opened). Rule: leave the banner alone; click the visible "Apply now" (or open the "Apply now" dropdown and click its "Apply
Now" item — Celestica); wait up to 15 s for the form / a *visible* sign-in box (the job page hides one in its menu) / a
CAPTCHA — the URL may not change. Seen: an employer, Celestica 11-04.

**AG. The question sits in its own row; the field's label is only a placeholder (JSA-232).** an employer's template puts
each Job-Specific question ("Are you at least 18 years of age?") in a text-only table row (`<tr><th>&nbsp;</th><td>…`)
right above the field row, whose `<label>` / aria-label is "Please select one of the options"; the veteran and disability
lists get only a heading row ("PRE-OFFER INVITATION … PROTECTED VETERAN") above a long notice. Read as the label, 7
questions had no rule and the read-back failed (every row had the same label). Rule: READ also returns the text-only rows
above the field's row up to the previous field (`QROWS`); `question_label` keeps a real label and gives a placeholder one
the nearest row ≤ 300 characters (else the last question sentence of a long notice). An empty label stays empty (a combo's
search box). New wordings answered: "related to anyone that works for <Co>" = relatives (No), "I have read and agree …"
= data consent, "Do you wish to furnish this information?" = Yes (Joey 11-10, qa). Tests:
`scripts/test_sf_question_label.py`, `scripts/test_rules_sf_jsa232.py`. Seen: an employer 11-06; dry run 31/31 on 11-10.

**AH. Education rows the filler did not know (JSA-295).** an employer's Education rows label their lists "Education Type",
"School/Institution Name", "Degree Achieved", "Area of Study", with "If other, enter School / Institution Name", "If other, enter
Area of Study" and "Major (Legacy)" text boxes. "Education Type" and "School/Institution Name" were not keys the filler knew,
so the required lists stayed empty and form_check showed `options = []`. The lists do load: the rows only kept no options.
Rules (`sf_background.canon_label`, `sf_combo_edu.kind`): School Name = "School/Institution Name"; Type = "Education Type" /
"Education Level"; **Degree Achieved** is a Yes / In Progress / No list there → current degree In Progress, finished
Yes; elsewhere a degree list, which gets the finished degree only. A finished degree never takes an "… - In progress"
option (`pick_degree`, UIUC got "Bachelors Degree - In progress" in the first dry run). School not in the list + an "If
other … school" box → "Other" + the name typed (`other_school_box`); canon accepts School = Other only when that box holds
his school (`canon.other_school_entries`). **Area of Study** without his major: the list is paginated, so it is searched
for the major first. If that finds nothing and the row has an "If other, enter Area of Study" box → "Other" + "Applied Data
Science" typed there (Joey 2026-11-11). With no such box, the old fallback stays: Computer Science, then IS
(`major_choice` / `major_pick`, also in the combo education rows). form_check keeps each list's options (≤ 400). Tests:
`scripts/test_sf_edu_block_jsa295.py` (50 DeepSeek cases), `test_sf_background.py`, `test_sf_combo_edu.py`.

**AI. A checkbox labelled only by a heading word (JSA-295).** "* Acknowledgement" sits under "Applicant Statement" and the
statement "My response … certifies that I have read, understand, accept and agree with the above statements and that the
information … is complete and correct." The statement is a sibling block (`div.col-xs-12`) two levels up, not a table
row, so QROWS found nothing and the box went unanswered. Rule: outside a table, QROWS climbs up to 5 parent levels and
takes the text-only siblings before the field. It skips the field's own `<label>` and stops at a block with inputs. For a
checkbox whose label is only Acknowledgement / Statement / Attestation / Certification / Agreement, `question_label` uses
the nearest such text (≤ 1200 characters). That text is the `certify` rule (ticked). "…my electronic signature below
certifies…" is not the signature rule. Test: `scripts/test_sf_edu_block_jsa295.py`; rules `test_rules_edu_text_jsa296.py`.

**AJ. A register-form radio group with no readable question (JSA-335).** Arthrex's Create Account form
(`career2.successfactors.eu`, company=1073501P) has a profile-visibility group whose question text is not in any ancestor
the runner reads — only the options ("Any Arthrex recruiter worldwide. All recruiters within Arthrex can potentially see your
profile…" / "Only recruiters in my region…"). `radio_question` found nothing, the group went to needs-user and no account
was created. Rule (Joey 2026-11-12, fix A): such a group is answered from the option content only when exactly one of
its options matches exactly one saved pick pattern of `OPTION_ANSWER_KEYS` (now `answers.profile_visibility.pick`; Newell
11-05) — `option_answer`; set, read back, logged as `answers.profile_visibility.pick (option content)`. No match, two
options matching, or two saved answers matching → still needs-user. Test: `scripts/test_sf_option_answer.py` (25
DeepSeek cases + the real Arthrex options). Seen: Arthrex 2026-11-12.

**G. CAPTCHA at sign-in.** Celestica's sign-in page has reCAPTCHA → status captcha, push to Joey, queued; never answered.


**Text answers the box's own limits refuse (JSA-312, shared with Oracle).** A dry run's read-back does not run the page's
checks. Rule: the READ extractor reads each box's maxlength / minlength / pattern / type; `run_successfactors.limit_gate`
completes a bare address in a url box with `https://` (`field_limits.fix_url`) and turns an answer that is still too
long / too short / not a url into a question for the candidate (required) or an empty box (optional) — never typed in,
never cut. Tests: `scripts/test_field_limits.py`.

**H. RMK site with a region segment in the path (JSA-332).** `careers.arthrex.com/NorthAmerica/job/<slug>/<id>/` was
not recognised (the old rule wanted `/job/` right after the host) → "no runner in batch_apply". Rule: `runner/posting.py`
`SF_RMK` accepts at most one segment before `/job/` (two do not count; builtin.com / LinkedIn never). No `?ats=successfactors`
workaround needed. Test: `runner/test/t_posting.py`. Seen: Arthrex 2026-11-12.

## 4. Where it stands (2026-11-04 night)
- **Submitted 6** (11-04 late: + an employer Product Planning Intern, Kenworth Engineering Operations Intern — page "Your
  application has been sent. Thank you!", 56/56; see P, Q, R): SPX Product Management Intern (runner 23/23, Joey ticked the reCAPTCHA and pressed Apply; page "Your
  application has been sent" shown inside a read-only box). an employer IT Data Analytics Intern (page "Your application has been sent. Thank you!"), an employer
  Branded Fuels Business Analytics Intern (40/40, page), an employer Data Science Intern (register-and-apply page; e-mail
  "an employer – Successful Job Application"). Joey: Applied Data Science is not "business or a related field" (rule).
- Waiting on Joey: Celestica ×2 — reCAPTCHA at sign-in.
- 11-05 batch (dry runs): Newell (register form, type T), Danfoss (chat iframe over Apply, type S), an employer (background
  labels / split words, type U; question labels, type V) — fixed in code. Rerun on release-031: Newell stopped at the
  no-id radios (type W), Danfoss at the one-page register-and-apply form (type X), an employer at the short school names
  (type Y) — fixed in code 11-05, live dry runs pending after release.
- Runner work left: SPX (header "Apply Now" link — now the job's `/talentcommunity/apply/`
  link is preferred, untested), Erie (education combo rows + new rules built 11-05, type O — live dry run pending;
  "Current Job Title" needs Joey).
- Learned tonight (see problem types A–H above and below): Enter in a UI5 date box submits the form (use Tab); radiogroups
  and UI5 date pickers are outside the plain inputs (`READ_EXTRA`); register-and-apply pages need the data privacy
  statement accepted; "Back to Job Listings" alone = success page; paginated lists load by scrolling / typing; resume
  parsing creates Education rows (handled per school) and splits words ("U NIVERSITY") — fixed only for ALL-CAPS names.

**I. reCAPTCHA on the application form.** SPX's register-and-apply page has "Please confirm that you are not a robot"
above Apply; the first Apply was refused for it. Rule: before Apply, `captcha_on` → status captcha, push to Joey, the
filled tab stays open — Joey ticks the box and presses Apply himself. Seen: SPX 11-04 (also Celestica at sign-in).

**J. Icon glyphs in block labels.** "Cover Letter\ue1c4 Download document …" — private-use characters are stripped before
reading the attached file name. Seen: SPX 11-04.

**K. Plain HTML radios were never read — and the read-back still said 27/27.** SPX's questionnaire ("Will you now or in the
future require sponsorship…", `fbjq_question_N`) uses `<input type=radio>` with the question in a `<legend>`; the runner
read each option as a text box labelled "Yes" / "No". Joey caught it before Apply. Rule: plain radios are grouped by name
(`READ_EXTRA`); radios inside a `role=radiogroup` take their option text from their `<label>` and their state from
`checked`, "No Selection" is empty; **every required control on the page that is empty and was not read is a problem**
(`UNSEEN_REQUIRED`) — a form can no longer pass with a question the runner did not see. Seen: SPX 11-04.

**L. Tab cleanup must stay narrow.** A cleanup that closed every candidate-site tab closed SPX's tab after Joey had ticked
its CAPTCHA. Rule: before a run only older tabs of the same job page are closed; never another company's tab.

**M. A reCAPTCHA tick expires in about 2 minutes.** SPX was refused twice ("Please confirm that you are not a robot")
because Apply was pressed minutes after Joey's tick. Rule: when a form has a reCAPTCHA, watch
`textarea[name=g-recaptcha-response]` and press Apply the moment it has a value; on register-and-apply pages Apply is
`button#fbqa_apply` (an employer's is `span[id$=_submitBtn]`). Status 2026-11-04 night: SPX filled (23/23) and waiting for
a fresh tick — not submitted; paused by Joey.
A dry run stopped at a sign-in CAPTCHA at once, so a tick given afterwards in the left-over tab had expired before any
rerun. Rule: `captcha_wait(submit, given)` — `--wait-captcha <min>` makes a dry run wait for the tick too (sign-in,
register, above Apply); without it a dry run waits 0 min, a submit 15 (`scripts/test_sf_captcha_wait.py`, DeepSeek 12).

**N. Sign-in refused with "Invalid email address or password" (Erie 11-04).** The Keychain password did not sign in and
"Create an account" did not open (the sign-in CAPTCHA resets after a failed attempt). Either Joey has an older Erie account
with his own password or the create link needs the CAPTCHA again. Open — asked Joey.

**O. Education rows made of combo lists (School / Degree / Major / Status).** Symptom: an education section ("Education
Details") with parser-created rows whose School, Degree, Major and Status are combo lists; the School list is long,
server-searched and may lack the school ("There were no results"). The general rules answered every row the same way,
the refill pass rebound all three School read-backs to the first box by label, and typing after a failed try appended
("University oUnivUniversi…"); two rows stayed empty ("School is required"). Cause: the rows were never treated as rows;
`combo_set` typed without clearing; the refill matched by label alone. Rule (`sf_combo_edu.py`, called after
`sf_background`): rows are grouped in page order (a School box + following short education-row labels, with a Degree or
Major box); each row is matched to a `config/profile.json` education entry (empty rows take the next entry, duplicates
and left-over empty rows are removed via the row's own "Remove" / "Delete Row" control, missing entries get "Add");
School = the search result whose normalised name equals the school (never a longer name such as "Loyola University
Chicago"), else **"Other" + the school's name in the row's companion box** ("If other / specify" box, else Comments);
Degree from the level ("Masters" / "Bachelors", the full degree name first); Major = the own major or an option inside
it ("Data Science"), else **Computer Science → Information Systems → Other** (Joey 2026-10-28 「以后没有相关的major的话优先选cs或者is」);
Status Attending / Graduated by the dates; a combo is always cleared before typing; a read-back row is rebound only when
its key is gone and exactly one free field has its label (`rebind`). New answer rules from the same form: a text box that
asks yes/no and says "If NO, please indicate NO" / "enter N/A" gets that word as written (a Yes the form wants explained
→ ask); several rules that all give the same Yes/No are not ambiguous; signature of applicant = full name; "grade point
average" = the GPA rule; `grad_pursuit` (pursuing a graduate degree = Yes, from the current master's entry);
`office_software` = Yes (candidate-profile skills: Word, Excel, PowerPoint); `agent_roles` (independent-agent / sales
producer roles) = No (target roles); citizen / LPR / refugee / asylee = No (`citizen_pr`); "own/operate your own
business" = `outside_business`; the non-compete question that names "previous or current employer" is no longer the
employer-name rule; "Travelers" is not the travel question. Still open: "Current Job Title" (required, no fact on file —
asked Joey). Tests: `scripts/test_sf_combo_edu.py` (DeepSeek 24 + fixed Erie checks), `scripts/test_rules_sf_erie.py`
(DeepSeek 28, 3 code fixes, 0 verdicts), t_rules (16 new). Seen: Erie Insurance 11-04 (account created with Joey's
yes; register page reCAPTCHA ticked by Joey; the runner opens the create link directly with --new-account).
Empty education sections (Erie 11-05, the account's second visit): "Highest Level of Education Completed" and
"Education Details" showed "There are no items in this section"; the runner found no rows, filled nothing and still read
back 40/40 (both sections optional). Rule: `sections_to_open` — before the rows are read, Add is clicked once in every
empty, visible section whose heading is about education (not sf_background's "Education" / "Formal Education" /
"Education History"); the new row is then filled like a parser row ("Highest Degree" by `highest_ed`). Tests:
`scripts/test_sf_combo_edu.py` (+22 DeepSeek, `sf_empty_sections_*`).

**P. "Create an account" click does nothing; the Apply dropdown is slow.** an employer / Kenworth (career5.successfactors.eu
`paccarinc`): the job page's Apply is a dropdown button ("Apply now" → "Apply Now"), the sign-in page can take > 15 s to
arrive, and clicking "Create an account" only re-validates the sign-in form ("An email address is required") — the
register form never opens, and a later `page.fill('#fbclc_userName')` timed out. Rule: open the link's register URL
itself (`login_ns=register…`) instead of clicking; wait up to 20 s for a *visible* `#fbclc_userName`; fill only visible
boxes (`_fill`, one retry after a re-render); Apply = `click_apply` (link → visible link → dropdown) also on the
SAP-error retry; `wait_form` waits up to 30 s. an employer's register form has no phone / country fields (skipped when absent).


**Q. Background sections (Previous Employment / Formal Education) filled by the resume parser.** an employer's rows came
prefilled wrong: company "HYDE PARK", every location "Chicago", one education row "M.S. in Applied Data Science; B.A. in
Economics" with From Date 05/01/2026; Type / Result are combo lists; Division is required. The date pickers repeat their
name in every row ("Start Date"), so reading or setting them by name hit the first row only (read-back said row 2 =
row 1). Rule: `sf_background.py` — each row matched to a fact (work = `config/wd_profile.json` work, by Company; education =
`config/profile.json` education, by School Name), set from it (dates = first / last day of the month), a missing school /
employer gets a row ("Add new row"), a duplicate is deleted, a row matching nothing blocks; read back per section / row /
label. Other date pickers are keyed by name + index (`ui5date:Start Date#1`). Division has no fact → blocks until Joey
gives one. Source list naming boards but no "job board" option: the row's own board when listed (Kenworth = LinkedIn), else
"Other" (rule D). New rule `degree_progress` ("in the process of or recently completed a Bachelor's or Master's" = Yes).
Tests: `scripts/test_sf_background.py`, `scripts/test_rules_sf_degree_source.py` (DeepSeek 24 + 24). Seen: an employer 11-04.

**R. A false "submitted": the form's own intro thanked the candidate.** an employer's application page opens with "Thank you for
your interest in this position." After Apply the page said "Please correct the errors below" (salary expectations:
"Invalid number." for "Open / per internship program standard"), but the runner matched the intro as the confirmation,
wrote two tracker rows and closed the tabs. Caught from the confirmation screenshot; both rows removed, results corrected
— NOT submitted. Rule: after Apply the refusal check runs first; a success phrase counts only when it was not on the page
before Apply (`done_text`); a salary box flagged "Invalid number" gets Joey's digits-only number (52000 a year / 25 an
hour, 2026-11-01, `run_wd.salary_number`) and Apply is pressed once more; any other refusal → queued. Always open
`submitted_confirmation.png` before reporting a page-confirmed submit. Tests: `scripts/test_sf_done.py` (DeepSeek 24).

**S. A chat widget covers "Apply now".** Symptom: the click on the job's Apply link times out ("Locator.click: Timeout
10000ms exceeded" — the link resolved but never received the click). Cause: a fixed, full-size chat iframe
(`#phenomChatbotIframe`, the Phenom Career Bot) lies over the page. Rule: before Apply (and before the SAP-error retry)
`hide_chat` sets `display:none` on chat widgets only — iframes / fixed elements whose id, class, title, name or src name a
chat bot, live chat or a chat vendor (`chat_overlay`); a cookie / consent banner, a CAPTCHA, a video or a map is never
touched (type F still holds: never close the cookie banner). A click that still times out → hide once more and retry once.
Tests: `scripts/test_sf_1105.py` (DeepSeek 7 `chat_overlay` cases), `runner/test/t_sf_1105_mock.py` (headless page: the
iframe blocks the click, is hidden, the banner stays, Apply clicks). Seen: Danfoss 11-05.

**T. Register form variants.** Symptom: "Please complete all required fields and re-submit. The following fields require a
valid input: Make My Profile Visible to, Please open the data privacy agreement …"; the account was never created. Causes
and rules: (a) a required radio group "Make My Profile Visible to" (Any <Co> recruiter worldwide / … in my country/region /
Only recruiters managing jobs I apply to) — `register_radios` reads every radio group on the register form (a group with no
label of its own takes its question from the enclosing text minus the option texts, `radio_question`) and answers it from
the rules: rule `profile_visibility`, answer in `config/profile.json → answers.profile_visibility` (`{"pick": ["/^any\\b.{0,80}\\brecruiters?\\b.{0,30}\\bworldwide\\b/i"], "text": "Any recruiter worldwide"}` = Joey 2026-11-05 「Any <Company> recruiter worldwide」, every company); no answer → status needs-user, nothing picked; (b) the
privacy link may say "data privacy **agreement**" — `accept_privacy` (also used by `sign_in` now) takes statement /
agreement / policy / notice (`privacy_link`) and tries links before plain text (the validation line names the agreement
too); (c) a password rule "must not be longer than 18 characters" — `pw_limits` reads the page's min / max length,
`pick_password` takes the first Keychain item that fits (`jobagent-workday`, then `jobagent-workday-long`); none fits →
needs-user. Passwords are never printed or logged — only the item name. Sign-in still tries the regular item only (a failed
attempt resets the sign-in CAPTCHA, type N). Tests: `scripts/test_sf_1105.py` (DeepSeek 26 `sf_register_*`), the mock
page test, t_rules. Seen: an employer 11-05.

**U. Background rows never matched: box labels and split words.** Symptom: "Previous Employment row 1 / row 2: matches no
fact on file", two more empty rows added with only their dates, Education rows "set from the facts" while School / Degree /
Major / Still Attending? stayed "No Selection" — and the read-back still passed those boxes (want None, not required).
Causes: the rows' labels were "Company Name" / "Title" / "Present Employer" and "College/University" / "Degree/Certificate"
/ "Still Attending?" / "Degree/Certificate Completion Date"; `bg_plan` knew only "Company" / "Job Title" / "School Name";
and the parser's split words ("HYDE P ARK INVESTMENT S ERVICES", "FROST & S ULLIVAN") were repaired only after the
matching. Rule: `canon_label` maps a row box's label to the fact key (work: Company, Job Title, Current, Start / End Date,
Location; education: School Name, Type, Subject, Attending, Completion Date, From / End Date, Result) for matching, values
and dates; Present Employer / Still Attending? = Yes / No from `current`; a completion date only for an ended degree; a
School list = the school's own option (`sf_combo_edu.pick_school`, searched by name / short name, never "Other" here),
Degree = `pick_degree` (the full degree name first), Major = `pick_major` (Joey 2026-10-28 fallbacks); a pick pattern is
never typed into a text box. `fix_split_words` repairs employer / company / school / title boxes **before** any row is
matched (the later pass stays for boxes that re-render). Tests: `scripts/test_sf_1105.py` (DeepSeek 7 `split_fix` + 7
`canon_label` cases + fixed an employer rows: split and unsplit names both match, no row added), `test_sf_background.py`.

**V. Question labels the rules missed.** Symptom: needs-user for "What is your highest level of completed education?"
(list headed by Associate options, then "Bachelor of Architecture", "Bachelor of Arts" …), "Have you been employed at <Co>
or any of its affiliates before?", "Voluntary Self-Identification of Gender", and a veteran list labelled only "Please
Select:" under the VEVRAA paragraph. Rules: `highest_ed` also matches "highest level of completed education" and, when
several options fit its pick, takes the option equal to (or starting with) the completed degree's `degree_full` from
`config/profile.json → education` (B.A. Economics, UIUC, May 2026 → "Bachelor of Arts"; none of them → ask, never the first
Bachelor option); `prev_employed` matches "been employed at <Co> … before / previously / in the past" (answer No); `gender`
matches "self-identification of gender"; a list whose label is only a placeholder ("Please Select", "Select one",
"No Selection" …) gets its options appended to the label (`label_from_options`) so the topic rule (veteran) answers it; a
placeholder over plain Yes / No stays unknown. Answers come only from the profile's standard answers — none on file → ask.
Tests: `scripts/test_rules_sf1105.py` (DeepSeek 24, private: it states Joey's EEO answers), `scripts/test_sf_1105.py`
(7 `label_from_options`), t_rules (7 new). Seen: an employer 11-05.

**W. Register-form radios with no id and no label.** Symptom: "Make My Profile Visible to — could not set 'Any <Co>
recruiter worldwide (S…' (TimeoutError)" — the answer was known (`answers.profile_visibility`), the click never landed.
Cause: the three `input[name=fbclc_searPref]` radios (values 1 / 0 / 2) have no id and no `<label for>`; the option text
sits in an `aria-label` and in a loose `<label>` after the input's wrapper span; `radio_set` looked the input up by id
(`[id=""]`) and timed out. Rule: each plain radio's text comes from its surrounding DOM — `option_text` takes its own label,
then aria-labelledby, aria-label, the text right after the input (or after its wrapper, up to the next radio), the text of
the wrapper that holds only this radio, else the value (≤ 300 characters); `radio_selector` finds the input by id, else by
name + value (unique in the group), else by name + position; after the click the group is read again and must show the
answer (else needs-user). Same reader for the application page's plain radios (`read_extra`). Tests:
`scripts/test_sf_1105.py` (DeepSeek `sf_register_apply_*`: 5 option_text + 4 radio_selector; fixed Newell checks),
`runner/test/t_sf_1105_mock.py` (the real Newell structure, fictional company: texts read, worldwide picked by name +
value, read back). Seen: an employer 11-05 (second run).

**X. One page = account + application (register-and-apply).** Symptom: "after Apply: … sign-in box 0 · no Create an account
link" → stopped after 11 s. Cause: career2.successfactors.eu (`danfossas`) shows ONE page — CV upload ("Upload a CV"), the
`fbclc_` account fields (e-mail ×2, password ×2 with "at least 8 / not longer than 18 characters", names, country code,
phone, country, notification boxes), the questions, salary, signature, "Read and accept terms of use" and `#fbqa_apply`;
`on_application` knew this layout only from the text "Upload a Resume" (an employer). Rule: `page_kind` decides from the page's
signals — "Expand all sections" / "My Documents" = application; a visible `#fbclc_userName` plus an Apply button, an attach
icon or "Upload a Resume / CV" = **register_apply**; the account box alone = register; `#username` = sign_in — and
register_apply runs the normal flow: `fill_account` (e-mail / names / phone from config, the first Keychain password that
fits the page's length rule — type T(c) — country code "United States (+1)", job-alert and marketing boxes off), every
account box read back at the end (`account_check`: the two password boxes compared on the page, never logged or stored;
type `account` rows), the terms link accepted like the privacy statement (`accept_link`: privacy statement / agreement or
"read and accept terms of use / terms and conditions"; "agree to the Terms of use" or a footer "… Job Portal Terms" is
not one; accepted = `privacy_accepted`: "… has been accepted" on the page or the hidden `#fbclc_dpcsId` filled; "must be /
not been accepted" never counts), the CV in the first attach block (its own download link shows the file name —
`block_file`; no second block → no cover letter), then the questions; cookie-consent switches are never fields
(`COOKIE_RX`, type F). `#fbqa_apply` only with `--submit` and every check passing (the same gate as the other SF flows).
Not handled yet: an existing account on such a page ("Please sign in." link) — a second run for the same company may be
refused; "Salutation" (required) has no fact on file → needs-user. Tests: `scripts/test_sf_1105.py` (DeepSeek 4 page_kind
+ 5 accept_link + 5 privacy_accepted + 4 account_ok; fixed Danfoss checks), the mock page test (page kind, account fields
read back, the password never in rows / log, terms accepted, CV shown, Apply untouched, canon audit raises no block).

**Y. School lists with short inverted names.** Symptom: "Education (University of Chicago): College/University: want
'University of Chicago', page ''" and UIUC's box left holding "University o" (a typed search). Cause: an employer's
College/University list names schools "Chicago, U of", "Illinois, U of/ChUrb", "Illinois, U of/Chgo"; searching the full
name or the short name finds nothing; the refill pass then typed the name again. Rule (`sf_combo_edu`): `school_words`
compares distinctive words (University / Univ / U / of / the / at … dropped, punctuation split, campus hints spelled out:
ChUrb / Urb / Urbana / Champaign = Urbana-Champaign, Chgo = Chicago — so "Illinois, U of/Chgo" is never UIUC); the list is
searched by the full name, the short name, then the distinctive word (`school_query`: "Chicago", "Illinois"); `pick_school`
takes the exact name first, else the ONE option whose words equal the school's (`school_fits`); several fits, or a near fit
without its campus ("Illinois, U of" — `school_near`), → ambiguous: the box is cleared and left empty, the row says "—
Joey", and **"Other" is never picked then**; "Other" only when nothing in the list can be the school (type O). A row with
no single fit is marked `nofill` so the refill pass never types into it. Tests: `scripts/test_sf_1105.py` (DeepSeek 24
`sf_school_short_*`, 1 verdict: an exact name is never ambiguous; fixed an employer list checks), the mock page test (a
server-searched list: "University of Chicago" → no results, "Chicago" → "Chicago, U of"; "Illinois" → "Illinois, U
of/ChUrb"; a campus-less list → ambiguous, box empty), `test_sf_combo_edu.py` (no change in the Erie cases). Seen: an employer
11-05 (second run).

**Z. A source list that names its sites ("Job Board - Glassdoor / - Indeed / - Other" + "LinkedIn").** Symptom: "How did
you hear about us?" read back "Job Board - Glassdoor" for a row found on Simplify. Cause: the rule's generic `/job board/`
pick took the first "Job Board - <site>" option, and the board post-pass only ran on lists with no "job board" option at
all. Rule: a list with a per-site option (`SITE_BOARD`: "Job Board - X", "Job Board: X") goes through
`job_board.board_pick` with the config defaults (`answers.how_heard_board`: the row's own board, else LinkedIn, else
Indeed — Joey 2026-11-03); a plain "Job Board" list keeps rule D. Test: `scripts/test_sf_1105c.py` (DeepSeek 26 + the
live list). Seen: an employer 11-05 (third run).

**AA. Privacy link with a word between "privacy" and "statement".** Symptom: the account form refused "Please open the
data privacy agreement to accept the terms"; `#fbclc_dpcsId` stayed empty. Cause: the link `a#dataPrivacyId` reads
"Review and Accept Data Privacy Consent Statement" and `PRIVACY_LINK` allowed no word between. Rule: "privacy
[consent|protection] statement|agreement|policy|notice". Test: `scripts/test_sf_1105c.py`. Seen: Newell 11-05 (third run).

**AB. Zero-width characters in option text fail the canon gate.** Symptom: pre-submit block "veteran_status = 'I am not a
protected veteran​'" with the right answer. Cause: the page's option ends in U+200B and `canon.norm` collapsed only
whitespace. Rule: `canon.norm` drops zero-width space / joiners / word joiner / BOM / soft hyphen. Test:
`scripts/test_sf_1105c.py`. Seen: Danfoss 11-05 (third run).

**AC. Work-authorization and prior-employment wordings the rules missed.** Symptom: needs-user for "Are you legally
authorized or able to work in the country in which the position is located?" and "Are you, or have you been employed by
<Co> during the last 5 years (formerly known as …) or any of its companies?" — both with plain Yes / No lists. Cause:
`authorized` knew "authorized to work" but not "authorized **or able** to work"; `prev_employed` knew "previously / ever
employed by" but not "are you, or have you been employed by" nor "been employed by <Co> **during** the last N years".
Rule: `authorized` also matches "authorized or / and/or (legally) able / eligible / permitted to work" (Yes); `prev_employed`
matches "are you, or have you (ever) been employed by|with|at|for" and "have you been employed by … during / in / within /
over the last / past N months / years" (No). A resume employer (`employers_re`) is still answered Yes by `resume_employer`,
which comes first. Tests: t_rules (3 new), `scripts/test_rules_sf1105d.py` (DeepSeek 26, 1 verdict: an OPT question is the
`on_opt` rule, not "none"; private — it states the resume employers). Seen: an employer 11-05 (release-036 rerun).

**AD. "Any type of sponsorship" is not the type question.** Symptom: the radio "Will you require any type of sponsorship
now or in the future?" stopped with "no matching option for sponsorship_type". Cause: `sponsorship_type` matched "type of
sponsorship" anywhere and `spons_future` excluded the same words, so the yes/no question went to the text rule. Rule:
"**any** type of (visa) sponsorship" is excluded from both patterns (a negative look-behind); "what / which type of
sponsorship", "If yes, what type …" and "Sponsorship type" stay `sponsorship_type` (the profile's text). Replay: the two
a Greenhouse employer forms (10-31) answer Yes again — exactly what was submitted (reason recorded). Tests: t_rules (2 new),
`scripts/test_rules_sf1105d.py` (7 yes/no + 5 type-text cases). Seen: an employer 11-05.

**AE. Education rows with UI5 "From Date" boxes.** Symptom: "From Date | From Date" as unknowns — two required
`ui5date:From Date` / `ui5date:From Date#1` boxes, one per education row, never filled. Cause: the boxes are UI5 date pickers
(input inside a shadow root), placed **before** School in each row ("Row number 1: From Date, To Date, School, Degree,
Major"), so `group_rows` (plain inputs from School on) never saw them and the general pass had no fact for a bare "From
Date". Rule (`sf_combo_edu`): `ROW_DATES` finds each row's own date pickers (the row's largest box holding none of the other
rows' fields, inside the same `.rcmFormSection`; keys = READ_EXTRA's `ui5date:<name>#<n>`, so a signature "Today's Date"
elsewhere is never taken); `edu_date_want` — a start box (From / Start / Begin Date) = the first day of the entry's
`start` month, an end box (To / End Date) only when required = the last day of `end`, in the box's own `format-pattern`
(`fmt_date`: yyyy / MM / dd / M / d); typed by `date_set` with Tab, **never Enter** (Enter = Save); read back by
`date_value` (both find the picker by accessible name + index, `name`). No `start` on file → the row asks Joey ("— no start
date on file for <school> … — Joey", needs-user), nothing is typed; a box already holding a date with no fact keeps it.
Open: `config/profile.json → education` has no `start` for UIUC (candidate-profile.md says Aug 2024 – May 2026) — until
Joey's fact is added there, Newell stops at UIUC's From Date. Tests: `scripts/test_sf_1105d.py` (DeepSeek 12
`edu_date_want` cases + fixed Newell checks), `runner/test/t_sf_1105_mock.py` (shadow-DOM pickers before School: row 1
typed and read back, row 2 asks, Enter never pressed, the signature date untouched). Seen: an employer 11-05.

**AF. The cookie banner covers the final Apply.** Symptom: `--submit`: "Apply click failed (TimeoutError)", then a 300 s
wait for a receipt e-mail and the queue line "pressed the final button but no confirmation" — although nothing was
pressed. Cause: Danfoss's register-and-apply page ends with `#fbqa_apply` at the bottom; the fixed cookie banner
`div.cookiePolicy.cookiemanager` (z-index 100, bottom 192 px) lies over it, and the page cannot scroll the button any
higher. Rule: `press_apply` — before each of two tries the button is scrolled to the centre and the element on top of its
centre (its nearest fixed / sticky ancestor) is read; `cover_action`: the button itself → click; a chat widget →
`hide_chat`; a **fixed cookie / consent banner → hidden from view (`visibility:hidden`) for this one click and shown again
right after** — its Accept / Reject / Modify / Close are never pressed (type F); a CAPTCHA or anything else (a session
dialog …) → stop. The click is always Playwright's real click on the button (the page's `onclick="return
submitQuickApply()"` and its validation run) — never a JS `.click()` or a form submit. `press_result` words the outcome:
clicked → unconfirmed "pressed the final button …"; not clicked and the button still there → **blocked "Apply not
pressed … nothing was submitted"** (no e-mail wait); not clicked but the button gone → unconfirmed "the Apply click failed
… check Gmail before any retry". Tests: `scripts/test_sf_1105d.py` (DeepSeek 10 `cover_action` + 6 `press_result`, 1
verdict: a fixed element whose class says "consent" is a banner by the spec), `runner/test/t_sf_1105_mock.py` (the banner
blocks a plain click; `press_apply` clicks once, the banner is visible again with its choices untouched; a session dialog
over Apply → stop, blocked, nothing clicked). Seen: Danfoss 11-05 (release-036 `--submit` rerun).

**AG. A saved answer loses to a generic yes/no rule on a text box.** Symptom: the required textarea "This position is
available in the following locations: …; Please rank your preferred work locations in order of interest. … Relocation
assistance, if available, will be discussed …" stayed needs-user although Joey had saved an answer for it with qa_add.py.
Cause: the long label's last sentence matched `relocate` (Yes); `rules_bridge.js` threw the Yes away on a text box, and the
saved answers (config `qa`) were only tried when the rules found nothing. Rule (`answer_rules.js answerFor` +
`rules_bridge.js` guard, JSA-205): a rule's bare Yes / No on an option-less text box does not fit the box — a saved text
answer for that very question wins; when the bridge's guard rejects a rule's answer it still tries the saved answers
before "unknown". A Yes / No list keeps the rule's answer. Tests: `scripts/test_rules_1105e.py` (DeepSeek 30, rule 1),
t_rules. Seen: an employer 11-05 (fifth run).

**AH. "Job Boards-Other (specify name below)" + a specify box filled "N/A".** Symptom: "Other or Referrer (Please
specify)" read back "N/A" after the source list was answered "Job Boards-Other (specify name below)". Cause: the
other-text post-pass only followed list answers starting with "Other"; the box fell to the referral rule (no referral →
N/A). Rule (`run_successfactors.other_board`, JSA-205): after a job-board "Other" pick ("Job Boards-Other", "Job Board -
Other", "Other (online) job board") the specify box gets the board's name — the row's own board (`job_board.board_of`:
store `source`, then the URL host), else `answers.how_heard_board` (LinkedIn, then Indeed). Test:
`scripts/test_sf_other_board.py` (DeepSeek 24). Seen: an employer 11-05.

**AI. The company's own application wizard behind "Apply now".** Symptom: "Apply click failed (TimeoutError)" twice,
`a:visible` "apply now" resolved to a covered copy. Cause: careers.knorr-bremse.com (KB Signaling) draws its own
"Apply now" inside web components (`kb-job-posting` / `kb-button`, shadow DOM); it opens a Knorr-Bremse 4-step wizard
(personal information → documents → additional information → submit) in a dialog, not the SAP form; the SAP
`/talentcommunity/apply/<id>` links are in the page only at zero size and lead back to the home page. Rule
(`custom_apply_widget`, JSA-222): hidden SAP links only + a visible shadow-root Apply → stop at once (blocked, the reason
names the wizard); a wizard runner is its own row (JSA-225). Test: `scripts/test_sf_custom_apply.py` ←
`test_cases/sf_custom_apply_cases.json` (DeepSeek 16). Seen: KB Signaling 11-05.

**AG. No 300 s wait for the receipt e-mail (JSA-391).** After the final Apply with no confirmation page the run ends at once
(`unconfirmed`, `receipt_pending`, no queue line / push); `receipt_confirm` confirms it from the company e-mail later or hands it to Joey after
48 h. A failed click (button gone, nothing pressed) still goes to Joey. See ats-lever "No in-place wait". Tests: `scripts/test_async_receipt.py`.
