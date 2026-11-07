# wellfound_search.py — spec (JSA-108)

Wellfound job-search result cards become job rows. Each card is read from the page as
`{"href": ..., "text": ..., "company": ..., "parts": [...]}`; `today` is a date (in the cases: 2026-11-03).

## job_id(href) → str
The numeric id right after `/jobs/` in a relative Wellfound path or a full wellfound.com URL:
"/jobs/4897782-research-engineer-intern" → "4897782"; "https://wellfound.com/jobs/123-x?ref=a" → "123".
Anything else (no `/jobs/<digits>`, `/jobs/abc`, empty, None, another site's URL such as
"https://example.com/jobs/55") → "".

## posted_date(text, today) → str
Reads a "posted … ago" phrase, case-insensitive, and returns the ISO date that many units before `today`:
"POSTED 6 DAYS AGO" → today − 6 days; units minute / hour → today; day = 1, week = 7, month = 30, year = 365 days;
singular or plural units; the count may be a number or "a" / "an" / "one" (= 1). "Posted today" / "posted just now" →
today; "posted yesterday" → today − 1. No such phrase (e.g. "RECRUITER RECENTLY ACTIVE", "", None) → "".

## parse_card(rec, today) → dict | None
None when the card has no job id (job_id(href) == ""), no title, or an empty / missing company.
Otherwise {"job_id", "company", "title", "location", "posted", "url"}:
- Lines: `parts` (a list of strings, blanks dropped) when it is non-empty, otherwise `text` split on newlines (blank
  lines dropped). Every line is trimmed.
- HTML entities in `parts`, `text` and `company` are decoded first ("AI &amp; Data" → "AI & Data").
- title = the first line; company = `company` trimmed.
- posted = posted_date() of the line that starts with "posted" (any case), "" if there is none.
- A line that is all upper case and contains a space (a badge such as "RECRUITER RECENTLY ACTIVE") is ignored.
- Location: on each other line, a leading work mode "In office", "Remote", "Hybrid", "Onsite" or "On-site"
  (any case, with or without a following space) is removed; then everything from the first "$", "€", "£",
  "No equity" or a percentage such as "0.5%" onward is removed; what is left (trimmed), if not empty, is a location.
  With `parts`, every such location is kept, in order, without repeats, joined with "; ". With `text` only the first one.
  If there is no location and some line's work mode was "Remote", location = "Remote"; otherwise "".
- url = "https://wellfound.com" + href when href is relative, the href itself when it starts with http; in both cases
  anything from "?" onward is removed.

Examples (text only): "Product Management Intern\nIn officeNew York City$100k – $110k\nPOSTED 2 MONTHS AGO" →
location "New York City", posted today − 60 days. "Analyst Intern\nIn officeSeattleNo equity\nRECRUITER RECENTLY ACTIVE\n
POSTED 1 WEEK AGO" → location "Seattle". With parts ["BA Intern", "In office", "Illinois", "Downers Grove",
"POSTED 7 DAYS AGO"] → location "Illinois; Downers Grove".

## pick_new(cards, ids, pairs) → list
`cards` are parse_card() results in page order; `ids` = Wellfound job ids already in the store; `pairs` = set of
(normalised company, title key) already in the store. A card is dropped when its job_id is in ids (or was taken earlier
in this call), its (normalised company, title key) pair is in pairs (or was taken earlier), or it is not a kept card
(same rule as indeed_search.keep_card: a data / analytics / BI / product / AI title, not senior, not clearly outside the
U.S., and a Summer-2027-style internship or 2027/2028 new-grad title). At most 2 cards per normalised company are taken.
Normalised company: lower case, "&" → "and", punctuation removed, words like inc / llc / corp / company / ltd / group /
technologies / labs / global / the removed. Title key: lower case, brackets, years, "summer", "intern(s)",
"internship(s)", "new grad", "remote", "us", "usa" removed, punctuation → spaces.
