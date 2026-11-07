---
name: ats-ashby
description: Apply to an Ashby job (jobs.ashbyhq.com/<org>/<id>) with the local runner run_form.py — plan from the public GraphQL form, fill, read back, gates, submit — plus every Ashby problem type seen so far
---

# Ashby applications (platform skill)

Part of the job-search agent. Read with `skills/auto-apply/SKILL.md` and the candidate's facts in `config/`. Code:
`skills/auto-apply/runner/` (`plan_build.py` Ashby parser, `prep_batch.py`, `run_form.py`). **After every Ashby batch,
update §4:** the kind of problem and its rule + test, not which company showed it — that goes in the type's `Seen:` line (private: the public export drops it) (Joey 2026-11-02).

## 1. Status
- Certified 2026-11-02 (JSA-050): 50 submitted, 100 % without Joey, median 15 s per form, no CAPTCHA so far.
- Auto-submit allowed inside an approved batch.

## 2. Flow
**Fast path (JSA-229 / 235):** `runner/batch_apply.py prepare | approve | submit <batch.json>` chains the steps below for a whole batch (≤ 10), same gates. **Ask first, fill once:** `prepare` collects this platform's questions offline from the public form data (plan rebuilt with today's rules + drafted open answers, materials gate offline — no job Chrome), so the form is opened only by `submit`; anything met only on the live form (a conditional question, a required field not in the plan, a failed read-back, an extra upload slot) → not submitted, `needs-user` / queued, the rest goes on; after Joey's answer `submit --only <folder>`. `prepare --dry-run` fills once first (demo, a board known for conditional questions). Every runner takes the job-Chrome lock `data/runner/chrome.lock` (JSA-236).
Same as `skills/ats-lever/SKILL.md` §2 (pick → `prep_batch.py` → unknowns → `ds_materials.py` → approve → `run_form.py`
dry-run → `--attach <org> --submit`). Each `run_form.py` run first **re-plans** (JSA-213): plan.json is rebuilt from the live
posting (saved `ashby_job.json` when unreadable) with today's rules, `config/profile.json → qa` and `answers.json`, and every
changed answer is logged (`replan: …`); `--no-replan` keeps prep's plan. The form comes from `jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting`
(application form + EEO survey); the JD from `api.ashbyhq.com/posting-api/job-board/<org>`.

## 3. Form facts
- Field containers: `div/fieldset[class*="_fieldEntry"]`, found by their label text.
- **Yes / No** (Boolean) = two buttons `button[data-option="yes|no"]`, selected = `aria-pressed="true"`. **A second click
  toggles it off** — click only when the current choice differs (caught by the read-back gate on a rerun).
- Location = autocomplete (`role=combobox`): type the city, pick the `[role=option]` that starts with it.
- Date = text box (react-datepicker): type `06/14/2027`, Escape. Multi-select = checkboxes named by their option text.
- reCAPTCHA Enterprise is invisible; only a visible challenge frame (`bframe`) goes to Joey.
- "Application limits" note: no re-applying to the same role within 90 days.

## 4. Problem types and the rules that keep them fixed

**A. Toggles and reruns.** Yes / No buttons toggle; a rerun in a filled tab can switch answers off. Click only when the pressed
button differs. A blocked run used to leave its tab open (since 2026-11-05 every run closes its tab, only a CAPTCHA stays — `runner/tab_policy.py`) and a rerun opens a new one, so an old, unsubmitted form stays and looks like
a job not applied to → rerun a blocked folder with `--attach <posting id>` (reuse its tab) and close the folder's older tabs after a
confirmed submit. `--attach` takes the first tab whose URL contains the text, so `--attach <org>` or `--attach ashby` picks
**another job's form** when two postings of one org are open — the readback then blocks on values from the other form ('on',
'') and nothing is sent. Rule: attach by the posting id (the UUID in the URL), or close the org's tabs and run without `--attach`.

**B. Dates.** Date boxes take MM/DD/YYYY. A season answer ("Summer 2027") in a date box becomes a wrong date → the rule's
`date` value is used for date boxes; a month-name answer ("December 2027") reads back as the first of that month and counts as
the same (`run_form.same`, `test_date_readback.py`). A hand-written `answers.json` date ("June 14, 2027") never read back
equal to the box's 06/14/2027 → **checked at prep** (`plan_build.date_answer`, JSA-073): a full date in any unambiguous form is
rewritten to MM/DD/YYYY, month + year is kept, a season / DD/MM / impossible date goes to `needs_user` with the reason
(`scripts/test_answer_format.py`, DeepSeek 30). **The prep-time check only reaches plans written after it** (JSA-208): a
plan.json from before JSA-073 still held "June 14, 2027", the runner typed it as is, the box showed 06/14/2027 and the
read-back blocked again on 11-05 (nothing in the date code had changed — the plan was stale). Rule: the runner checks
every date again at fill time (`run_form.date_value` = the same `date_answer`: a full date is typed as MM/DD/YYYY, a
season → `needs-user`) and the read-back compares a worded date as its MM/DD/YYYY form (`run_form.date_same`; a date
typed and shown as is — Lever text boxes — still matches). Tests: `scripts/test_ashby_submit_school.py` (DeepSeek 30 +
the stale-plan fixture `test_cases/ashby_stale_date_plan.json`) and `scripts/test_ashby_form_mock.py` (headless mock page).

