# LinkedIn Easy Apply survey helpers — spec (2026-11-05, JSA-176)

A read-only survey counts how many LinkedIn internship listings use "Easy Apply" (applied inside LinkedIn) versus "Apply"
(goes to the company's own site). These pure functions do the parsing; none of them touches the network.

## search_url(keyword, easy=False, start=0) → string
A LinkedIn job-search URL for the United States, posted any time (LinkedIn's new search page; amended 2026-11-05 after
the first live run showed that the old `/jobs/search/` path redirects there and drops the experience-level filter).
- Scheme + host + path: `https://www.linkedin.com/jobs/search-results/`.
- Query parameters: `keywords` = the keyword exactly as given (URL-encoded), `geoId` = `103644278`.
- `f_AL` = `true` is present only when `easy` is true; absent otherwise.
- `start` is present only when `start` > 0 (its decimal value); absent when 0.
- No other parameters (in particular no `f_E`, no `f_TPR`, no location parameter).

## parse_count(text) → int or None
`text` is page text that may contain a results count such as "1,234 results".
- Find the FIRST place where a number is followed (optionally by "+", then optional spaces) by the word "result" or
  "results" (case-insensitive, whole word). Its number is the count.
- Numbers may contain thousands commas ("12,345" → 12345). A "K" / "k" suffix right after the number means thousands
  ("1K+ results" → 1000, "2.5K results" → 2500; round to the nearest whole number).
- A preceding "Over" / "About" does not change the number ("Over 1,000 results" → 1000).
- If there is no such count but the text contains "No matching jobs found" (case-insensitive) → 0.
- Otherwise → None (e.g. empty text, text without a count, "25 jobs", "results" with no number before it).
- A number not directly followed by result/results (only "+" and spaces may sit between) is ignored: in
  "3 new results" the 3 is not a count.

## classify_button(text) → "easy" | "external" | "unknown"
`text` is the visible text or aria-label of a job page's apply control. Compare case-insensitively with runs of
whitespace treated as one space.
1. Contains "easy apply" → "easy" (e.g. "Easy Apply", "Easy Apply to Data Analyst Intern at Acme").
2. Else contains "applied", "application submitted" or "no longer accepting" → "unknown" (already applied / closed).
3. Else contains the whole word "apply" → "external" (e.g. "Apply", "Apply on company website",
   "Apply to Acme on company website", "Apply now").
4. Else → "unknown" (e.g. "", "Save", "Applicants", "Application", "I'm interested").
The rules are checked in that order; the first that matches decides.

## link_target(href) → string
`href` of an apply link → the destination host, lowercase, a leading "www." removed; "" when there is none.
- Empty, None, a relative URL ("/jobs/view/1"), "#", or a non-http(s) scheme ("javascript:void(0)", "mailto:…") → "".
- A LinkedIn redirect — host `linkedin.com` or `www.linkedin.com`, path starting `/redir/redirect` or `/safety/go`,
  with a query parameter `url` — → the host of the decoded `url` parameter (same lowercase / no-"www." rule; "" if that
  is not an http(s) URL).
- Any other URL whose host is `linkedin.com` or ends with `.linkedin.com` → "linkedin".
- Otherwise the host of `href` itself (port dropped).

## card_easy(lines) → bool
`lines` = the text lines of one search-result card. True when any line, stripped, equals "Easy Apply"
(case-insensitive); False otherwise (also for an empty list, or a line such as "Easy Apply available soon").

## card_title(lines) → string
`lines` = the text lines of one search-result card. The title is the first non-empty line (after stripping spaces) with a
trailing "(Verified job)" removed (case-insensitive, with the spaces before it); "" when there are no non-empty lines.

## intern_title(title) → bool
True when `title` contains, as a whole word (case-insensitive), one of: intern, interns, internship, internships,
co-op, coop. False otherwise — e.g. "Internal Audit Analyst", "International Data Analyst", "Data Engineer", "" or None.

## pick_sample(groups, n) → list of ids
`groups` = a list of [keyword, [job ids in page order]]. Take ids round-robin: the 1st id of each group in group order,
then the 2nd id of each group, and so on; skip an id already taken; stop at `n` ids or when every group is used up.
Groups with fewer ids simply run out. n ≤ 0 → [].

## share(part, total) → float or None
part / total rounded to 3 decimals; None when total is 0 or None, or part is None.
