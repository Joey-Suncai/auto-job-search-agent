---
name: ats-tiktok
description: Apply to a TikTok or ByteDance early-career job (lifeattiktok.com, careers.tiktok.com, jobs.bytedance.com, joinbytedance.com). Covers the per-candidate application limit, which decides what gets applied for, plus the sign-in rules, the dry-run runner (run_tiktok.py) and every TikTok / ByteDance problem type seen so far.
---

# TikTok / ByteDance applications (platform skill)

Part of the job-search agent. Read with `skills/auto-apply/SKILL.md` (general rules) and the candidate's facts in `config/`.
**After every TikTok / ByteDance batch, update §5**: add each new problem to its type, with the rule and the test that
enforces it. Record the kind of problem and its fix, not the company. Companies and dates go in the type's `Seen:` line
(private: the public export drops it).

## 1. Status (2026-11-03, JSA-047)
- **Dry-run runner `skills/auto-apply/runner/run_tiktok.py`.** It signs in, uploads the resume, corrects the parser's
  mistakes from `config/`, answers the questions with `answer_rules.js`, reads every field back and stops. **There is no
  submit code path.** Submit always shows a CAPTCHA, and the limit (§2) makes every application expensive, so the
  candidate submits by hand after reading `form_check.json`.
- 2026-11-03: 5 dry-runs on tier A TikTok forms (DE ×1, PM ×4), **95 / 95 fields read back**, 0 problems, ~40 s each.
  Then the slot candidate J00121 (AI Agent PM) with the availability resume: 20 / 20 incl. one parsed junk block removed.