**C. Option lists that are not yes/no.** A sponsorship select with ten visa statements is not a yes/no pair: "I am / I do…"
counts as Yes only in a two-option list, a longer statement list → unknown (`yesNo`, `test_yes_no_options.js`). A
checkbox's `name` can carry a trailing space ("On-Cycle Internship ") while the plan has the trimmed option text → the
runner matches checkboxes by the space-normalised name, never by an exact `[name=…]` selector (JSA-073; the 11-02 block
was this, not the list format). A multi-select in `answers.json` is checked at prep (`plan_build.multi_answer`): a list or
"A | B", every part an exact option; "A, B" whose parts are all options is read as the list; anything else → `needs_user`. A follow-up "if yes, what kind of sponsorship" is not the yes/no
sponsorship question (`canon.py --learn <org> sponsorship_future "<option>"`, or the label rules of ats-workday type I).

**D. Open questions.** Always draft "why this job / company", even when optional (Joey) — `prep_batch.open_qs` (`MOTIVE_RE`).

**E. Fields the plan does not cover.** A required structured "Education History" system field (type `EducationHistory`:
school type-ahead "Search schools…", `<path>-degree`, `<path>-major`, start / end month + year selects, `<path>-isCurrent`) is
now answered from `config/profile.json` → `education` (the newest school: UChicago, M.S. Applied Data Science, Sep 2026,
current) by `plan_build.education_entries` and filled / read back by `run_form` (`edu_same`; DeepSeek 20,
`scripts/test_education.py`; Allen Control 11-03 all checks pass). Any other required system field not in the plan still
blocks before Submit. System fields (name / e-mail / phone) can
render late on the first open (they appear ~2.5 s after load, later on a cold start) → before filling, `run_form` waits up
to 20 s for every planned `_systemfield_*` entry (`system_fields` + `wait_until`, `scripts/test_system_wait.py`, DeepSeek 24),
reloads once if they never come, then lets the form settle 1 s (JSA-073). The batch driver's one `--attach` retry stays as
the second net.
**The School box is a type-ahead that keeps only a picked option** (JSA-209): typed text reads back while the box has
focus and is dropped once it loses it, so a plan that filled School as a text box (written before JSA-056) passed the
read-back and Ashby then refused the form ("Missing entry for required field: School"). Rules: type the profile's school,
read the shown options and click the one `run_form.pick_school` names (equal after normalising — case, &, punctuation,
a leading "the" — else the single option holding the whole name as words; two candidates or none → `needs-user`, never a
guess); read back after focus has left the box, and re-read it once more just before Submit (`Form.recheck`); a plan
with `_systemfield_education_history` as anything but `education` → `needs-user` (re-plan / re-prep). Tests:
`scripts/test_ashby_submit_school.py`, `scripts/test_ashby_form_mock.py`.

**F. The audit reads the wrong question.** "Do you identify as transgender?" is not the gender question — canon gender
`label_not` = transgender / cisgender / pronoun / orientation (`test_gender_canon_label.py`, private). Widen the audit only with
DeepSeek cases.

**G. Optional EEO answers stay blank after a fact or qa answer is added.** The EEO survey questions are `demographic`
optional fields; they are filled whenever a rule, a qa entry or `answers.json` answers them — but plan.json was written at prep,
and `run_form.py` used it as is, so answers added later (Joey's qa, a hand-written `answers.json`) never reached the form, and
"What is your current age?" matched no rule. Rules: `run_form.py` re-plans every run (`replan`, `plan_changes` —
`scripts/test_plan_changes.py`); the `age_range` rule takes "(What is / What's) your (current) age" / "How old are you"
(`scripts/test_age_question.js`); still-unanswered optional questions stay `skip_optional`; the canon audit reads every
planned answer, demographic ones included.

**H. The form refuses Submit but the run says "unconfirmed".** After Submit Ashby can show a red box "Your form needs
corrections" listing the fields ("Missing entry for required field: School") — nothing was sent — while the runner only
waited for a thank-you page, logged "no confirmation seen" and recorded `unconfirmed` (which sends Joey to Gmail for a
receipt that never comes). Rule: after pressing Submit the runner reads the page's validation errors **first**, on every
poll (`run_form.submit_errors`); any error → status `failed` with the field names in `problems`, after_submit.png,
`form_check.json → after_submit_errors`, a queue line — never `unconfirmed`, no e-mail wait. Fix the field, re-run.
Tests: `scripts/test_ashby_submit_school.py` (DeepSeek 30 + the sanitised page text `test_cases/ashby_submit_errors_page.txt`),
`scripts/test_ashby_form_mock.py`.
