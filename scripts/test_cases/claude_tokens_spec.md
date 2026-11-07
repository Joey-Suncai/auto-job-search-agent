# Attributing Claude token use to job applications by time

Inputs:
- msgs: list of Claude replies {"t": local time "YYYY-MM-DDTHH:MM:SS", "total": tokens incl. cache reads, "new": new tokens}.
- results: runner log lines {"folder": application folder, "at": local time the run ENDED, "secs": run length in seconds,
  "url": job URL, "status": "submitted" | "needs-user" | "handoff" | ...}. A folder can have several runs.
  Platform from the URL: contains "myworkday" → workday, "greenhouse" → greenhouse, "lever.co" → lever, "ashbyhq" → ashby.

Rules:
1. A run window is [at − secs, at] (inclusive). A reply whose time is inside one or more run windows belongs to those
   folders, split evenly (both total and new).
2. Otherwise, if the reply is inside one or more folders' SPANS (from the start of the folder's first run to the end of its
   last run), it belongs to those folders, split evenly.
3. Otherwise it is overhead of its calendar day. A day's overhead is shared among platforms in proportion to the number of
   distinct folders that had a run (start or end) on that day. Overhead on a day with no runs is "unallocated".
4. Per platform: submitted = number of folders with at least one "submitted" line; direct_sum = [total, new] summed over
   all its folders (submitted or not); direct_median = [median total, median new] over its SUBMITTED folders' direct
   tokens (median of an even count = mean of the two middle values; null when nothing was submitted); overhead = [total, new];
   all_in_per_app = (direct_sum + overhead) / submitted, per component (null when nothing was submitted).
   All numbers are rounded to whole tokens.
5. The output also has "_unallocated": [total, new].
