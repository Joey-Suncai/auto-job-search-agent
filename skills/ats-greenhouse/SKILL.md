---
name: ats-greenhouse
description: Apply to a Greenhouse job (job-boards.greenhouse.io, boards.greenhouse.io, gh_jid= links) with the local runner — plan from the public API, fill, verify, ladder, submit on gates — plus every Greenhouse problem type seen so far.
---

# Greenhouse applications (platform skill)

Part of the job-search agent. Read with `skills/auto-apply/SKILL.md` (general rules) and the candidate's facts in `config/`. Code lives in `skills/auto-apply/runner/`. **After every Greenhouse batch, update §4:** add the new problem to its type with the rule and the test that enforces it — the kind of problem and its fix, not which company showed it — that goes in the type's `Seen:` line (private: the public export drops it) (Joey 2026-11-02; company and date go in the commit message and session log).

## 1. Status

**Re-certifying (2026-11-05):** the form replay found 4 wrong answers on submitted Greenhouse forms (problem type L); Joey: 「再交10份0错答」 — certified again after 10 submits from 2026-11-05 16:23:50 with 0 wrong answers (`data/runner/recertify.json`, scorecard shows `re-cert k/10`).
- Certified (JSA-050): 55 submitted, 100 % without Joey, median 27 s per form, ~16k Claude tokens per application (vs ~200k with a browser agent).
- **Auto-submit is allowed** for Greenhouse: one "yes" per batch from Joey (`data/runner/approved_batches.json`), then the runner submits only when every gate passes.

