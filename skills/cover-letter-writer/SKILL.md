---
name: cover-letter-writer
description: Writes Alex Rivera's cover letter for one specific job — reads the job description, maps its must-haves to his verified profile and pre-approved story bank, drafts a one-page letter, and produces .txt, .docx and .pdf in the application folder. Use whenever a cover letter is needed, including from auto-apply.
---

# Cover-letter writer (agent)

**Every application gets a letter** — also when the form has no cover-letter slot (Joey 2026-11-05).

**Inputs:**
- the job description text;
- company and role;
- output folder `applications/<YYYY-MM-DD>_<Company>/`;
- optionally, where the letter will go (a file upload, or a text box with a character limit).

**Outputs:** `fit_map.md`, `cover.txt`, `Alex_Rivera_Cover_Letter_<Company>.docx` and `.pdf`.

**Sources of facts:** `skills/_shared/candidate-profile.md` and `skills/_shared/story-bank.md`. Nothing else.

## Rules
1. **Story bank only.** The main story and every personal detail come from `story-bank.md`, and only from stories marked **Confirmed**. You may shorten, rephrase and reorder; you may not add a fact, number, feeling, quote or motivation that is not written there or in the profile. Never invent a new story — if one is missing, report the gap (Step 7).
2. **Don't summarize the resume.** Each body paragraph must add something the resume can't: how he did it, why it mattered, what it shows about how he works.
3. **Show, don't claim.** No trait adjective ("detail-oriented", "passionate", "strong communicator") unless the same sentence or the next one proves it with a concrete example.
4. **Warm, plain tone** — like writing to a colleague he respects but doesn't know well. No template phrases: "I am writing to express my interest", "I believe I would be a great fit", "fast-paced", "dynamic", "leverage", "passionate about", "I am confident that".
5. **Specificity test.** If another applicant could send the letter with only the name changed, rewrite it.
6. **Never write what he hasn't done** (Joey 2026-11-05: 「不写我还没做过 X」). No "I have not / haven't (yet) used X", no list of missing tools or domains — in the letter or in open answers. A JD tool he lacks is a gap in `fit_map.md`, never a sentence. When his background will make the reader wonder (economics degree for an engineering role), answer with what he *has* done that fits, with evidence — no apology, no gap list. Enforced by `ds_materials.py` from JSA-190; until then check `cover.txt` for such sentences.
7. Keep team work as team work (the stock project is a team of 3). Don't mention visa status unless he asks.

## Steps
1. **Read the job description.** Pull out:
   - the company's mission or problem, in their words, plus one specific fact about the company (product, customer, recent news);
   - the 3–5 must-haves, ranked by how central they are to the job;
   - logistics (location, on-site days, dates);
   - job ID / requisition number, hiring manager name, any character limit.
2. **Build the fit map** (internal worksheet, saved as `fit_map.md`, never pasted into the letter). One row per must-have:
   `must-have | best story ID or profile fact | strong / partial / none`. Sort strongest first.
3. **Choose material.**
   - **Main story:** the Confirmed story whose tags best match the #1 must-have.
   - **Supporting proofs:** 1–2 more facts or stories for the next must-haves.
   - **Motivation:** a motivation from the story bank that genuinely fits this company, tied to the specific company fact from Step 1.
4. **Draft 300–400 words, four paragraphs:**
   - **(a) Opening** — the role (and job ID if there is one); why this company, specifically; one sentence previewing what he brings. Simple and direct, no gimmick hook.
   - **(b) The story** — situation → what he did and how → result with numbers. Make clear which must-have it proves.
   - **(c) Fit and context** — 1–2 more must-haves with brief proof; answer any question the reader will have (Rule 6); logistics if they matter.
   - **(d) Close** — one line restating the fit, interest in talking, thanks.
   - Greeting: the hiring manager's name if known, otherwise "Dear Hiring Manager" or "Dear <Company> team". Sign as "Alex Rivera".
5. **Check:**
   - every fact and number appears in the profile or a Confirmed story;
   - the company and role names are spelled exactly; job ID included if given;
   - 300–400 words (or under the character limit), one page;
   - no banned phrases; the resume-summary test (Rule 2) and specificity test (Rule 5) pass.
6. **Build the files.**
   - Save the text as `cover.txt`: paragraphs separated by blank lines, ending with the sign-off and a contact line.
   - Run `node scripts/cover.js` in a folder holding `cover.txt`, with the `docx` package available. It reads `cover.txt` and writes the `.docx`: maroon name header, contact line, date and role line, Calibri 11.
   - Edit the role line and the output filename in `cover.js` for each job.
   - Run `soffice --headless --convert-to pdf`, then `pdfinfo` to confirm it is 1 page.
7. **Return:**
   - the file paths;
   - the text with no sign-off contact line, for pasting into a form text box;
   - the story IDs used;
   - **story bank gaps**: any top-3 must-have with no strong Confirmed story, with a one-line suggestion for a story he could add. The letter still ships using the best partial match — no waiting for review.

Example: `applications/2026-10-23_Netic/` (an Ashby employer, Full-Stack Software Engineer (Product) intern) — written before this version.

## Why these rules (sources)
- Don't summarize the resume; show traits with a concrete example; explain unusual candidacy; warm conversational tone; about one page; simple opening; "Dear Hiring Manager" is fine — Ask a Manager, "How to write a great cover letter": https://www.askamanager.org/2018/05/how-to-write-a-great-cover-letter.html
- Opening = purpose + why this role/organization + preview of strengths; 2–3 body paragraphs with detail beyond the resume; close restates fit and thanks; include job reference code; one page — MIT CAPD: https://capd.mit.edu/resources/how-to-write-an-effective-cover-letter/
- ~400 words preferred; matching the posted skills is the most important tailoring step; the introduction leaves the biggest impression (self-reported surveys, 2022–2023) — Resume Genius: https://resumegenius.com/blog/cover-letter-help/cover-letter-statistics/t3
- Requirement → qualification map, strongest first — TechWhirl, T-letter: https://techwhirl.com/get-more-interviews-with-a-t-letter/
- After AI writing tools spread, generic tailoring lost most of its signal value; edited, specific letters did better — Galdin & Silbert, "Signaling in the Age of AI" (2025): https://arxiv.org/html/2509.25054v1 (this is why real details come from a pre-approved story bank)

**Never a story ID in the text (2026-11-04, JSA-162).** `ds_materials.leaked_ids` rejects a letter or answer that contains a story-bank ID ("(M2)", "S6"): the draft is re-asked. Test `scripts/test_leaked_ids.py`.

**The program is "Applied Data Science" (2026-11-04, JSA-163).** `ds_materials.wrong_program` rejects "a Master's / M.S. / degree … in Data Science" without "Applied". Test `scripts/test_wrong_program.py`.
