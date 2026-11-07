# Human-check hand-off (JSA-106) — pure functions

Human checks / CAPTCHAs on job application forms are always answered by the applicant (Joey), never by a program. These
functions only build the notification text and keep the list of checks waiting for him.

## company(folder)
- An application folder name is `<YYYY-MM-DD>_<Name_with_underscores>` (for example `2026-11-03_FHLB_Indy_Analyst`), or a path ending in such a folder.
- Returns the part after the date and the underscore that follows it, with underscores turned into spaces: `FHLB Indy Analyst`.
- A folder name without that date prefix is returned whole, underscores turned into spaces.
- The result is cut to at most 60 characters.

## message(folder, checks, parked=True) → (title, body)
- `checks` is a list of {"question": text, "options": [text, ...]}; a check with an empty or missing question is an image / widget CAPTCHA.
- The title is exactly `求职 runner：人机验证（等你）`.
- The body's first line is company(folder).
- Then, for each of the first 3 checks only (more are not shown): a line `· ` + the question with all runs of whitespace collapsed to one space, cut to 200 characters; for a check without a question the line is `· 图片 / 勾选验证（CAPTCHA）`.
- If the check has options (blank options are ignored), the next line is `  选项：` followed by up to 8 options joined with ` / `, each cut to 40 characters; when there are more than 8 options the line ends with ` …`.
- The last line tells him to finish it in the job Chrome tab: it contains `job Chrome`. With parked=True it contains `runner 已先去投下一份`; with parked=False it contains `runner 在等` instead.
- The text never contains an answer to the check: nothing is chosen, ranked or suggested among the options.

## pending(rows) → open checks
- rows are ledger events in file order: {"at": ISO time, "folder": name, "state": "open" | "resolved", ...}.
- For each folder only its LAST event counts: if it is "open" the folder is listed, if it is "resolved" it is not.
- The result is the list of those last "open" events sorted by "at", oldest first.
- An empty ledger gives an empty list.

## summary(rows) → (title, body) or None
- rows are open checks as returned by pending().
- No rows → None.
- Title: `求职 runner：<N> 个人机验证等你` with N the number of rows.
- One body line per row: `· <company(folder)> (<ats>): ` followed by the questions of its checks (whitespace collapsed, each cut to 80 characters) joined with ` | `; a check without a question, or a row with no checks, shows `CAPTCHA`.
- The body ends with a line containing `job Chrome`.
