# TikTok / ByteDance dry-run runner — pure helper functions (spec)

The runner fills a TikTok or ByteDance early-career application form, corrects what the site's resume parser got wrong using
the candidate's config, and reads every field back. These helper functions have no browser access.

## apply_url(url) → string or null
A posting URL becomes the apply-form URL.
- `https://lifeattiktok.com/search/<id>`, `https://careers.tiktok.com/position/<id>` (also `/resume/<id>/...`) → `https://lifeattiktok.com/resume/<id>/apply`
- `https://jobs.bytedance.com/en/position/<id>/detail` (also without `/en`, or `/resume/<id>/apply`), `https://joinbytedance.com/search/<id>` → `https://jobs.bytedance.com/en/resume/<id>/apply`
- `<id>` is a run of at least 10 digits. `www.` is allowed; `http` or `https`.
- Anything else (Greenhouse, Workday, a TikTok page without an id, an id shorter than 10 digits, empty, null) → null.

## parse_slots(text) → {limit, project, remaining} or null
Reads the form's limit banner, e.g. `From 2026-07-01 to 2026-12-31, you can submit up to 2 job applications (including
referrals) within the “Undergraduate/Master Intern - 2027 Start” recruitment project. You currently have 1 application(s)
remaining.` → `{limit: 2, project: "Undergraduate/Master Intern - 2027 Start", remaining: 1}`.
- The banner can sit inside other page text; line breaks and repeated spaces anywhere count as one space.
- The project name is in curly quotes “…” or straight quotes "…". Matching is case-insensitive. "application" may be singular.
- No banner (Project Intern and PhD roles have none) → null.

## field_of(degree) → string
Profile degree string → field of study: drop a leading abbreviation made of 1–3 dotted parts, each 1–4 letters starting with
a capital (`M.S.`, `B.A.`, `Ph.D.`, `M.B.A.`), and the space after it. `M.S. Applied Data Science` → `Applied Data Science`;
`B.A. Economics` → `Economics`; a string without such an abbreviation is returned trimmed; empty/null → empty string.

## month(s) → "YYYY-MM" or ""
`08/2025` → `2025-08`; `2025-08` → `2025-08`; `2025.8` → `2025-08`; `2025/8` → `2025-08` (a 4-digit year, one non-digit,
then a 1–2 digit month). Anything without a year+month (`2025`, `Aug 2025`, empty) → `""`.

## edu_plan(entries, education, wd_education) → (plan, problems)
- `entries`: education blocks on the page, `[{idx, school}]` (school text as the parser wrote it, often uppercase).
- `education`: the profile's schools `[{school, match_re, level, degree}]`, e.g. `{school: "University of Chicago",
  match_re: "chicago", level: "master", degree: "M.S. Applied Data Science"}` and `{school: "University of Illinois
  Urbana-Champaign", match_re: "illinois", level: "bachelor", degree: "B.A. Economics"}`.
- `wd_education`: `[{match, From_month, To_month}]` (a regex `match` tested against the profile school name), e.g. chicago →
  2026-09 / 2027-12, `illinois|urbana|uiuc` → 2024-08 / 2026-05.
Rules: page blocks are taken in order; a block matches the first unused profile school whose `match_re` is found in the
block's school text (case-insensitive). A master-level profile school never matches a block whose text names Illinois /
Urbana / UIUC unless the profile school itself is in Illinois (so "University of Illinois Chicago" is not UChicago). Each
profile school is used at most once. A matched block → plan item `{idx, school (profile name), degree, field, start, end}`
where degree is TikTok's option: master → "Master's degree", bachelor → "Bachelor's degree", phd → "PhD", mba → "MBA",
associate → "Associate degree"; field = field_of(profile degree); start/end from the matching wd_education entry ("" when
none matches). A block with an empty school or a school not in the profile → a problem string that names the block idx;
it is not in the plan. A profile school that matched no block → a problem string that names the school.

## lang_plan(entries, languages) → (plan, problems)
`entries` `[{idx, language}]`; `languages` `[{match, tiktok}]` (e.g. `{match: "chinese|mandarin", tiktok: "Native or
bilingual"}`, `{match: "english", tiktok: "Professional working"}`). A block whose language matches a `match` regex
(case-insensitive) → `{idx, language, proficiency: tiktok}`; "Mandarin" or "Cantonese" also match an entry whose `match`
contains "chinese". No match, or a matching entry without a `tiktok` level → a problem naming the block idx.

## work_plan(entries, work) → (plan, problems)
`entries` `[{idx, kind, company}]` (kind = internship or work); `work` `[{match, "Job Title", From, To}]` with From/To like
`08/2025`. A block whose company matches a `match` regex (case-insensitive) → `{idx, kind, title, start: month(From),
end: month(To)}`; otherwise a problem naming the block idx and the company.

## same(want, got) → bool
Whitespace-normalized, case-insensitive equality. If `want` looks like a phone number (only digits, spaces, `()+.-`, at
least 7 characters) the last 10 digits are compared. If either side contains " | " (a multi-select), compare the sorted
parts. Empty want vs empty got → true.
