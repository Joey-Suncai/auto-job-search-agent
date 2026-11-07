# Joey's to-do list — merge rules

Three ledgers record things that wait for Joey:
- the runner queue: lines `- [ ] <time> **<folder>** — <message> — <url>` (open) or `- [x] …` (done);
- human checks: JSON lines {at, folder, state: open|resolved, checks:[{question}]} — the LAST line per folder decides
  whether it is open;
- dashboard Apply requests: JSON lines {at, id (job id), status, note} — the LAST line per job id decides; only status
  `needs-you` waits for Joey.

The list has ONE row per application folder:
1. `n` = how many open entries (all three ledgers together) the folder has; the row shows the NEWEST entry's message
   (by time).
2. A folder is NOT listed (closed by itself) when: it has a `submitted` result, OR its tracker row's status is one of
   Applied / Assessment / Interview / Offer / Rejected / Archived / No response / Withdrawn, OR its job's eligibility is
   已关闭 / 不可投 / 重复. Ticked (`[x]`) queue lines and resolved checks never count.
3. A dashboard request maps to its folder through the job id; with no folder known it is listed under the job id.
4. Problem type from the row's message, first match wins, in this order: unconfirmed (no confirmation / unconfirmed /
   check Gmail) · captcha (CAPTCHA, human check, "verify you are human") · sign-in (sign in, account creation, login,
   password, one-time code) · answers (needs answers, no rule answers, unknown, question) · materials (materials,
   transcript, resume, cover letter) · gate (canonical / canon, fields not confirmed, review page lacks, not approved,
   referral) · runner error (runner error, timeout, timed out) · refused (refused, correct the errors) · otherwise other.
   A row whose newest entry is a human check is type captcha.
5. Rows are ordered by problem type in the order above, then oldest first.
