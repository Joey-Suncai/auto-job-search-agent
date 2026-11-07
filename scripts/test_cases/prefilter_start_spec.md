# Spec: prefilter START flag from the candidate's target terms (JSA-087)

start_flag(level, text, intern_summer, fulltime_from) → true when the job's start date does not fit the candidate.
intern_summer = the summer of the internship (a year, e.g. 2027); fulltime_from = earliest full-time start "YYYY-MM".
Internship (level contains "intern"): true when the text names
  - a fall / autumn / winter / spring term in the year before intern_summer or in intern_summer itself ("Fall 2026", "Spring 2027" for 2027),
  - a January, February or March date in the intern_summer year ("January 2027"),
  - "co-op" or "residency" anywhere,
  - "starting" / "start date" followed (within 30 characters) by the year before intern_summer.
  "Summer 2027" alone → false. Seasons in other years (e.g. "Fall 2028" for 2027) → false.
Full-time (any other level): true when
  - "start" / "starting" / "start date" is followed within 40 characters by a year from two years before fulltime_from's year
    up to the last year that ends 4+ months before fulltime_from, or by a month-year that is 4 or more months before
    fulltime_from but in that last partial year (for fulltime_from 2028-01: "start … 2026", "start … September 2027" → true;
    "start … October 2027", "start … January 2028", "start … 2028" → false),
  - "immediate start", "immediately start" or "ASAP".
Matching is case-insensitive.
