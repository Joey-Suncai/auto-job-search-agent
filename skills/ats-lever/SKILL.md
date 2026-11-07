---
name: ats-lever
description: Apply to a Lever job (jobs.lever.co/<site>/<id>) with the local runner run_form.py — plan from the apply page, fill, read back, gates, hCaptcha hand-off in Edge, submit — plus every Lever problem type seen so far
---

# Lever applications (platform skill)

Part of the job-search agent. Read with `skills/auto-apply/SKILL.md` (general rules) and the candidate's facts in `config/`.
Code: `skills/auto-apply/runner/` (`plan_build.py` Lever parser, `prep_batch.py`, `run_form.py`). **After every Lever batch,
update §4:** the kind of problem and its rule + test, not which company showed it — that goes in the type's `Seen:` line (private: the public export drops it) (Joey 2026-11-02).

## 1. Status
- Bar = 30 submitted (Joey 2026-11-02; 23 so far). **The last step is manual by design**: hCaptcha stops most runner
  submits, so the form opens in Joey's Edge, the extension fills it, and Joey clicks Submit (§2.6).
- **Auto-submit by default** inside an approved batch (Joey 2026-10-31: 「lever改为自动提交」): every Lever folder runs with
  `--submit`. A challenge after Submit often still submits: the runner waits for the company receipt e-mail and records it.

## 2. Flow
**Fast path (JSA-229 / 235):** `runner/batch_apply.py prepare | approve | submit <batch.json>` chains the steps below for a whole batch (≤ 10), same gates. **Ask first, fill once:** `prepare` collects this platform's questions offline from the public form data (plan rebuilt with today's rules + drafted open answers, materials gate offline — no job Chrome), so the form is opened only by `submit`; anything met only on the live form (a conditional question, a required field not in the plan, a failed read-back, an extra upload slot) → not submitted, `needs-user` / queued, the rest goes on; after Joey's answer `submit --only <folder>`. `prepare --dry-run` fills once first (demo, a board known for conditional questions). Every runner takes the job-Chrome lock `data/runner/chrome.lock` (JSA-236).
1. **Pick**: `python3 skills/auto-apply/scripts/prefilter.py --level Intern` (uses `ats_url` for Built In rows); read the
   live JD (`eligibility_fetch.load(url)`) and run `eligibility_rules.js` on it. Lever demo boards exist ("Lever is looking for…") — not real jobs.
2. **Prep**: batch JSON `{"jobs":[{"id","company","title","url","ats_url","track"}]}` →
   `CX_RULES=../scripts/answer_rules.js ~/.job-agent-venv/bin/python skills/auto-apply/runner/prep_batch.py <batch>` →
   folder, `lever_job.json` (api.lever.co/v0/postings), `jd.md`, `job.json`, `plan.json` (url = `/apply`).
3. **Unknowns** (`plan.json.needs_user`): profile / decisions-log first; ask Joey only what is new, then add a rule to
   `scripts/answer_rules.js` + `scripts/test/t_rules.js` (`build_bundle.py`) and re-run prep.
4. **Materials**: `ds_materials.py <folder> --track <track>`. A transcript upload gets the profile's official transcript
   (`config/profile.json` → `transcript`, registered in the manifest by `materials_gate.register_transcript`).
5. **Approve** the folders in `approved_batches.json`, then dry-run: `~/.job-agent-venv/bin/python run_form.py <folder>`;
   look at `filled_check.png`; submit: `run_form.py <folder> --attach <site> --submit` (batch default: no `--wait-captcha`,
   so a challenge goes straight to the hand-off sheet; `--wait-captcha 20` only while Joey is at the Mac).
6. **Hand-off in Joey's Edge (JSA-072, 2026-11-02; was "his Chrome", JSA-058)** — the job Chrome is the only Chrome on this Mac
   and it has the debugging port, so hCaptcha rejects even Joey's own clicks there ("There was an error verifying your
   application"). So a Lever submit that hCaptcha stops (status `unconfirmed`, no problems,
   `run_form.handoff_cmd`) is opened in **Microsoft Edge** (`open -a`; env `JSA_HANDOFF_BROWSER`, `--no-handoff` to skip) and
   the job-Chrome tab is closed. In Edge the `lever_fill` extension (loaded once from `skills/auto-apply/lever_fill/extension`)
   fills the page on load from the server (LaunchAgent `com.jobagent.leverfill`, 127.0.0.1:8765); Joey looks, clicks Submit,
   solves a challenge if one appears; the thanks page records it. Never make the job Chrome look like a normal browser to
   hCaptcha (evasion, rule 7). Tests: `scripts/test_handoff_cmd.py` (DeepSeek 24).
