# Platform scorecard (JSA-045)

A function computes, per job-application platform, the numbers used to certify that platform. Inputs:
- `results`: runner log lines, each {at: "YYYY-MM-DDTHH:MM:SS", folder, url, ats (may be absent), status, and optionally
  problems (list), bad (int), failed (int), needs (int), verify_pass (bool), secs (number), deepseek {prompt, out}, by}.
- `emails`: company e-mails, each {job_id, date: "YYYY-MM-DD", type}.
- `fmap`: folder name → job id (a folder may be missing).
- `ds_cost`: folder name → materials cost in USD (missing = 0).
- `wrong`: records {folder} of wrong answers found after a submit.
- `today`: "YYYY-MM-DD".

Rules:
1. Platform of a line: url contains "greenhouse" → "greenhouse"; else contains "myworkday" → "workday"; else contains
   "lever.co" → "lever"; else contains "ashbyhq" → "ashby"; else the line's `ats` value; else "other".
2. Lines whose folder name does not start with a date and underscore (YYYY-MM-DD_) are test lines and are ignored entirely.
3. An application = a folder. A folder belongs to the platform of its earliest line (by `at`).
4. first_clean: a folder's earliest line is clean when its status is "dry-run" or "submitted", AND problems is absent or
   empty, AND each of bad, failed, needs is absent or 0, AND verify_pass is not false. first_clean_rate = clean folders / folders.
5. A folder is submitted when any of its lines has status "submitted". Its submit day = the date part of its earliest submitted line.
6. needed_joey: a submitted folder whose earliest submitted line has by = "joey" (Joey submitted it by hand), or that has
   any line before that submitted line with status "captcha" (a CAPTCHA is always solved by Joey). Lines with status
   "handoff", "unconfirmed", "blocked" or "dry-run" before the submit do NOT count: the runner or Claude recovered.
   no_joey_rate = (submitted − needed_joey) / submitted.
7. Confirmation of a submitted folder: confirmed when an e-mail has the folder's job id (from fmap), a type in
   {Confirmation, Rejection, Assessment, Interview, Offer}, and a date from the submit day through submit day + 2 days
   (inclusive). Not confirmed and today is on or before submit day + 2 days → pending (excluded from the rate).
   A folder with no job id in fmap is never confirmed (and is pending only by the date rule).
   confirm_rate = confirmed / (submitted − pending).
8. wrong_answers = number of `wrong` records whose folder is a submitted folder of the platform.
9. Runner time of a submitted folder = sum of secs over the lines that have secs. A submitted folder where no line has
   secs has no runner time (not logged) and is left out of the median. median_secs = median over submitted folders that
   have a runner time (even count: mean of the two middle values); none → null. Also output timed = how many submitted
   folders have a runner time.
10. DeepSeek cost of a submitted folder = ds_cost[folder] + sum over its lines of (deepseek.prompt × 0.28 + deepseek.out × 0.42) / 1,000,000.
    mean_ds_cost = mean over submitted folders.
11. Any rate, median or mean with nothing to compute from (denominator 0 / no submitted folders) is null.
12. Bar (each a boolean): n_ok = submitted ≥ 50; no_joey_ok = no_joey_rate ≥ 0.95; confirm_ok = confirm_rate ≥ 0.95;
    wrong_ok = wrong_answers == 0; time_ok = median_secs ≤ 300; cost_ok = mean_ds_cost ≤ 0.01. A null value fails its bar.
    certified = all six true. clean_ok = first_clean_rate ≥ 0.95 is still output, for information only — it is NOT part
    of certified.
13. Output: a mapping platform → {folders, submitted, timed, first_clean_rate, needed_joey, no_joey_rate, confirmed, pending, confirm_rate,
    wrong_answers, median_secs, mean_ds_cost, n_ok, no_joey_ok, clean_ok, confirm_ok, wrong_ok, time_ok, cost_ok, certified}.
    Platforms with no folder do not appear. Rates are fractions (0–1), not percentages.
