# job_closed — closed postings are written back to the store (JSA-417)

A posting found closed must not stay 可投 in the store. Two pure functions decide; one pure function writes the mark.

## 1. gh_verdict(statuses)
Greenhouse single-job API, one HTTP status per host tried (US and EU host, same board and job id). Returns "open", "closed" or "unknown".
- Any status 200 → "open".
- Otherwise every status is 404 or 410 (and the list is not empty) → "closed".
- Anything else — 403, 429, 5xx, 0 (network error / timeout), or a mix of 404 and an error — → "unknown". An error is never "closed".

## 2. board_verdict(status, body, job_id, platform)
Lever (`platform` "lever": the board is a JSON list of postings, each with `id`) and Ashby (`platform` "ashby": a JSON object
with `jobs`, a list of postings each with `id`). `body` is the response text.
- status not 200 (403, 404, 429, 5xx, 0 …) → "unknown": a board that cannot be read says nothing about the job. (A 404 on the whole board is a wrong slug, not a closed job.)
- status 200 and the body is not valid JSON, or not the expected shape (Lever: not a list; Ashby: no `jobs` list) → "unknown".
- status 200, the list contains a posting whose `id` equals job_id → "open".
- status 200, a valid non-empty list without that id → "closed".
- status 200, a valid but EMPTY list → "unknown" (an empty board is more likely an outage than every job closing).
- ids compare as exact strings.

## 3. mark_closed_row(row, why, source, today)
Mutates the store row dict and returns True when it changed anything, else False. The row is never deleted.
- row elig is "可投", "待核实", empty or missing → elig "已关闭"; elig_base "已关闭"; elig_checked today; elig_reason is a Chinese text that contains today's date, the source and why;
  elig_closed = {"at": today, "why": why, "source": source}; tier_orig is set to the old tier when the row has none yet; tier "Blocked". Returns True.
- row elig already "已关闭" → nothing changes (the first date and reason stay), returns False.
- row elig "不可投" or "重复" → nothing changes, returns False (a stronger verdict stays).
- why is cut to 200 characters.