7. **Hand-off sheet (JSA-042, 2026-10-31)**: whenever every check passed but nothing was confirmed (dry-run, CAPTCHA,
   "error verifying"), `run_form.py` writes `<folder>/manual_submit.md` (`runner/manual_submit.py`): every answer in form
   order, long answers in copy blocks, full file paths, the fields to leave blank. A failed check removes an old sheet.
   Joey submits in his own Chrome, then records it from the main folder:
   `python3 scripts/store/sync_results.py --manual "<folder>" [--note "…"]` → `results.jsonl` line (`by: joey`),
   Applied tracker row, queue ticked, `application_record.md` line; a second run adds nothing. Regenerate a sheet by
   hand: `~/.job-agent-venv/bin/python skills/auto-apply/runner/manual_submit.py <folder>`.

## 3. Form facts
- Questions: standard inputs (`name`, `email`, `phone`, `org`, `location`, `urls[…]`, `resume`) + custom **cards**
  (`cards[<uuid>][fieldN]`, template JSON in the hidden `[baseTemplate]` input: text, textarea, multiple-choice = radio,
  multiple-select = checkboxes, dropdown / university = `<select>`, **file-upload** = file) + optional `eeo[…]` selects +
  `consent[marketing]` (its own sentence is the label; "contact me about future job opportunities" = Yes).
- Location: type the city, pick the suggestion (fallback: the typed text). Cookie notice covers Submit → Decline/Dismiss.
- **hCaptcha**: invisible until Submit; a challenge then appears → push + wait (`--wait-captcha`). The challenge expires
  after a few minutes; if it did, rerun the submit command while Joey is at the Mac.

## 4. Problem types and the rules that keep them fixed

**A. hCaptcha after Submit.** Invisible until Submit; in the job Chrome (CDP-driven) Lever often answers "There was an error
verifying your application" — even after a person solved the challenge there — and the form resets. That banner means
*unknown*, not *failed*: many such applications were received. Rules: the runner detects the banner (`VERIFY_ERR`), stops as
unconfirmed and never loops retries; it waits up to `--mail-wait` 180 s for the company's receipt e-mail
(`gmail_code.choose_mail`, read-only; zone-less mail dates read as UTC) → `submitted`, `confirmed_by: email`; no page and no
mail → the Edge hand-off (§2.6) or `manual_submit.md`. Before any retry check Gmail — a blind retry can send a duplicate.
Never make the job Chrome look like a normal browser to hCaptcha (rule 7). Tests `test_handoff_cmd.py`, `test_choose_mail_tz.py`
(`test_choose_mail.py` private). A receipt from a differently named legal entity is not matched → stays with Joey.

**B. Card fields.** Custom cards (`cards[<uuid>][fieldN]`) include `file-upload` (= a file field, e.g. a transcript), radios,
checkboxes and `<select>`s; an `answers.json` key that is a card field key must match exactly and never be read as a regex
(`plan_build.override_for`, `test_override_for.py`).

**C. Questions that look like another question.** An office multi-select "check all that apply (… visa sponsorship …)" is the
office pick (`office_all`), not sponsorship; "what school are you attending for your major" is the school question, not the
field of study; "include your completed degree program and school name" is free text, not the degree level. Rules + canon
`label_not` with DeepSeek cases (`test_canon_education.py`).

**D. Conditional EEO fields.** The CC-305 disability form makes Name + Date required once disability status is answered →
`lever_fields` adds `eeo[disabilitySignature]` / `eeo[disabilitySignatureDate]`, rule `signature_date` = today.

**E. Already applied under another link.** An aggregator row can resolve to a Lever posting already in the tracker →
`prefilter.posting_key` skips any row whose url / ats_url is a posting already applied to.

**F. Optional questions with a fact were left blank.** An optional question is filled whenever a rule knows the fact —
but the rule wording missed common phrasings ("What is your area of study?", "What degree are you pursuing?", "When do you
expect to graduate?", "Nick Name"), so the field was skipped. Rules widened in `answer_rules.js` (discipline / degree /
grad_date / preferred_name; "graduate from your course of study" stays the grad date, "degree and area of study" stays
unknown) with cases in `t_rules.js` and `scripts/test_optional_facts.js` (DeepSeek 31). An optional question with no fact
stays blank — never guessed (JSA-075).

