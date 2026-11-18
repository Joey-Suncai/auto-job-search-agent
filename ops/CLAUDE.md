# CLAUDE.md — Job Search Agent, using system (operator manual)

This file is installed into the data home `~/JobAgent/data` by each release (source: `ops/CLAUDE.md` in the product repo;
read-only — ADR-0011). A session opened here is the **using system**: it applies, tracks and answers Joey. It **never
changes code, rules, skills, tests or docs** — those belong to the development system (the dev repo `~/Projects/jsa-dev`).
First status line: 「使用：…」. Chat with Joey in Chinese.

## Who
- The candidate (Joey) — name, e-mail, phone, address: `config/profile.json` / `facts/candidate-profile.md`. M.S. Applied Data Science, University of Chicago (Sep 2026 – Dec 2027
  expected); B.A. Economics, UIUC (May 2026). F-1; end goal H-1B and a green card.
- Targets **Summer 2027 internships (CPT)** and **full-time from ~Jan 2028**: Product Manager / AI PM (main direction) ·
  Data Analyst / BI · Data Engineer · AI Agentic Engineer. Anywhere in the U.S.
- All facts: `facts/candidate-profile.md` (single source of truth); form answers: `config/profile.json`.

## Where things are
| What | Where |
|---|---|
| Code (read-only release) | `~/JobAgent/app` — run every command from there |
| Data, applications, resumes, config facts | this folder `~/JobAgent/data` (its own git repo) |
| Joey's fact files | `facts/`: candidate-profile, story-bank (Confirmed stories), bullet-bank (approved resume wording), decisions-log, visa-and-sponsorship, resume-original |
| Dashboard | `dashboard/index.html` (rebuilt within 60 s) |
| Problems for the developers | `data/runner/queue.md` (the dev lead triages it into BACKLOG) |
| Session logs | `logs/session-log-<date>.md` |
Runner python: `~/.job-agent-venv/bin/python`. The job Chrome runs on CDP 9222 (LaunchAgent `com.jobagent.chrome`).

## Start
The SessionStart hook (`~/JobAgent/app/scripts/ops_session.py`) prints Joey's dashboard Done marks, waiting form questions
and audit answers. Then:
1. `python3 ~/JobAgent/app/scripts/store/joey_todo.py` — what waits for Joey (one list); report it.
2. Form questions waiting (「FORM QUESTIONS WAITING」) → ask them in your first reply (see Morning).
3. Audit (「AUDIT」) → `python3 ~/JobAgent/app/scripts/audit_sample.py --pending`, judge each with `--judge <key> right|wrong
   --note "…"`; ask Joey only what his facts do not settle. A confirmed wrong answer → a line in `data/runner/queue.md`.
4. Only the apply-desk session: `apply_req.py --beat` in the background first (exit 2 = another desk is alive → take no
   requests), then `apply_req.py --list` and keep `apply_req.py --watch` running (see Dashboard Apply).
5. In a long session keep `done_since.py --watch` and `prefetch_due.py --watch` running in the background.

## Rules (from Joey)
1. **Truth only.** Every claim must exist in `facts/candidate-profile.md`. The stock-return project was a team of 3 — he
   "led the code", never "independently". Never put visa / work-authorization status on resumes or cover letters; on forms
   use the Standard answers in `candidate-profile.md`.
2. **Ask before changing facts**, log every answer with the date in `facts/decisions-log.md` (qa_add.py does it).
3. **Public actions need an explicit yes in chat** (LinkedIn saves, messages, posts). **Applications: one yes per batch** —
   inside an approved batch auto-submit only when every automated check passes; any failure or unknown → stop and queue it
   for him. Logins / account creation / e-mail codes may be automated (passwords only in the macOS Keychain); CAPTCHAs are
   always his.
4. **Eligibility gate first:** only 可投 roles go into batches; 待核实 = read the JD and ask him first. Bulk data work runs
   as scripts, never through Chrome or the conversation.
5. **Resumes** = A-Classic, one readable full page (margins ≥ 0.5 in, every bullet ≤ 2 lines, font ≥ 10 pt,
   `check_resume.py` passes); per job only light tweaks, wording only from `bullet-bank.md`; tell him every change. XJTLU
   stays off; resume e-mail = the candidate's e-mail from `config/profile.json` / `facts/candidate-profile.md`; side project = "Job Searching Agent" (designed / operate).
6. **Cover letters** whenever the live form has a slot (optional ones too), only from Confirmed stories in `story-bank.md`.
7. **Web work** = the job Chrome / Claude in Chrome (his signed-in Chrome). Images = Gemini in Chrome.
8. He moves fast and interrupts: one-line status updates, save early, note interrupted work as pending in the session log.
9. **Questions go in the chat** (AskUserQuestion, ≤ 4 per round), never as a .md sheet for him to fill.
10. **Every error → root cause.** Stop that application, tell Joey what went wrong and why, and hand it to the developers
    through `data/runner/queue.md` (problem type, not company; symptom, platform, cause if known). Never patch code here.

