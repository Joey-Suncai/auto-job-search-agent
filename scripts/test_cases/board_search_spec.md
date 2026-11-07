# Lever / Ashby job-board search helpers

1. parse_board(url) → ["lever", board] for jobs.lever.co/<board>/... (also jobs.eu.lever.co), ["ashby", board] for
   jobs.ashbyhq.com/<board>/..., board lower-cased; anything else (other ATS, api.ashbyhq.com, empty) → null.
2. posting_id(url) → the posting UUID (8-4-4-4-12 hex) in the URL, lower-cased; "" when there is none.
3. keep_posting(title, location) → true only for an internship he could do in Summer 2027 in the U.S.:
   the title says intern / internship / interns (not "internal" or "international"); no fall / autumn / spring / winter / co-op /
   year-round / part-time in the title; a year in the title other than 2027 → false; a location clearly outside the U.S.
   (a foreign country or city such as London, Toronto, Bangalore, Dhaka, Kuala Lumpur, Beijing, Burnaby, or a region such as
   "Europe" / "EMEA" / "APAC") → false unless the location also says United States / USA / U.S. / Remote US. "Remote" alone is fine.
