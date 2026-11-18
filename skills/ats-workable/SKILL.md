---
name: ats-workable
description: Apply to a Workable job (`apply.workable.com/<account>/j/<SHORTCODE>`) with the dry-run runner run_workable.py — public form schema, fill, read back, stop before "Submit application" — plus every Workable problem type seen so far.
---

# Workable applications (platform skill)

Part of the job-search agent. Read with `skills/auto-apply/SKILL.md` (general rules) and the candidate's facts in `config/`.
Code: `skills/auto-apply/runner/run_workable.py`. **After every Workable batch, update §4** (problem types, not companies;
companies go in `Seen:`).

## 1. Status (2026-11-03, JSA-122)
- **Submit path (JSA-146, 2026-11-04, Joey 「tier C投递」 / 「开始补」):** `run_workable.py --folder applications/<folder> --submit
  [--wait-captcha 10]`. Gates: every field read back, nothing unknown, folder in `approved_batches.json`, not already
  submitted. Clicks `[data-ui="apply-button"]`; confirmed by the thank-you page (`confirmed_page`) or the receipt e-mail;
  a CAPTCHA → Joey. Submitted → tracker row (sync_results) and every tab of the posting closed; dry-run tabs stay.
  Tests `scripts/test_workable_submit.py` (DeepSeek 20 + 12 for `full_address`: the single "Address" box gets the whole
  address). First live batch 11-04: an employer ×3, page-confirmed 9 / 9 each. Tracker rows were skipped because the runner
  ran with `CX_DATA=<real data/runner>` (read as test mode) → `sync_results.test_data` only skips other folders
  (`scripts/test_sync_testdata.py`, DeepSeek 10). Dry runs 11-03: Raydar 12 / 12, an employer 9 / 9, Thorlabs 20 / 20
  (Raydar / Thorlabs / Best Friend Finance are full-time roles starting now — tests only, never submitted).
- No account, no sign-in. No CAPTCHA seen on the page so far (the report expected a Greenhouse employer Turnstile at submit — the
  runner records it when the frame appears).
- Supply (2026-11-03): 34 可投, 0 A/B (Raydar 11, CWILL 4, an employer 3 …). Tests: `scripts/test_workable.py` (DeepSeek 20).

**Common segments (JSA-186 / JSA-187, 2026-11-05) — `runner/runner_common.py` (+ `presubmit.py`):** the runner does the page work only. Opening checks: already submitted · materials gate (requirements.json seeded with resume + optional letter when missing) · the upload must be the folder's **tailored** resume from `materials_manifest.json`, never a library default — a problem in a `--submit` run stops it before filling (`blocked`, queued, `stopped_at: common_gate`). Submit gate: canon on what the page holds for the irreversible fields, every field read back, zero unknowns, batch approved; only a page-work status `dry-run` can lead to a press (captcha / needs-user / closed keep their name). Closing books: one results line (old keys + `phases` seconds, `stopped_at` = common_gate / platform_page, `tenant`), one `data/runner/fields/<YYYY-MM>.jsonl` line per field, sync_results, tabs closed, unconfirmed → queue + push; the log ends 「停在：公共关卡 / 平台页面」. Tests `scripts/test_presubmit.py`, `scripts/test_runner_common.py` (DeepSeek scenarios through the real main()).

## 2. Run
**Fast path (JSA-230):** `runner/batch_apply.py prepare | approve | submit <batch.json>` runs this platform inside a (mixed) batch — never waits in place for Joey; a CAPTCHA / sign-in / unknown goes to his queue and the next job starts. ≤ 5 per batch with a sign-in platform.
**Ask first, fill once (JSA-235):** the form schema is public, so `batch_apply.py prepare` lists the questions offline (`run_workable.offline_plan` / `offline_unknowns`, no job Chrome) and the form is opened only by `submit`; a problem met only on the page → not submitted, queued.
```bash
CX_DATA=~/Projects/job-search-agent/data/runner ~/.job-agent-venv/bin/python skills/auto-apply/runner/run_workable.py \
    --url https://apply.workable.com/<account>/j/<SHORTCODE>/ [--job J01234] [--resume <pdf>] [--keep-tab]
```
Output (git-ignored): `data/runner/dryrun/workable/<account>_<SHORTCODE>/` — run_log.md, form_check.json, page.png.

## 3. Flow
1. `GET https://apply.workable.com/api/v1/jobs/<SHORTCODE>/form` → sections Personal information · Profile · Details;
   fixed ids (`firstname`, `lastname`, `email`, `phone`, `address`, `resume`, `summary`, `cover_letter`) and the
   company's `QA_<n>` questions (text, paragraph, boolean, choices). `plan_fields` skips Education / Experience groups and
   the photo.
2. Answers from `answer_rules.js` (`rules_bridge.js`); the page `…/apply/`: inputs by id (`phone` = `#input_phone`),
   booleans = radios `name=QA_<n>` value true / false behind styled `#wrapper_<radio id>` boxes, the resume file input
   `[data-ui=resume]`. Cookie banner → "Decline all".
