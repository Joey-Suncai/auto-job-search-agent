# Spec: the "specify" box after a source list answered "Job Boards - Other" (SuccessFactors, 2026-11-05)

A SuccessFactors form asks "Please indicate how you heard about this job" (a list), followed by a text box such as
"Other or Referrer (Please specify)". When the list was answered with a job-board "Other" option — "Job Boards-Other
(specify name below)", "Job Board - Other", "Other Job Board", "Other online job board" — the text box gets the NAME of a
job board, never "N/A":

1. The job's own board when the job's record names one: its `source` value first (e.g. "linkedin", "indeed_search",
   "Built In", "handshake"), else the host of its posting URL (e.g. https://www.linkedin.com/jobs/… → LinkedIn,
   https://www.indeed.com/… → Indeed). Known boards: LinkedIn, Indeed, Glassdoor, ZipRecruiter, Monster, CareerBuilder,
   Handshake, Wellfound, Dice, Built In, Craigslist, Simplify. The answer is the board's name as written in that list.
2. Otherwise (a company career site URL, a GitHub list, an aggregator, no source) → the configured default board,
   **LinkedIn** (the configuration may give another default list, e.g. ["Indeed"]; then that one).
3. A list answer that is not a job-board "Other" option — "Other", "LinkedIn", "Employee Referral (specify below)",
   "College or University (specify name below)", "an employer Career Site", "Job Fairs (Non-University)-Specify Below",
   empty — gives no board name (none: the box keeps whatever the other rules answer).