- **JDs ask for availability on the resume** ("Please clearly state your availability in your resume, including your start
  and end dates"): use the availability variant (2026-10-26 folder, June 7 – September 3, 2027, confirmed by the candidate).
- **Project Intern roles (exempt from the limit) did not fit on 2026-11-03**: undergrad-only, or "2026 Start" needing
  3 months / 12 weeks during the M.S. term, or a 12-week winter. Read the JD before counting on the exemption.
  The slot counter stayed at 1, so dry-runs do not use a slot.
- TikTok account: created 2026-11-03 (candidate's e-mail + Keychain `jobagent-workday`; the candidate solved the CAPTCHA,
  and the e-mail code was read from Gmail). **ByteDance (`jobs.bytedance.com`) has a separate account system, and there is
  no account there yet** → the runner stops with "incorrect email or password".
- **Never a test application here.** Every 可投 role is tier A/B. Certification is dry-run only.

## 2. The application limit (read this before you pick anything)
From TikTok's Early Careers FAQ (https://lifeattiktok.com/earlycareers/faq, read 2026-11-02):
> "There are two application periods each year, and you may apply for up to **two Early Career positions per program
> within each application period**. Application periods: January to June · July to December. … The application limit
> applies to both **TikTok and its affiliates' jobs globally**. This application limit **does not apply to PhD and
> Project Intern** opportunities."
> "Can I withdraw my original application to apply for another position? **No**, you cannot withdraw … once submitted."

The form shows it too: *"From 2026-07-01 to 2026-12-31, you can submit up to 2 job applications (including referrals)
within the "Undergraduate/Master Intern - 2027 Start" recruitment project. You currently have N application(s) remaining."*
`run_tiktok.parse_slots` reads this banner into `form_check.json.slots`; 0 remaining → status `no-slot`. A Project Intern
form has **no banner** (confirmed 2026-11-03 on a "Product Manager - Project Intern" form).

Consequences:
- **2026H2: 1 slot left.** The other was used on 2026-10-27 (tracker J00109, Strategy PM Intern). Referral applications
  count against the limit too.
- ByteDance shares the limit even though it has separate accounts (the FAQ says "TikTok and its affiliates' jobs
  globally").
- Project Intern / PhD roles are outside the limit. Read each JD for term and dates first: they may not be a summer
  internship.
- So the ~190 可投 / 待核实 roles are **slots, not volume**. The candidate picks the slot roles himself. Record each submitted
  application's period (`2026H2`, `2027H1`).

**Slot counter (JSA-097, `skills/auto-apply/scripts/tiktok_slots.py`; spec `scripts/test_cases/tiktok_slots_spec.md`).**
- Limited = company name has tiktok / bytedance / capcut / lemon8 (incl. "TikTok USDS Joint Venture") or the posting is on
  lifeattiktok.com, careers.tiktok.com, jobs.bytedance.com, joinbytedance.com. Exempt = title has "Project Intern" or "PhD".
- Period = the **submit day**: January–June → `<YYYY>H1`, July–December → `<YYYY>H2` (a Summer 2027 role submitted in
  November 2026 uses a 2026H2 slot). Program = `intern` (level / title has the word intern) or `graduate` (new grad /
  full-time); each program has its own 2 slots; an unknown program counts against both.
- Counted = a limited, non-exempt tracker row with any status but Shortlisted / empty (Rejected still counts). Its period =
  the row's `period` field (written by `sync_results.py`, backfilled by `tiktok_slots.py --backfill`), else `applied_on`.
- `python3 skills/auto-apply/scripts/tiktok_slots.py` prints used / left per period. `prefilter.py` drops a counted role
  when its program is full ("tiktok slots full", with the reason) and tags the rest `SLOT1` / `SLOT2` (slots left);
  `run_tiktok.py` refuses before opening Chrome (status `no-slot`, exit 2) and flags a form banner that shows fewer
  applications left than the tracker (a submitted application missing from the tracker).

## 3. Sites and sign-in
| What | TikTok | ByteDance |
|---|---|---|
| Job page | `lifeattiktok.com/search/<id>` | `jobs.bytedance.com/en/position/<id>/detail` (also `joinbytedance.com`) |
| Apply form | `lifeattiktok.com/resume/<id>/apply` (`careers.tiktok.com/...` redirects here) | `jobs.bytedance.com/en/resume/<id>/apply` |
| Sign-in | e-mail + password, mobile, Facebook, LinkedIn. **No Google**. Terms box `input.atsx-checkbox-input` must be ticked; button `button.loginSubmit` | same page, **separate accounts** |
| Create account | `/create-account`: e-mail + password (≥ 8 chars, letters + numbers/symbols) → **CAPTCHA** ("Select 2 objects that are the same shape") → 6-digit e-mail code (Gmail, read-only) → lands on `/resume/edit` | not created yet |
| Submit | **CAPTCHA** at Submit (2026-10-27) → always the candidate | — |

Login rule (candidate 2026-10-30): use Google when it is offered; it is not offered here, so use the e-mail in
`config/profile.json` with the Keychain password `jobagent-workday`. A script reads the password (`wd_signin.keychain_password`);
it is never printed or sent to a model. The candidate allowed the runner to create the TikTok account (2026-11-03,
「<candidate e-mail>，允许runner」).

## 4. Flow (dry-run)
1. Pick: the candidate chooses the slot role(s) (§2); Project Intern roles need no slot. Check the counter first
   (`tiktok_slots.py`); the runner refuses a role whose slots are used.
2. Run (Mac, job Chrome on CDP 9222; one run at a time):
   `CX_DATA=~/Projects/job-search-agent/data/runner ~/.job-agent-venv/bin/python skills/auto-apply/runner/run_tiktok.py --job <J-id> [--resume <pdf>] [--wait-captcha 5]`
   Default resume: the track's A-Classic PDF in `resume/2026-10/`. Output: `data/runner/tiktok/<J-id>/` (`run_log.md`,
   `form_check.json`, `filled_check.png`) + one `results.jsonl` line (`ats: tiktok`). **Commit `data/runner/results.jsonl`
   right after the run** (uncommitted lines block `land.py` for other sessions).
3. Read `form_check.json`: `readback` (every planned field), `problems`, `slots`, and `review` (parsed blocks that have no
   config source — projects only when `config/profile.json` has no `projects` list). Decide on the review items with the candidate.
4. Submit: the candidate does it in the tab (CAPTCHA), then records it **the same day** (`sync_results.py --manual <folder>`;
   the row gets its `period`) — an unrecorded submit is an uncounted slot.

What the runner sets (everything else is left as the resume parser filled it):
| Field | Source |
|---|---|
| Resume | the PDF (the parser then fills basic info, education, internships, projects, languages) |
| Name / Mobile / Email | `config/profile.json` name.full, contact.phone (digits; +1 code), contact.email |
| Education degree / field / start–end month | profile `education` (level → TikTok option, field = degree minus "M.S." etc.) + `config/wd_profile.json` `From_month` / `To_month` |
| Language proficiency | `config/wd_profile.json` `languages[].tiktok` (English "Professional working", the candidate's choice 2026-10-26) |
| Internship title / period | `config/wd_profile.json` `work` (matched by company) |
| Project name / title / period / description | `config/profile.json` `projects` (matched by `match_re`; a parsed block that matches none is removed, a project the parser missed is added with the section's Add button; `end: null` → the end-month panel's "Present") |
| Work authorization (2 questions), "Where did you hear" | `answer_rules.js` through `rules_bridge.js` (No / Yes / "Recruitment Website") |
| Privacy Policy box | ticked (sends nothing by itself) |

Widgets: two families. `atsx-*` (antd-like) for the profile part: `.atsx-form-item` with `label[for="education[3].degree"]`
style keys; selects = `.atsx-select-selection` → visible `.atsx-select-dropdown li[role=option]`; school = a search
combobox (value in `.atsx-select-search__field`); dates = `.atsx-date-picker-period-month-label` ×2 → panel
`[data-cy="2024"]` then `[data-cy="08"]`. `ud-formily` for the job questions: `.ud-formily-item[data-form-field-id]` (label
in `data-form-field-i18n-name`), dropdown `.ud__select__dropdown .ud__select__list__item`.

## 5. Problem types and the rules that keep them fixed
**A. A limited slot spent by accident.** The limit is per candidate, per program and per half-year, and an application
cannot be withdrawn. Rule: `run_tiktok.py` has no submit path; it reads the slot banner and stops at 0 (`parse_slots`,
`test/t_tiktok.py`); the submit is the candidate's own click. The tracker is counted too (§2 slot counter): `prefilter.py`
and `run_tiktok.py` refuse a counted role whose program has used its 2 slots this half-year, and a banner showing fewer
left than the tracker is reported as a missing tracker row (`scripts/test_tiktok_slots.py`, 28 DeepSeek cases + 8 fixed).

**B. The resume parser writes wrong facts.** It filled the bachelor start date from an earlier school (2022-09 instead of
2024-08), set English to "Native or bilingual", and turned a leadership role into a project named after the role. Rule:
after upload, every field with a config source is overwritten from `config/` and read back (`edu_plan`, `lang_plan`,
`work_plan`, test `t_tiktok.py`). A block whose school / company is not in the config (e.g. the resume's availability
line read as an internship named "Available", or a school kept off applications) is **removed** with its own remove
button (`.resumeEditForm-item .formOperate-removeBtn`, no confirm dialog) and the removal is read back (`drop_unknown`).
Fields without a config source are listed in `form_check.json.review` for a human decision.

**B2. The parser files a non-project as a project and misses the real ones.** A leadership / club role was read as a
project named after the role, and none of the resume's real projects was parsed. Rule: projects have a config source,
`config/profile.json` `projects` (only projects already in the candidate profile; name, `match_re`, role, start, end —
null = ongoing — description in approved wording). `project_plan` matches parsed blocks to it in page order (each project
used once); an unmatched block is removed (`drop_unknown`), every project with no block gets a new block
(`TT.add_block` → `.createFormSection-addBtn` / `.formOperate-addBtn` of "Project Experience", the new `project[n]` key
found by diffing the labels), then name / role / period / desc are filled and read back like every other field.
Keys: `project[n].name` · `.role` ("Title") · `.period` · `.link` (left empty) · `.desc`. Ongoing end = the panel item
`[data-cy="-"]` "Present". Test: `test/t_tiktok.py` (24 DeepSeek cases `scripts/test_cases/tiktok_projects_cases.json`).
Without a `projects` list the runner falls back to listing the blocks in `review`.

**C. The page renders late.** The redirect to `/login` happens seconds after load, and the slot banner appears after the
form. Rule: wait for either `/login` or `label[for=name]`, and keep reading the banner until it appears (up to ~35 s);
a final pass re-reads every filled field, so a later fill cannot silently undo an earlier one.

**D. Two sites, two account systems, one limit.** The TikTok account does not sign in on `jobs.bytedance.com`. Rule: the
runner stops with "incorrect email or password (no account on this site yet?)"; creating the ByteDance account needs the
candidate (CAPTCHA). Seen: 11-03

**E. A CAPTCHA at account creation and at Submit.** Never solved by the runner; `--wait-captcha <min>` waits at sign-in
while the candidate solves it in the job Chrome tab. Seen: 10-27 (Submit), 11-03 (create account)

## 6. Answers that are easy to get wrong here
- "Are you legally authorized to work in the US **without restriction**?" → **No** (F-1). "Will you now or in the future
  require visa sponsorship or a visa transfer?" → **Yes**. Rules `any_employer` / `spons_future` (`t_rules.js`).
- "Where did you hear about this opportunity?" (multi-select) → "Recruitment Website" (profile `how_heard`; rule matches
  "where did you hear" since 2026-11-03).
- Education: start / end months come from the profile's education entries (`wd_profile.json`), never the résumé parser's
  guess (it read a wrong start year); a school the candidate keeps off the résumé never appears.
