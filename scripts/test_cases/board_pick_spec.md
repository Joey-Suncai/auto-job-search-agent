# Spec: picking new Lever / Ashby internships for the store (board_search.py, JSA-076)

Three pure Python functions.

## known(rows) -> (keys, boards, ab)
`rows` = list of store job dicts with optional keys `url`, `ats_url`, `company`, `tier`, `tier_orig`.
- `keys`: set of posting UUIDs (lower-case, pattern 8-4-4-4-12 hex) found in `url` or `ats_url`.
- `boards`: dict {(kind, board): company}. A URL `https://jobs.lever.co/<Site>/...` (also `jobs.eu.lever.co`) gives ('lever', site lower-case);
  `https://jobs.ashbyhq.com/<Org>/...` gives ('ashby', org lower-case) except org 'api' or 'embed'. The first row's company wins.
- `ab`: set of lower-case company names whose `tier` or `tier_orig` is 'A' or 'B'.

## pick_new(keys, ab, results) -> list
`results` = list of `(((kind, board), company), data)`. `data` is the raw board API response or None (unreadable → skipped).
- Lever data: a list of postings `{id, text (title), categories: {location}, hostedUrl, createdAt (ms epoch)}`.
- Ashby data: `{jobs: [{id, title, location, jobUrl, publishedAt, isListed}]}`; isListed False → dropped.
Skip the whole board when company.lower() is in `ab`. A posting is kept when its id is non-empty, not in `keys`, and the title is an
internship for summer / 2027 located in the U.S. (titles with "Intern"/"Internship" and a U.S. city or "Remote" pass; titles without
intern, or a location like "London", "Toronto", "Dhaka, Bangladesh", "Europe" fail). Postings whose title matches a data / analytics /
AI / ML / product / BI / quant / statistics word sort first and get tier 'C'; others tier 'D'. At most 2 postings per company across all
its boards; the same posting id is never output twice. Output dicts: {id, title, location, url, posted, company, kind, tier}.

## to_rows(new, rows, today) -> list
Turns picked postings into store rows. Ids are 'J' + 5-digit zero-padded numbers continuing after the largest existing numeric
'J…' id in `rows` (no J ids → J00001). Fields: company, title, location, url and ats_url (= posting url), tier, score 45 for C and 35 for D,
level 'Internship', added = today, source '<kind>_search', posted, track 'Data Sci / Analytics' for C else 'Other',
score_note '<kind>_search default (tier median)'.
