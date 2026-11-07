# Aggregator link resolver (JSA-046)

A job row has a `url`, a `company`, a `title` and maybe an `ats_url`. Some urls point at job aggregators instead of the
company's own application page. A decision function returns what to store for one row. Network access is given to it
as functions (in tests: fixed tables): follow(url) → final URL after redirects, or nothing on a network error;
board(ats, token) → list of (posting title, posting url) on a company job board; wd_search(host, tenant, site, title) →
list of (posting title, posting url) from a Workday site's search. It also gets three candidate lists for the row's
company: `known` boards [(ats, token)], `guesses` [(ats, token)], `tenants` [(host, tenant, site)].

Output: nothing (null) for a row it does not handle, else an object with `code` and, depending on the code, `ats_url`.

1. Aggregator kind from the url (case-insensitive): contains "zapply.jobs" → zapply; else "go.vansh.nyc" → vansh; else
   "jobright.ai/jobs/info/" → jobright. Any other url → null.
2. A row that already has a non-empty ats_url → code "already" (nothing else is called).
3. zapply and vansh rows: follow the url.
   - no final URL → code "dead_link".
   - final URL's host contains "zapply.jobs" or "vansh.nyc": if the host is zapply.jobs and the path is exactly "/jobs"
     or "/jobs/" → code "expired"; otherwise → code "stuck".
   - otherwise → code "redirect", ats_url = the final URL with these query parameters removed (names matched
     case-insensitively): any starting with "utm_", and "source", "src", "gh_src", "iis", "iisn". Other parameters and the path stay.
4. jobright rows: the jobright url is never followed or fetched (follow must not be called).
   - empty or whitespace title → code "no_title".
   - Candidates in this order: every `known` board, then every `guesses` board that is not in `known`, then every Workday tenant.
     For a board candidate the postings are board(ats, token); for a tenant, wd_search(host, tenant, site, row title).
   - Title similarity = |A ∩ B| / |A ∪ B| where A and B are the sets of words of the two titles after lowercasing,
     replacing every character that is not a letter, digit or space by a space, and dropping the words
     the, a, an, and, of, for, in, to, u, s, us, usa.
   - A candidate matches when its best posting has similarity ≥ 0.75, unless the second-best posting has exactly the same
     similarity and a different url (two equally good postings → that candidate gives no match, go on to the next one).
   - The first candidate that matches wins: code "board" (from a board) or "workday" (from a tenant), ats_url = the
     matching posting's url, exactly as given.
   - No candidate matches (or there are none) → code "no_match".
