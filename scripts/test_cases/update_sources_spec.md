# update_sources: keep the Sources table (data/store/sources.jsonl) current after the daily refresh

`update_sources(sources, jobs, today, github_ok, boards_ok)` returns the new list of source rows. Each source row has
at least `source` (its label), `type`, `cadence`, `last_run` (YYYY-MM-DD), `in_dashboard` (int); other fields are kept.
A job's labels are its `sources` field split on "; " (a list is taken as is; a missing value has no labels).

1. `in_dashboard` of every source row = number of jobs that carry its label (0 if none).
2. If `github_ok` is true, every row whose `type` is "Curated GitHub list" gets `last_run` = today and
   `cadence` = "Daily 08:15". If false, those rows keep their old last_run and cadence.
3. If `boards_ok` is true, the rows "Lever boards" and "Ashby boards" get `last_run` = today and `cadence` =
   "Daily 08:15 (board search)". If false they keep theirs. Other rows (LinkedIn, Built In, Handshake, Greenhouse
   boards, Hacker News…) never get a new last_run or cadence from this function.
4. A label carried by at least one job but with no source row gets a new row: source = label, type =
   "Company job boards (API)" for "Workday search", "Certification test supply" for "Cert supply", "Other" for any
   other label; cadence = "As needed" (wd_search.py is not part of the daily refresh); last_run = today;
   in_dashboard = its count. The label "Unknown" never gets a row.
5. Existing rows are never removed, their other fields are never changed, and the input is not mutated. Output is
   sorted by `source`. Running twice with the same inputs gives the same result.
