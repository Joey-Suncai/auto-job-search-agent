# linkedin_search.py — spec (JSA-069)

LinkedIn job-search result cards (read from the signed-in search page, never the job page) become job rows for a student
who wants Summer 2027 internships or 2027/2028 new-grad roles in the United States in data / analytics / BI / product /
AI. `today` below is 2026-11-01.

## rel_date(text, today) → str
A relative date phrase → ISO date (YYYY-MM-DD) counted back from `today`; '' when the text is not such a phrase.
- Case-insensitive; surrounding spaces ignored; an optional leading "Posted " or "Reposted " is ignored.
- "Today" / "Just now" → today. "Yesterday" → today − 1 day.
- "<n> <unit> ago" / "<n> <unit>s ago" where n is digits, "a", "an" or "one" (= 1) and unit is minute, hour (both → 0
  days), day (1), week (7), month (30), year (365) → today − n × unit days.
- The whole text must be the phrase: "Posted 2 weeks ago" → 2026-10-18; "3 days ago" → 2026-10-29; "Reposted One Month
  Ago" → 2026-10-02; "5 hours ago" → 2026-11-01; "Viewed", "Be an early applicant", "2 weeks" (no "ago"),
  "Posted 2 weeks ago · 40 applicants" → ''.

## job_id(url) → str
The numeric LinkedIn job id (6 or more digits) from a linkedin.com URL: the path "/jobs/view/<id>" (also
"/jobs/view/<words>-<id>", with or without a trailing slash or query) or a "currentJobId=<id>" query parameter. Anything
else (another site, no id, fewer than 6 digits) → ''.

## parse_card(rec, today) → dict | None
`rec` = {"id": "<job id>", "lines": [text lines of the card]}. Returns None when the id has no digits, or when fewer
than three lines remain after the title rule below. Otherwise returns
{"job_id", "title", "company", "location", "remote", "salary", "posted", "li_alumni", "li_connections"}:
- job_id = the digits of rec.id. Empty / whitespace-only lines are dropped first.
- Title rule: the first line may end in " (Verified job)" (any case); that suffix is removed. If the second line equals
  the (cleaned) first line, the first line is dropped (the title counts once). The remaining lines are then:
  title, company, location, then any number of insight lines.
- location: a trailing " (On-site)", " (Onsite)", " (Hybrid)" or " (Remote)" (any case) is removed; remote = "Yes"
  when that suffix was "(Remote)", else "".
- Insight lines, any order: "N connection works here" / "N connections work here" → li_connections = N;
  "N school alumni work here" / "N school alumni works here" → li_alumni = N ("company alumni" lines are ignored);
  the first line starting with "$" → salary (the line as is); the first line starting with "Posted" or "Reposted" →
  posted = rel_date(line); without such a line, the first other line that rel_date understands (e.g. "1 week ago").
  Everything else ("Easy Apply", "Viewed", "·", "Medical benefit") is ignored. Defaults: salary "", posted "",
  li_alumni 0, li_connections 0.

## keep_card(title, location) (shared with Indeed, used by pick_new)
True only when: the title has a track word (data, analy…, AI, machine learning, ML, LLM, GenAI, agent/agentic, product,
business intelligence, BI, insight(s)); no senior word (senior, sr, staff, principal, lead, director, head of, VP,
architect, PhD, Ph.D, postdoc, MBA); the location is not clearly outside the U.S.; and the title is a 2027-or-no-year
internship without fall / spring / winter / co-op / year-round / part-time, or a new-grad / entry title with no year other
than 2027 / 2028.

## pick_new(cards, ids, pairs) → list of cards (tested as the list of their job_id)
`cards` = parsed cards in order; `ids` = LinkedIn job ids already in the store; `pairs` = (company key, title key) pairs
already in the store. A card is dropped when its job_id is in ids, its (company key, title key) is in pairs, or
keep_card is False. Kept cards add their id and pair, so a later card with the same id or the same pair is dropped too.
Order is kept; there is no per-company limit.
- company key: lower case, "&" → " and ", ".com" removed, other non-alphanumerics → space, then the words inc,
  incorporated, llc, corp, corporation, co, company, ltd, limited, plc, lp, llp, holding(s), group, the, usa, us,
  america, na, services, technologies, technology, lab(s), global, international removed; spaces collapsed.
  "an employer Platforms, Inc." → "meta platforms"; "The Walt Disney Company" → "walt disney".
- title key: lower case; text in ( ) or [ ] removed; 20xx years, summer, intern(s), internship(s), new grad(uate),
  remote, us, usa removed; non-alphanumeric runs → one space; trimmed. "Data Analyst Intern (Summer 2027)" → "data analyst".

## company_tiers(rows) → {company key: tier}
For each store row take tier_orig, else tier; only A, B, C, D count (Blocked, '' and others ignored). Per company key
the most common tier wins; a tie goes to the better tier (A before B before C before D). Companies with no counting row
are absent.
