# job_board.py — spec (2026-11-03)

A form asks "Please specify" after "How did you hear about us? = Job Board" with a list of job boards. Rule (the
candidate's own words): if the job row's source is one of the listed boards, choose it; otherwise choose LinkedIn.

Known boards and the words that name them (case-insensitive; `\s*` = optional spaces):
LinkedIn "linked\s*in" · Indeed "indeed" · Glassdoor "glassdoor" · ZipRecruiter "zip\s*recruiter" · Monster "monster" ·
CareerBuilder "career\s*builder" · Handshake "handshake" or "joinhandshake" · Wellfound "wellfound", "angel\s*list" or
"angel.co" · Dice the whole word "dice", "dice.com" or "dice_search" · Built In "built\s*in" or "builtin" ·
Craigslist "craigslist" · Simplify "simplify". Boards are tried in this order.

## board_of(source, url) → board name or null
Look at `source` (the store's source value, e.g. "linkedin", "indeed_search", "wellfound_search", null) first, then the
host part of `url` (scheme removed, everything after the first "/" dropped). The first board (in the order above) whose
words appear in the text being checked is the answer; null when neither text names a board (a company career site,
"github", "jobright.ai", null / empty values).

## board_pick(options, source, url, default) → option text or null
`options`: the list's option texts (blank ones ignored). If no option names any known board → null (it is not a
job-board list). Otherwise try, in order, the row's board (board_of(source, url)) and then `default` — a board name such as "LinkedIn", or a LIST of board names tried in order (e.g. ["LinkedIn", "Indeed"]); a name that is not a known board is skipped: the first option whose text contains that board's words is
returned (original text). null when neither is found.
