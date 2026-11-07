---
name: resume-updater
description: Builds and updates Alex Rivera's resumes — keeps the 4 role versions (Data Engineer, Data Analyst, Product Manager, AI Agentic Engineer) and his general original in the A-Classic layout, and tailors A-Classic for one job using a JD keyword map, the exact job title, and only pre-approved wording from the bullet bank. Checks readability (1 full page, 0.5 in margins, bullets ≤ 2 lines) and reports every change.
---

# Resume Updater

Folder: `/Users/you/Projects/job-search-agent/` (access: see `job-search-agent`).
- **Original** (his general resume): `resume/Alex_Rivera_Resume_UChicago_ADS_original.docx` (text copy `skills/resume-updater/references/resume-original.md`). Change it only when he asks; preview first. Edits are done on its XML (see §6), not with `build_a.py`.
- **Template for `build_a.py`: `resume/Alex_Rivera_Resume_UChicago_ADS_original_TEMPLATE.docx`** (the 2026-10-22 original; paragraph indexes in §5 refer to it). **Never overwrite the template.**
- **Role versions:** `resume/<YYYY-MM>/Alex_Rivera_Resume_<Role>_A-Classic.docx` + `.pdf`. Before replacing, `mv` the old files into `resume/<YYYY-MM>/_archive_A-Classic_before_<date>/` (iCloud placeholders can't be `cp`'d from the device shell).
- **Wording:** `skills/resume-updater/scripts/content.py` (all role wording) and `skills/_shared/bullet-bank.md` (every approved bullet wording, tagged).
- **Facts:** `skills/_shared/candidate-profile.md`; deeper detail `skills/_shared/story-bank.md`. Decisions: `skills/_shared/decisions-log.md`.
- **Scripts:** `build_a.py` (build), `fill.py` (page fill), `check_resume.py` (readability + wording), `diff_resume.py` (change list). `build_b.js` = retired B-Modern style, don't use.
- Read the `anthropic-skills:docx` skill only for new layout work (`office/validate.py`); rebuilding the bases needs nothing outside this folder (`scripts/prepare_template.py`).

## 1. Rules (every resume)
1. **Truth only.** Every fact must be in `candidate-profile.md`. Every sentence must be in `bullet-bank.md`. A new wording needs his yes in chat, then goes into the bank.
2. **Decided — don't re-ask:**
   - Email alex.rivera@example.com. Contact line adds `linkedin.com/in/example | github.com/example`.
   - Stock project = team of 3, he led most of the code and analysis. Never "independently".
   - Projects: **Job Searching Agent** *(Personal project, built with Claude Code)*, "Ongoing", first; then the stock project. NC tax project and the old AI Job-Intelligence Pipeline are off the resume. Agent wording "designed / operate / specified / set", never "coded". No application count until the tracker shows it (update at 25 / 50 / 100).
   - Equity screen: AI tools only gathered the fundamentals data; shortlist = 30 stocks. LCOF model: co-built with a consultant.
   - XJTLU off Education; Voice Club leadership stays but the competition is written **"Voice" flagship competition** — no school name (Joey 2026-10-28, supersedes the 10-22 "keep as is"). A-Classic is the only style. Titles "… Intern". Visa status never written.
3. **Accomplishments, not duties** — each bullet starts with a varied action verb and follows **X-Y-Z**: accomplished X, as measured by Y, by doing Z. Bullets without a measure are reported, and improved only when a real number exists. *(Google / Laszlo Bock; MIT CAPD; Harvard OCS)*
4. **Plain words.** Banned: leverage(d), spearhead(ed), orchestrate(d), synergy, dynamic, passionate, results-driven, cutting-edge, detail-oriented, team player, utilize(d), seamlessly, robust. *(TopResume 2025 survey: 19.6% of hiring managers would reject an AI-generated resume; 52% accept AI help but want it to sound human.)*
5. **ATS-safe layout** — single column, standard section names, no tables, no text in headers or footers, no graphics. *(Greenhouse via Jobscan; MIT CAPD)*

