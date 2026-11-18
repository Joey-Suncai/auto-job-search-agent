---
name: daily-job-refresh
description: Daily append-only refresh of the candidate's jobs list (`data/store/jobs.jsonl`) from the curated GitHub job lists (local LaunchAgent `com.jobagent.refresh`, 08:15 CT; the claude.ai scheduled task "Daily job refresh" runs in shadow until 2026-11-12). Use to check, fix, re-run or change that routine, or to run the same append by hand.
---

# Daily job refresh (append only) — verified 2026-10-25

## What runs
- **Primary (ADR-0004, from 2026-10-30): LaunchAgent `com.jobagent.refresh`**, every day 08:15 CT on his Mac → `python3 scripts/daily/run_daily.py refresh` → `append_new.py` on a temp copy of `data/store/jobs.jsonl` (perm data from `data/processed/perm_ellis.txt`), append-only check (no old row missing or changed; the old 3,000-row floor was dropped 2026-11-02 so a new user's empty store works, `perm_ellis.txt` optional), then **`board_search.search()`** (JSA-076, Joey 2026-11-02 「加进去」) adds new Lever / Ashby internships from every board linked in the store + `skills/job-hunt-pipeline/references/extra_boards.txt` (public board APIs, ~460 boards, 8 threads, 20-min cap — unfinished boards count as unreadable; no browser, no model; ids continue after the last row; a failure is logged and the GitHub rows are still saved), `store.py` check, then saves the store, commits only `data/store/` and pushes. A failure leaves the store untouched and pushes a "失败" message. Push = macOS notification + iMessage (`scripts/daily/notify.py`). Log `data/runner/daily/<date>.md` and `/tmp/jobagent_refresh.log`.
- **Shadow until 2026-11-12 (JSA-031), then disabled:** scheduled task **Daily job refresh** (`trig_01CRUirKaYh1Kfh534m8dKcm`), every day 08:15 CT, bound to his MacBook Air. Its prompt is stored in `skills/job-hunt-pipeline/daily-new-roles-prompt.md` (pre-migration copy; current: `phase2-prompts/Daily_job_refresh_local.txt` — do not edit either). It still writes the claude.ai store; compare with `~/.job-agent-venv/bin/python scripts/store/claude_export.py <dir>`.
- Script: `skills/job-hunt-pipeline/scripts/append_new.py`. Both the LaunchAgent and (since 2026-10-29) the shadow task read it from the local repo, so editing the folder copy + commit is enough.
- Data: the run touches only `data/store/jobs.jsonl`; the local page `dashboard/index.html` rebuilds within 60 s (`com.jobagent.dash`). The shadow task touches only the claude.ai `datasets/jobs` (Command Center https://claude.ai/artifact/MavpNryRBsKpTbLdBiEnbe, read-only for sessions). New rows get `"added": <date>`; existing rows are never changed or removed (`rank` is recomputed on load, never stored). Applications, companies, contacts, sources and emails are left alone.
- Inputs (local run; the shadow task uses the claude.ai jobs asset and the kit asset `pipeline/kit` instead):
  - `data/store/jobs.jsonl`;
  - `data/processed/perm_ellis.txt`, read only as data;
  - 13 public GitHub lists, cloned fresh each run (Simplify ×2, vanshb03 ×2, speedyapply ×2, zapply, Jobright DA/BA ×4, flexapply H-1B, sergyinfo H-1B).

## Run it by hand
```bash
python3 scripts/daily/run_daily.py refresh [--no-git] [--no-notify]   # same as the 08:15 run
launchctl kickstart gui/$(id -u)/com.jobagent.refresh                 # or trigger the LaunchAgent itself
```
Raw script only (debugging; does not touch the store):
```bash
mkdir -p W/prev W/raw
python3 scripts/store/store.py --export jobs W/prev/dash_jobs_prev.json
cp data/processed/perm_ellis.txt W/raw/
python3 -I skills/job-hunt-pipeline/scripts/append_new.py W   # add --no-clone to reuse W/src
cat W/out/refresh_summary.json                                # jobs, prev_jobs, new_roles, new_ab_internships, clone_failures, top_new
```
Prefer `run_daily.py refresh` for anything that should land in the store — it does the append-only check, `store.py --check`, the commit and the push. Never upload to the claude.ai dashboard (read-only until 2026-11-12).

## Verify a run
- Read the push / `data/runner/daily/<date>.md`. It reports total roles, new roles, new A/B internships and clone failures.
- `git log -1 -- data/store` shows `data: refresh <date> (…)` when roles were added; 0 new roles means correctly unchanged (nothing to commit). `python3 scripts/store/store.py --check` passes.
- Shadow (until 2026-11-12): claude.ai `datasets/jobs.updated.by` = "Claude (daily new-roles append)" with a new version; compare counts with `claude_export.py`.
- 2026-10-25 test: 13/13 clones, 5,070 roles, 0 new, because an append had already run that morning. A local re-run of the folder copy gave the same numbers.

## Pitfalls seen (2026-10-25)
- **Earlier cloud runs reported SUCCEEDED but wrote nothing.** The first versions of this task, not bound to his Mac, left no dashboard change, no debug doc and no Gmail draft. Always verify with the data (now `data/store/jobs.jsonl`; for the shadow task `datasets/jobs`) plus the run's own report, never the status alone.
- **Shadow-task prompt changes need approval** from a session linked to his MacBook Air, or an edit in the desktop app.
- **A full daily rescore was rejected.** It changes existing scores and ids. The daily run only appends; full rescoring and the Chrome sources happen in the weekly refresh (`job-hunt-pipeline`, reminder Sundays 10:43). After it, import the result into the store (`store.py --import jobs`); repacking the kit (`scripts/kit.py pack`) and updating `pipeline/kit` is shadow-only until 2026-11-12.
- **The Mac must be awake** for the 08:15 run (launchd runs a missed time after wake). The old "cloud run can't reach his folder" problem is gone: the LaunchAgent runs in the folder.
- **Deleting or pausing scheduled tasks from a session can be blocked** by the auto-mode classifier. He can do it in the app.