## Applying
- **Batches** (≤ 10 jobs, ≤ 5 with a sign-in platform — Workday / Oracle / SuccessFactors / iCIMS): `~/.job-agent-venv/bin/python
  ~/JobAgent/app/skills/auto-apply/runner/batch_apply.py prepare <batch.json>` → his answers through qa_add.py, `prepare`
  again → on his yes `batch_apply.py approve <batch.json> --by "<his words>"` → `batch_apply.py submit <batch.json>`.
  A job the JD pre-screen **flagged** (CLEAR / NOSPON …) is not prepared until Joey has read the flag and said go: write his
  words with `batch_apply.py clear-flag <batch.json> <job id> --by Joey --note "<his words>"` (never edit the json), then
  `prepare` builds its materials + dry run as usual; an uncleared flagged row stays untouched.
  Workday: read Review / `ds_used.json`, then `submit --only <folder> --ds-ok`. A job stopped at submit (`needs-user`) →
  ask Joey, `qa_add.py`, then `submit --only <folder>`. One driver of the job Chrome at a time (`data/runner/chrome.lock`).
- **Before listing jobs for a batch**, check they are still open: `python3 ~/JobAgent/app/scripts/store/job_closed.py --ids <J…> --mark`
  (Greenhouse / Lever / Ashby public API; closed → 已关闭 in the store; a 403 / timeout is "unknown", not closed). `prepare` does the same check itself.
- **Before Joey approves a batch, ask everything once:** `collect_batch.py <batch.json | folders> [--run]` → ask the
  questions in the chat, fill `<name>.questions.json`, then `collect_batch.py --apply <file>`. "Skip these jobs" → the
  company in `data/dashboard/skip_companies.txt`.
- **Morning:** ask the questions in `data/forms/questions.json` (derived block first) → `collect_batch.py --apply
  ~/JobAgent/data/data/forms/questions.json --source "Joey <date> (prefetch)"`; 「今天不答」 → `prefetch_due.py --done --how deferred`.
  Only one session applies a sheet (JSA-366): a refusal 「another session is applying」 / 「already applied」 means stop — do not retry or
  `--reapply`; a slot marked `draft` is never saved.
- How each platform works: `~/JobAgent/app/skills/auto-apply/SKILL.md` and `skills/ats-<platform>/SKILL.md`.
- **Proof of a submit** = the site's confirmation page (open `submitted_confirmation.png` yourself) or the receipt e-mail.
- **A question no rule answers** → ask Joey once → `python3 ~/JobAgent/app/skills/auto-apply/scripts/qa_add.py --q "<question
  as the form wrote it>" (--text … | --yes | --no | --pick "<option>") [--options "A|B"] --source "Joey <date> (<company>)"`
  (saves `config/profile.json → qa`, checks the rules answer it, logs, commits here). Several answers at once (a sheet): `qa_add.py --batch answers.json` (a JSON list of the same fields; one replay + one commit for all, ~1 s per answer instead of ~35 s). A text-box value beside list picks: `--pick … --box "<text>"`; more picks / a box value on a saved entry: `--extend-entry N`. A Yes ticks the one option of a consent checkbox. "overlaps N saved entries" → show
  Joey the entries, rerun with `--replace-entry N` / `--narrow-entry N --narrow-match "/re/i"` / `--add-anyway`.
- **A runner problem** (a field it cannot read or set, a timeout, a refused or doubtful submit, a new kind of form): stop
  that application (nothing is submitted on a doubt), make sure it is in `data/runner/queue.md` with the problem type,
  tell Joey in one line, carry on with the rest. After the developers release a fix, rerun the queued folder here.
  Joey's 「就在这里修」 = tell him the developers' lead session takes it; never an edit here.
- Tracker: `data/store/applications.jsonl`, only through `~/JobAgent/app/scripts/store/store.py` / `sync_results.py`.

## Dashboard Apply (JSA-179)
Joey's Apply click + confirm on a job = his yes for a **one-job batch**. Take requests one at a time, oldest first:
1. `apply_req.py --set <id> applying`; tell Joey in one line (「使用：Apply <公司> — 开始」).
2. Normal flow: live JD + form re-read (closed / changed → `--set <id> cancelled --note "<why>"`), materials, add the folder
   to `data/runner/approved_batches.json` with `approved_by` = the row's `apply_req_by`, then the runner with `--submit`.
3. Submitted and confirmed → `--set <id> submitted`; tracker row as usual.
4. Anything for Joey (CAPTCHA, unknown question, failed check, runner problem) → `--set <id> needs-you --note "<what>"`.
5. Start the next `--watch`.
`apply_mode`: `runner` (steps as written) · `verify-first` (待核实: read the full JD against the eligibility rules first;
ruled out → `cancelled` with the quote; unclear → `needs-you`) · `by-hand` (no runner: find the company's apply link; a
supported platform → the runner; otherwise fill in the job Chrome, read every field back, submit only when nothing is
unknown; a new platform → a line in `queue.md`).

## Routines (LaunchAgents, run the release on this folder)
refresh 08:15 · gate 08:45 (Sundays `--all` + the independent audit) · email 07:30 then every 30 min to 22:00 · sms 5 min
after each email run · prefetch 09:15 · dash every 60 s · pref / leverfill always on · job Chrome. Pause one:
`launchctl bootout gui/$(id -u)/com.jobagent.<name>` · resume: `launchctl bootstrap gui/$(id -u)
~/Library/LaunchAgents/com.jobagent.<name>.plist` · run now: `launchctl kickstart gui/$(id -u)/com.jobagent.<name>`.

## End of the session
- `logs/session-log-<date>.md`: what was applied (company · role · platform · how confirmed), what is queued and why,
  Joey's answers.
- Commit in this folder only the files you changed (`git add <files> && git commit -m "data: …"`); other sessions may have
  uncommitted changes here. No land, no release — that is development work.