## 2. One full page that stays readable (his rule, revised 2026-10-24)
Fill one page **with real content**, but keep it readable *(Ladders eye-tracking: 7.4 s first look; cluttered layouts, too little white space and long sentences hurt. MIT CAPD: don't shrink fonts or margins; margins ≥ 0.5 in)*:
- 1 page; `fill.py` bottom ≈ 730–756 (the bottom margin starts at 756).
- Margins ≥ 0.5 in on all sides (`build_a.py` sets 720 twips; the template had 620 top/bottom).
- Every bullet ≤ 2 lines; no last line holding a single word.
- Font 10–11 pt; never below 10 pt.
Order to fill: (1) a true bullet from the bank; (2) spacing (`a_bullet_after` 20–30, `a_section_before` 80–120); (3) font `a_sz` 21–22. If it spills, back off in reverse order. Never drop the strongest content to fit.
`python3 scripts/check_resume.py <docx…>` enforces margins, ≤ 2 lines, one-word last lines and banned words (exit 1 = fix), and lists bullets with no number.
Current (2026-10-24): DE bullet 30 + section 120 · DA bullet 30 + section 120 · PM 11 pt + bullet 30 + section 120 · AI 10.5 pt + bullet 30 + section 120 → bottoms DE 741 · DA 751 · PM 738 · AI 740 · Original 740.

## 3. Role versions (same facts, different emphasis)
| | Data Engineer | Data Analyst | Product Manager | AI Agentic Engineer |
| --- | --- | --- | --- | --- |
| Headline (italic) | Data Engineering Internship 2027 · Python · SQL · Cloud-Native Data Pipelines | Data Analyst / BI Internship 2027 · SQL · Python · R · Excel · Tableau | AI Product / Product Analytics Internship 2027 · Evaluation Design · Data-Driven Decisions | AI / Agentic Engineering Internship 2027 · LLM Agents · Evaluation · Human-in-the-Loop |
| Section order | Edu → Skills → Experience → Projects → Leadership | same as DE | same as DE | Edu → Skills → **Projects → Experience** → Leadership |
| Agent bullets | ingestion · dedup · tiers + dashboard · application flow | dedup · scoring priorities · tiers + dashboard · application flow | multi-agent · guardrails · application flow | multi-agent · guardrails · tailored outputs · application flow |
| Hyde Park | 4 (cleaning first) | 4 (cleaning first) | 3 (rubric first) | 3 (rubric first) |
Stock project: DE 3 bullets, others 2. Voice Club: 3 bullets everywhere. PM and DA carry an extra "Domains" skill line.

## 4. Tailor for one specific job (resume agent; used by `auto-apply`)
Inputs: job description, company + role, output folder `applications/<YYYY-MM-DD>_<Company>/`. Style: A-Classic.
Start from the closest base role in `content.py`; keep its sections and facts.

1. **Keyword map** — save `keyword_map.md` in the application folder. List the JD's skills, tools, methods and repeated verbs, the must-haves first in the order the JD lists them:
   `JD term | true for him? (profile/bank) | where it appears on the resume | action`.
   Every **true** must-have appears **verbatim at least once** (skills line or a bank bullet that already says it). Untrue terms are never added; list them as gaps. *(MIT CAPD: mirror the JD's repeated terms where your experience supports it, prioritise requirements listed first. Jobscan / Greenhouse: recruiters search and filter parsed resumes by skills and the posting's own terms — vendor data, directional only.)*
2. **Headline = the posting's exact job title** first, then 2–4 true JD keywords, e.g. "Data Engineer Intern, Summer 2027 · Python · SQL · Airflow". *(Jobscan: resumes containing the job title got 10.6× more interview invitations — vendor data.)*
3. **Pick and order bullets from `bullet-bank.md` only:**
   - the first bullet under each job/project = the one that best matches the JD's #1 must-have;
   - swap in a bank variant whose tags match the JD better;
   - move Projects above Experience when the projects match the JD better *(Harvard OCS: put the more relevant section first; Ladders: F-pattern, the top of the page gets read)*;
   - add or drop at most 1–2 bank bullets or skill lines to fill the page.
   Not allowed: new sentences, new facts, changed titles/dates/numbers, new sections.
4. **Build:** deep-copy the base role, apply the changes, write `content.json` with `ROLES = {"<Company>_<Role>": role}` (examples `config/examples/tailor_job_example_netic.py`, `config/examples/content_job_example_netic.py` (personal, moved 2026-11-02)); copy `build_a.py` into the job folder, symlink `un/` (unpacked TEMPLATE), add the `HEADLINES[key]` line, set section order, run it; `soffice` → PDF.
5. **Check:** `fill.py` (1 page, bottom 730–756), `check_resume.py` (must pass), look at the render.
   **Page top-up (JSA-063, `ds_materials.py` `fill_candidates` / `layout_fill`):** when the page is under-filled even at the loosest spacing, the build adds back, one at a time, an item the selection step dropped from the **base track's own** resume — bullets first (best JD-word match first, ties in base order), then skill lines — within the §4.3 limits (entry ≤ base+1, total ≤ base+1, skill lines ≤ base+1). It skips a base bullet whose tags equal a swapped-in variant's in the same entry (same fact twice) and a skill line whose label is already on the page; an item that pushes it to two pages is undone and the next one tried. Each addition is a change-list line ("补满一页"). Nothing left to add → it fails with "a longer approved wording is needed" (ask Joey; never pad). Tests: `scripts/test_fill_candidates.py` (DeepSeek cases).
6. **Report to him (in Chinese):** `python3 scripts/diff_resume.py <base_role> content.json` + the headline change + the keyword map summary (true must-haves covered, gaps not covered) + bullets with no measure. Save `Alex_Rivera_Resume_<Company>_<Role>_A-Classic.{docx,pdf}` in the application folder and return the PDF with this report.

## 5. A-Classic build (`build_a.py`) — cloned from the TEMPLATE's XML
1. `python3 scripts/prepare_template.py` (unzips the TEMPLATE into `scripts/un/`, drops symlinks, merges runs, and checks the run count of every paragraph template below; self-contained since JSA-012 — the docx skill's `merge_runs.py` is not needed). `build_a.py` runs it by itself when `un/` is missing; `python3 scripts/build_a.py` then rebuilds the four bases byte-for-byte in text and layout (layout knobs `a_sz`, `a_bullet_after` — also applied to the Courses lines — and `a_section_before` live in `content.py`, never as docx patches).
2. Paragraph templates (after merge_runs): p0 name · p1 contact · p2 section header (bold small caps, bottom border, before 80 / after 30) · p3 school + right-tab location · p7 degree + right-tab date · p8 "Courses:" bullet · p13 skill line · p16 org (small caps) · p17 title + tab + date · p18 bullet (style `a4`, numId 2) · p25 project line (bold title + italic tag + tab date). Headline = p1 + italic.
3. `fill(tpl, texts)` replaces each `<w:t>` in order (escape & < >) and strips `w14:paraId`. Body = head + new paragraphs + template `<w:sectPr>` with top/bottom margins raised to 720.
4. Role knobs in `content.py`: `a_sz`, `a_bullet_after`, `a_section_before`, `skills_a` (extra skill lines). In nested helpers use `out.extend(...)`.
5. Copy `un/` → `build_<Role>/`, write `document.xml`, `zip -Xqr out/<name>.docx .`; validate with `office/validate.py`.

## 6. Editing the original (only when he asks)
Unpack the original, `merge_runs.py`, edit paragraphs in `word/document.xml` with the same `fill()` approach (clone an existing bullet/project paragraph as the template), set `pgMar` top/bottom 720, re-zip, `validate.py --original`, then §2 checks. 2026-10-24 script: container `rs/orig/edit_orig.py` (not kept on the Mac).

## 7. Deliver
Preview first (he approves every resume change before replacement). Then: archive the old files (`mv`), `device_commit_files` the new `.docx` + `.pdf`, update `content.py` / `bullet-bank.md` if wording changed, log in the session log and decisions log.

## Sources (why these rules)
- MIT CAPD, Crafting an effective resume — master + tailored versions, action verb + quantified result, mirror JD terms, prioritise first-listed requirements, ATS-safe templates, margins ≥ 0.5 in, don't shrink fonts, verify AI output: https://capd.mit.edu/resources/career-toolkit-crafting-an-effective-resume/
- Harvard OCS, Resumes and Cover Letters (mirror) — action verbs, quantify, vary verbs, tailor, move the more relevant section up, easy to skim: https://fae.uprrp.edu/enlace/wp-content/uploads/sites/17/2022/08/undergrad_resumes_and_cover_letters.pdf
- Ladders eye-tracking study (HR Dive) — 7.4 s first screen; clear sections, F/E-pattern, bold titles; clutter, too little white space, long sentences hurt: https://www.hrdive.com/news/recruiters-spend-74-seconds-looking-at-your-resume/541582/
- Google / Laszlo Bock X-Y-Z formula (Inc.com): https://law.utexas.edu/wp-content/uploads/sites/44/2020/09/Google-Recruiters-Say-Using-the-X-Y-Z-Formula-on-Your-Resume-Will-Improve-Your-Odds-of-Getting-Hired-at-Google-_-Inc.com_.pdf
- Jobscan, ATS resume guide (vendor data: 99.7% keyword filters, 76.4% search by skills, 10.6× job title): https://www.jobscan.co/blog/ats-resume/
- Jobscan on Greenhouse — no auto-reject; parsing breaks on tables, columns, header/footer text; use the posting's terms: https://www.jobscan.co/blog/greenhouse-ats-what-job-seekers-need-to-know/
- TopResume 2025 hiring-manager survey on AI-written applications: https://topresume.com/career-advice/ai-in-hiring-survey
