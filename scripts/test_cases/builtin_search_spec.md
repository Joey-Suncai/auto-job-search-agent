# builtin_search.py — spec (JSA-069)

Built In (builtin.com) search result cards become job rows for a student who wants Summer 2027 internships or
2027/2028 new-grad roles in the United States in data / analytics / BI / product / AI. `today` below is 2026-11-01.

## job_id(url) → str
The digits at the end of a Built In job path "/job/<slug>/<digits>", either relative ("/job/data-intern/11528663") or
on builtin.com ("https://builtin.com/job/data-intern/11528663"); a trailing "/", "?query" or "#fragment" after the
digits is allowed. Anything else ("/company/acme", "/job/11528663" with no slug, "/jobs?search=data") → ''.

## parse_card(rec, today) → dict | None
`rec` = {"id": "<card id>", "href": "/job/<slug>/<id>", "lines": [text lines], optional "title", optional "company"}.
- job_id = job_id(href) when href has one (the card id can differ from it), else the digits of rec.id.
- company = rec.company when non-empty, else lines[0]; title = rec.title when non-empty, else lines[1].
- None when job_id, title or company is empty.
- The other lines (lines equal to the title or company skipped) are recognised by their shape:
  - work mode: "In-Office", "Hybrid", "Remote", or two of them joined by " or " ("In-Office or Remote",
    "Remote or Hybrid"), any case. remote = "Yes" when the work mode starts with "Remote", else "".
    location = the line right after the (first) work mode line, unless that line is a salary, a level, a work mode or
    "Easy Apply" (then location = "").
  - salary: "<n>-<n> Hourly|Annually|Monthly", each n digits with an optional decimal part and optional K or M
    ("28K-28K Hourly", "50-50 Annually", "55-10K Hourly") → salary (first one).
  - level: "Internship", "Entry level", "Junior", "Mid level", "Senior level", "Expert/Leader" → bi_level (first one).
  - posted: the first line that is a relative date: optional "Posted " / "Reposted ", then "Today", "Just now",
    "Yesterday", or "<n> <unit>(s) ago" with n = digits / "a" / "an" / "one" and unit minute / hour (0 days), day (1),
    week (7), month (30), year (365) → ISO date counted back from today ("Reposted One Month Ago" → 2026-10-02,
    "3 Days Ago" → 2026-10-29, "Yesterday" → 2026-10-31).
- url = "https://builtin.com" + href (query / fragment removed) when href's id equals job_id; a full https href is kept
  as is; otherwise "https://builtin.com/job/<slug of title>/<job_id>" (slug = lower case, runs of non-alphanumerics → "-",
  no leading / trailing "-").
- Output: {"job_id", "title", "company", "location", "remote", "salary", "posted", "bi_level", "url"}; missing parts "".

## known(rows) → (ids, pairs)
ids = every job_id(...) of a row's url and ats_url, plus <digits> of an elig_key exactly "bi:<digits>". pairs = the
(company key, title key) of every row (see pick_new).

## pick_new(cards, ids, pairs) → list of cards (tested as the list of their job_id)
A card is dropped when its job_id is in ids, its (company key, title key) is in pairs, or keep_card(title, location) is
False. Kept cards add their id and pair, so a later card with the same id or pair is dropped too. Order kept, no
per-company limit.
- keep_card: the title has a track word (data, analy…, AI, machine learning, ML, LLM, GenAI, agent/agentic, product,
  business intelligence, BI, insight(s)); no senior word (senior, sr, staff, principal, lead, director, head of, VP,
  architect, PhD, Ph.D, postdoc, MBA); the location is not clearly outside the U.S. ("3 Locations", "Remote", U.S. cities
  are fine); and the title is a 2027-or-no-year internship without fall / spring / winter / co-op / year-round /
  part-time, or a new-grad / entry title with no year other than 2027 / 2028.
- company key: lower case, "&" → " and ", ".com" removed, other non-alphanumerics → space, the words inc, incorporated,
  llc, corp, corporation, co, company, ltd, limited, plc, lp, llp, holding(s), group, the, usa, us, america, na,
  services, technologies, technology, lab(s), global, international removed; spaces collapsed.
- title key: lower case; text in ( ) or [ ] removed; 20xx years, summer, intern(s), internship(s), new grad(uate),
  remote, us, usa removed; non-alphanumeric runs → one space; trimmed.