3. Read back every field; stop before "Submit application".

## 4. Problem types
- **Confirmation from the form itself (JSA-299, all runners):** after Submit a page counts as the confirmation only when it changed (Submit button gone or URL changed, `confirm_page.judge`) and shows a success URL or a success sentence that is new since the click; "thank you for your interest" alone never counts (forms greet with it). No such page → the receipt e-mail. Workable: `page_done` (the apply button gone or the URL changed) — `confirmed_page` alone is a text check.
**A. Styled Yes / No boxes.** `Locator.check` on the hidden radio does not change it → click `#wrapper_<radio id>`,
then fall back to `check(force)`. Seen: Raydar 11-03

**B. Resume read-back.** The file input holds the file but the page shows only its (shortened) name in the upload box →
read back by the file name's first 30 characters in the page text. Seen: Raydar 11-03

**C. Open: "Will you require work authorization of any kind?"** answered Yes by the `authorized` rule — the right answer
(F-1: CPT now, sponsorship later) but through the wrong rule; it should be the sponsorship rule. To fix with a t_rules case.

**D. Prose boxes: cover letter and essays (fixed 2026-11-04, JSA-151).** Symptom: the runner left the (optional) "Cover
letter" box and the company essays empty, and a fact rule answered an essay ("How did you **find** the root cause …" →
how-heard "Online job board"). Cause: the runner only knew fact rules; it never read `cover.txt` / `open_answers.md`.
Rule: in folder mode the `cover_letter` box gets `cover.txt` (optional or not, Joey 2026-11-03); every essay box
(`essay_like`: Describe / Tell us / Share / Explain / why / how did you check …, or a label > 100 characters), required
or optional, gets its `open_answers.md` answer by field id; a short fact answer in an essay box is refused
(`guard_short_answers`); anything undrafted → `questions.json` written, status needs-user — run
`skills/auto-apply/scripts/ds_materials.py <folder>`, then rerun (the runner never drafts). `how_heard` gained
`not: root cause|investigat|problem|…`. Test: `scripts/test_workable_prose.py` (DeepSeek cases), t_rules.

**D2. Required fields are never empty (Joey 2026-11-04 「必选题不能留空」).** After the read-back every required field that is
empty **on the page** — no answer, a failed fill, a cleared box — is a problem (`required_empty`), so `--submit` never
presses Submit with one. Optional fields are still answered (essays, cover letter) but do not block. Test:
`scripts/test_workable_prose.py`.

**E. Rule wordings.** A bare "Address" (rule `address` now accepts it; "permanent legal address" does not match) and
"…require <Co> to file a petition … for employment-based status" (rule `spons_future`, F-1 → Yes). Cases in t_rules.js.
"What is your permanent legal address?" → `answers.permanent_address` (Joey 2026-11-03, rule `permanent_address`). Seen: an employer 11-03

**F. The company's own `CA_` fields.** Options come as `options: [{name: <id>, value: <text>}]` (not `choices`), radios carry the
option id as their value (`choice_map`), dropdowns are comboboxes `#input_<id>_input` (read-only ones are opened, not typed
into) with a `[role=option]` listbox, text inputs carry only `name=<id>`. A `type: number` pay box takes digits only →
25 (hourly, when the form asks "hourly or annually" → Hourly) or 52000 (Joey 2026-11-01). Rules widened for "currently, or
… in the past been employed by", "highest degree of education", "name(s) and relationship(s)", "required pay rate",
"hourly or annually" (`pay_period`). Tests `scripts/test_workable.py` (DeepSeek 20 + 16, 4 verdicts: the cases swapped
`name` / `value`), t_rules. Seen: Thorlabs 11-03

**G. Open questions for the candidate.** "Notice Period" → Available immediately and the self-assessment "Are you confident working in
fast-moving, startup-like environments …?" → Yes (Joey 2026-11-03, rules `notice_period` / `startup_fit`). An essay ("Describe a time you used AI
…") comes from `open_answers.md` (type D). Seen: Thorlabs · Best Friend Finance 11-03

**H. Date boxes (fixed 2026-11-10, JSA-234).** Symptom: "Available start date" filled with 06/14/2027 read back empty.
Cause, two layers: the runner had no fill step for `type: date` at all (`type date not handled yet`), and the box is a
react-datepicker text input masked to its placeholder (`YYYY/MM/DD` on Syntiant) — the rules' US `06/14/2027` typed there
becomes `0614/02/27` and is cleared on blur (probed live: fill or typing, US order → empty; `2027/06/14` → kept).
Rule: `to_mask` rewrites the answer in the placeholder's own token order / separator (no usable mask → `YYYY/MM/DD`),
fill, Escape + blur, then read back the same `input[name=<id>]` and compare as calendar days (`same_date`); the typed
text is kept in the field row as `typed`. Tests `scripts/test_workable_date.py` (DeepSeek 25). Seen: Syntiant 11-10
(dry run 9 / 9).