**G. Demographic survey after the EEO block.** "What is your location?" is a `<select class="candidate-location">` with
**no name** (values = country codes); choosing a country reveals the survey section for it (`countrySurvey_<code>` or
`countrySurvey_all-candidate-locations`, questions `surveysResponses[<id>][responses][fieldN]` from a template JSON).
`plan_build.lever_survey` reads the select (key `candidate-location`, label "Country of residence (…)" → the country
fact) and every section; `build` keeps only the sections the chosen country shows. The runner and the `lever_fill`
extension address the select by CSS (`select.candidate-location`), choose it first, then the revealed questions. The age range comes from `answers.age_range`
(profile age + `as_of`, `ageBand` picks the band that contains it; Joey 2026-11-03). A survey
question with no fact is left blank and listed in `needs_user` (`survey: true`, not required, never sent to
DeepSeek drafting) for Joey. Tests `scripts/test_lever_survey.py` (DeepSeek 16 + a page fixture) (JSA-075).

**H. Runner submits recorded as Joey's.** The `lever_fill` extension is also loaded in the job Chrome, so on the runner's
own /thanks page it reported "submitted by Joey" (`by: joey`) before the runner wrote its line. Rule: `run_form.py` keeps
`<folder>/runner_active.json` (pid + time) for the whole Lever run and deletes it right after its own results line (which
now says `by: runner`) — before any Edge hand-off. While that mark is live (pid running, < 2 h) the server neither serves
the fill nor records /thanks (`server.runner_owns`, `scripts/test_runner_owns.py`, DeepSeek 24 + round trip) (JSA-083).

**I. URL boxes with other names, optional questions left blank.** The parser knew five fixed `urls[…]` names, so a Lever employer's
required `urls[LinkedIn Profile]` and ShopBack's `urls[Github / Portfolio]` were never planned — and the dry-run said
"all checks pass" because a box that is not planned is not checked. Optional questions with a known fact ("Where do you
currently live? (City, State)") or an essay ("What is the coolest thing you have ever built using AI?") were skipped; Joey
2026-11-04: answer them. Rules: `plan_build.lever_urls` reads every `urls[X]` box on the page; rule `city_state`
(profile `city_state`); `prep_batch.optional_essay` sends optional question-textareas to ds_materials. Tests
`scripts/test_lever_gaps.py` (DeepSeek 24), `t_rules.js`. a Lever employer J00988 went in with the two optional boxes blank.

**J. A second submit of a finished application; tabs left behind.** ShopBack 11-04: Joey clicked Submit on a dry-run tab
(the extension recorded it, 02:00), then the runner submitted again (02:01) and Lever answered `/already-received`. Rules:
`run_form.already_submitted` refuses any folder with a `submitted` line in results.jsonl before opening the form; dry-run
tabs stay open (Joey 2026-11-04: 「刚跑结束后不用关掉标签，是要成功提交之后关掉。」) and are closed with every other tab of
the posting once a submit is confirmed — by the runner (`close_posting_tabs`, `posting_key`) or, for Joey's own submit, by
the lever_fill server through the job Chrome's DevTools endpoint (`close_job_chrome_tabs`). Tests
`scripts/test_already_submitted.py` (DeepSeek 16 + 12).

**K. Drafted answers dropped, fact questions mis-answered (JSA-150).** `plan_build.load_open_answers` read only ids made of
letters / digits / `_-`, so Lever card ids (`cards[uuid][fieldN]`) were skipped and every DeepSeek answer for a Lever card
was lost (optional essays blank, required ones back to needs_user). Rules that grabbed the wrong question: "Year of High
School Graduation" (grad_date → now `hs_grad_year` 2022), "If yes, what type of sponsorship?" (spons_future "Yes" → now
`sponsorship_type` = the profile's explanation), "School Major:" (school → discipline), a long values question with
"excellence" (phone: "cell" is a whole word now), "… MM/YYYY" degree dates (`degree_start_mmyyyy` / `degree_end_mmyyyy`);
format questions are never sent to the essay writer (`prep_batch.FACT_FORMAT`); canon no longer reads "accomplishments
from school or past internships" as the school field. Tests `scripts/test_rules_fix150.py` (DeepSeek 26),
`scripts/test_prep_fix150.py` (18), t_rules. Seen: a Lever employer / a Lever employer / Belvedere prep 11-05