## 2. Flow
**Fast path (JSA-229 / 235):** `runner/batch_apply.py prepare | approve | submit <batch.json>` chains the steps below for a whole batch (≤ 10), same gates. **Ask first, fill once:** `prepare` collects this platform's questions offline from the public form data (plan rebuilt with today's rules + drafted open answers, materials gate offline — no job Chrome), so the form is opened only by `submit`; anything met only on the live form (a conditional question, a required field not in the plan, a failed read-back, an extra upload slot) → not submitted, `needs-user` / queued, the rest goes on; after Joey's answer `submit --only <folder>`. `prepare --dry-run` fills once first (demo, a board known for conditional questions). Every runner takes the job-Chrome lock `data/runner/chrome.lock` (JSA-236).
1. **Pick**: `python3 skills/auto-apply/scripts/prefilter.py --track "<Track>" --level Intern --login no` (reads `data/store/jobs.jsonl` + `applications.jsonl` by default) → only 可投, no login, not already applied. Read the JD window yourself too: part-time in term, wrong year, on-site far away, external forms ("complete this Google Form") — the gate misses these.
2. **Prep** (Mac): `~/.job-agent-venv/bin/python skills/auto-apply/runner/prep_batch.py data/runner/batches/<name>.json` → folder + pin, `gh_api.json` (`boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>?questions=true`: every question with exact options, compliance/EEO, **`demographic_questions`**, education), `jd.md`, `questions.json`, `plan.json`, `requirements.json` (every file slot; a required one only Joey can supply prints `📎 needs a file from Joey` and goes into the status row's `joey_files` — type M).
3. **Unknowns**: `plan.json.needs_user` → answer from the profile / decisions-log; ask Joey only what is truly new, all at once. Write them to `<folder>/answers.json` (key = question id or label regex). New personal facts → `config/profile.json` (+ the candidate profile and decisions log).
4. **Materials**: `python3 skills/auto-apply/scripts/ds_materials.py <folder> --track <Data_Analyst|Data_Engineer|Product_Manager|AI_Agentic_Engineer>` — **never set `DS_EFFORT`** (thinking on → truncated JSON); run conversions **one at a time** (parallel LibreOffice → "soffice failed"); "page under-filled" → rerun with `--fresh`. Then **fact-check every cover letter** against the confirmed stories: invented titles, a degree the candidate does not hold, "led end to end" for team work. Fix `cover.txt` → `scripts/rebuild_letter.py <folder>`.
5. **Rebuild the plan** after answers/open answers: `CX_RULES=../scripts/answer_rules.js ~/.job-agent-venv/bin/python plan_build.py <folder> --url <embed url>` → `ready=True`.
6. **Approve**: Joey's batch yes → add the folders to `data/runner/approved_batches.json`.
7. **Run** in ONE Claude in Chrome tab of the job Chrome (`start_chrome.sh`, port 9222, only the Claude extension installed): open `https://example.com/?cx=<marker>` with Claude in Chrome, then on the Mac
   `bash skills/auto-apply/runner/run_attached.sh cx=<marker> <folder> [<folder> …]` (or `run.py <folder> --attach cx=<marker> --submit`). Stops at the first handoff.
8. **Close tabs**: `run.py` closes its own tab after a confirmed submit (a `--attach` tab goes back to the marker page; `run_attached.sh` runs `close_done_tabs.py` at the end). Joey's rule 2026-10-28.
9. **Record**: tracker `data/store/applications.jsonl` (`store.load("applications")` → add/update rows → `store.save(...)` → commit + push; the local dashboard follows within 60 s — no upload, the claude.ai dashboard is read-only until 2026-11-12), unpin folders, results in `data/runner/results.jsonl`, session log.

**L3 — a field the runner could not fix (see `handoff.json`)**
1. Look before touching: `~/.job-agent-venv/bin/python skills/auto-apply/runner/handoff_show.py "<app folder>"` — read-only; it prints the fields to fix, the intended answers, and what the live tab holds now.
2. Change **only** the fields listed in `handoff.json`. No submit, no Back, no sign-in, no CAPTCHA.
3. One actor per tab: `status.txt` must not be `running` and no `run.py` / `run_wd.py` process may be alive.
4. Hand back: `run.py "<app folder>" --resume --attach <URL fragment>` (`cx=` is the extension marker — CDP cannot use it). `verify.js` + `canon.py` decide; "I fixed it" never counts.
5. Cannot fix it, or it needs a human decision: write `applications/<folder>/l3_log.md` + `data/runner/queue.md` (the tab closes when the run ends — only a CAPTCHA tab stays, Joey 2026-11-05, `runner/tab_policy.py`).

## 3. How the runner decides (do not bypass)
- Script fill (react-select with real clicks/keys, phone country, location typed in steps, native selects, radios, checkbox groups) → **DeepSeek** for a field the script got wrong (one field's DOM + planned answer, max 3 tries) → **handoff.json** + tab kept for Claude in Chrome → `run.py <folder> --resume --attach <token> --submit` → **Joey only for CAPTCHA / email code**.
- Gates for submit: canonical audit (`canon.py`: the selected values vs his facts, evidence-backed — blocks even when verify.js passes) · batch approved · `plan.ready` · `verify.js` pass (L1 page value, L2 React state, L3 visible errors) · no field problems · no unplanned required field · no CAPTCHA. A model's own report never counts.
- Confirmation = `/confirmation` URL or thank-you text that was **not** on the page before the click (JD text often contains "Thank you for your interest").

## 4. Problem types and the rules that keep them fixed

**A. A wrong plan looks right.** `verify.js` compares the page with our own plan, so a wrong answer in the plan (degree,
veteran wording, source, "authorized as of today") shows green. Rule: the **canonical audit** (`canon.py`) reads the
selected values off the page and checks them against the candidate's facts (evidence line each); a mismatch blocks the
submit even when verify passes. Widen it only with DeepSeek cases (see ats-workday type M).

**B. Fields the plan did not know about.** Required demographic questions (`demographic_questions`), GDPR boxes from
`data_compliance` (processing / retention / demographic-data consent), a race question that appears only after the
Hispanic answer, transcript upload slots. Rules: `plan_build` reads `demographic_questions` and `gdpr_fields()` (data
processing / demographic = consent, retention = future roles; `test_gdpr_fields.py`); a second fill pass for conditional
fields; optional generic fields not on the page are skipped (`runtime.json`); a transcript slot gets the profile's official
transcript (materials gate registers it; `run.py` uploads it).

**C. Widgets that hold a different value than they show.** react-select shows text while React holds nothing; multi-selects
are a `<fieldset>` of checkboxes; phone (intl-tel-input) and textareas are uncontrolled; help text ("select all that
apply") looks like an error; a consent question that mentions "telephone calls" is not a phone field. Rules: verify L2
reads react-select state; verify reads the fieldset's checked labels and DeepSeek ticks boxes; L2 "n/a" for uncontrolled
inputs (the DOM value is what is sent); L3 ignores `…-description` text unless error-styled; `isPhone` / `is_phone` = key
phone, or a text / tel box with "phone" as a word and no options (`test_is_phone.py`).

**D. Open questions and length limits.** A why-us question phrased as "what interested you / drew you / made you apply" must
be recognised (`MOTIVE_RE`, `test_motive_re.py`); when the facts cannot answer, ds_materials writes `ASK` and the field must
stay needs-user (`load_open_answers`, `test_open_answers.py`); a limit in the label wins, else single-line text = 255
characters, else 1200 (`answer_limit`, `test_answer_limit.py`).

**E. Post-submit e-mail security codes.** The code boxes are 8 one-character inputs `security-input-0..7` (never a ZIP /
postal / promo / phone box); the right mail is one that names this company, sent after submit − 30 s, with a code not
already used (`gmail_code.choose_code`, `data/runner/used_codes.json`); any read error → logged, status unconfirmed — never a
crash without a results line. Tests `test_code_boxes.py`, `test_choose_code.py` (private).

**F. Board URLs.** Some board URLs redirect into a company iframe → use the embed URL
`job-boards.greenhouse.io/embed/job_app?for=<board>&token=<id>`; EU boards (`job-boards.eu.greenhouse.io`) use the same flow.

**G. CAPTCHA and other hand-offs.** An invisible reCAPTCHA at submit ("error processing your application") → not Applied,
queue for Joey. Extensions in the job Chrome (Simplify popups) block clicks → only Claude in Chrome is installed there.
Every stop — including a materials-gate stop — writes a `results.jsonl` line (`blocked`, mode `gate`) so the scorecard sees it.

**H. Authorization and EEO answers** follow the shared rules (ats-workday types I and J): "for any employer" wins over
sponsorship wording; anchored veteran picks; Hispanic and race answered by their own rules.

## 5. Answers that are easy to get wrong on Greenhouse
EEO, sponsorship and authorization answers come from `config/profile.json` (JSA-077) — the traps: veteran lists that start with "I identify as a veteran…" when the answer is "not a protected veteran"; a Hispanic question followed by a race list (answer each from its own rule); "authorized for any employer" differs from "authorized" for a restricted status (e.g. F-1 / CPT) · how did you hear: the real source if listed · middle initial N/A only where an initial is asked · cover letter only if the form has a slot.

**G. A required upload the plan has no file for.** `Run.unplanned_required` skipped file inputs, so a required document
(not the resume) went in empty and the runner pressed Submit. Required file inputs are now checked too (the `required` /
`aria-required` attribute, or a "*" / "required" in the field's label block); any uncovered one blocks the submit.
Tests `scripts/test_unplanned.py` (DeepSeek 16, run in a headless Chrome).

**H. Long option lists cut to 12.** A needs-user / DeepSeek question carried only its first 12 options, so the right one
(USD) was missing → `plan_build.OPT_CAP` = 200 (all options).

**I. An option list inside the question's description.** "Please select at most 2 focus areas from the list below" is a
plain textarea whose choices sit in the question's `description` HTML. The plan now keeps that description (plain text) on
the field, `prep_batch.open_qs` passes it into `questions.json`, and ds_materials sends it with the question, so the drafted
answer picks from the real list instead of guessing from the JD.

**J. A where-do-you-live question read as a willingness question.** "Are you local to NYC or the Tri-State area and able
to commute in for a Hybrid work schedule?" hit the `onsite` rule (hybrid / commute) → "Yes, local to NYC" for a candidate
who lives elsewhere. Rule `local_area` (before `onsite`, in the specific list): Yes only when the named place is the
profile's home (`answers.local_area.home`); elsewhere the "not local but willing to relocate" option, else a plain No; an
option claiming he will not / cannot relocate is never picked (asks). Same form: a "Portfolio, Video, or Website
**Password**" box got the website URL → `website` rule `not: /password/i`. Tests `test/t_rules.js`,
`scripts/test_rules_local.py` (DeepSeek 24).

**K. Start-date wordings the rule did not know.** "When would you be available to start a summer internship?" (text box)
went to needs_user. `start_date` now also reads "when would / will / could you be available / able to start", "what date
could you begin" and "start date availability" → the profile date; a general "when are you available to start?" text box
stays `avail_season` (the season). Tests `test/t_rules.js`, `scripts/test_rules_start.py` (DeepSeek 16).


**L. A rule that matches a wider question than it was written for (found after submit by the form replay, JSA-188).**
Symptom: a submitted text / select answer is truthful but answers a different question — "If yes, please provide your
visa type and expiration date" got the work authorization "CPT"; "Please provide your GPA (cumulative, not major
specific)" got the major rule's "Other". Cause: a broad pattern (`auth_kind`: *visa (type|status)*; `discipline`: *major*)
claimed the question before the specific rule. Rule: a visa type / status / classification box is the visa (`immigration_status`,
F-1; a yes/no question that names a visa classification is not one); a GPA question is never the field of study
(no band holds the GPA → ask). Guard: `scripts/learn/replay.py --check` re-answers every stored form on each rule change and
lists every answer that would differ on a submitted form. Tests: `scripts/test_replay_fixes_1105.py` (DeepSeek 28),
`node test/t_rules.js`.

**M. A required extra file slot nobody fills, and a refused submit recorded as "unconfirmed" (JSA-209).**
Symptom: after Submit the form stayed, with "This field is required." under a posting's own upload slot ("Please upload
your resume and brief research supplement — as a single PDF"); the run said `unconfirmed` and the queue said "check
Gmail". Cause: (1) the requirements probe classified the slot by its label — it mentions the resume, so it counted as the
resume and the material gate passed; the slot was in the plan, so type G's unplanned-required check did not see it either;
the runner uploads only resume / cover letter / transcript; (2) after the click the runner only looked for a confirmation,
never for the form's own validation errors. Rules: every `input_file` question goes into `requirements.json` at prep
(`prep_batch.file_requirements`; an older gh_api requirements file is re-probed), classified by
`materials_probe.slot_kind` — an extra slot is resume / cover letter / transcript only when its label names exactly that
one document with no other document or merge wording, else `other_file`; a required slot with no file on hand
(`run.missing_file_slots`) stops the submit **before filling** → `needs-user` + a queue line with the slot's label; Joey's
file goes in the folder and `answers.json` names it (`{"question_…": "<file>"}`, registered in the manifest's
`extra_files`), then rerun. After Submit, the form's validation errors (`SUBMIT_ERRORS_JS`, only those new since the
click; never on the e-mail code step) → `failed` with the field names (`submit_errors.json`; nothing was submitted), never
`unconfirmed`. Tests: `scripts/test_gh_file_slots.py` (DeepSeek 30 + the Viking fixture), `scripts/test_gh_submit_errors.py`
(DeepSeek 24, headless Chrome), `test/t_run.sh` (needs-user, refused → failed). Past folders checked 11-05: no submitted
form had a required extra slot left empty (the required ones were transcripts, all uploaded).
**N. Graduate-transcript slot (JSA-216).** Symptom: the UIUC undergraduate transcript went into an optional "Graduate
Transcript" slot (a Greenhouse employer ×2, submitted). Cause: `slot_kind` read any label with "transcript" as the transcript slot. Rule:
`materials_probe.GRAD_TRANSCRIPT` ("graduate / master's / M.S. / post-graduate … transcript", "Transcript (Graduate, if
applicable)") → kind `grad_transcript`; Joey 2026-11-05 「研究生成绩单目前还没有，那这种问题的岗位就先跳过去」: a job with such a
slot, required or optional, is skipped — prep marks the row `skipped_grad_transcript`, run.py stops with STATUS skipped and a
queue line; the undergraduate transcript is never uploaded there. Test: `scripts/test_grad_transcript.py` (DeepSeek 26).

**O. A rule answers a question that only shares a word with it (JSA-218 / JSA-219).** Symptom: found only by reading the
plans before submit (the corrections went into `answers.json`, so the scorecard looked clean): a GPA *scale* list got the
first band holding the GPA on file ("0.0 - 5.0"); `phone` matched "phonetically" (name pronunciation box got the phone number);
`authorized` answered "If you have a current work authorization/status, when does it expire?" with Yes; "authorized for
ALL employers" got Yes; "earliest you are eligible to begin full-time employment" was read as the graduation date (2027);
range options "Before / Between … and … / After" were matched by the month name; the education paragraph came from a
DeepSeek draft (B.S. / "M.S. Data Science" / high school "not provided"); "Legal First / Last Name (if different from
preferred name)" got Joey; the pronoun self-describe box got He/Him; how-heard took the first option "Radix Recruiter"; the
Degree combo showed "Masters" while the plan said "Master's Degree" → verify failed → hand-off. Rules: `gpa_scale` (options
starting at 0 → the scale on file), `phone(?!tic)` + `name_pronunciation` (none on file → ask), `visa_expiry` (status /
authorization + expire → the profile text; a yes/no "is it temporary or subject to expiration?" stays yes/no),
`any_employer` matches "all employers", `ft_start` (answers.ft_start.after), month / season ranges for `grad_date`
(`ymRange`), `education_list` / `hs_name` from `education` + `high_school` and `plan_build.FACT_FIRST` (facts beat an
open_answers.md draft), legal-name boxes go to first / last name, `pronouns` skips self-describe boxes, how-heard and
`canon.pick` never take a person (recruiter / employee / friend), `plan_build.degree_equiv` adds the level's spellings to
`accept`. Tests: `scripts/test_rules_1105g.py` (DeepSeek 30), `t_rules.js` (one case each, as seen); replay reasons logged.
