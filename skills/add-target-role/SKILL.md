---
name: add-target-role
description: Adds a new target role (e.g. Data Analyst) to the candidate's job search end to end — new track in the job pipeline, role-specific sources, refreshed dashboard and tracker, and two tailored resumes. Use when he says "also add <role>" or "加上 <role> 这个方向".
---

# Add a target role (proven 2026-10-23 with Data Analyst — he said 顺利)

Inputs: the role name (e.g. "Data Analyst"). Outputs: new track in `build_jobs.py`, refreshed store `data/store/` and local dashboard `dashboard/index.html`, tracker rows for the role, `resume/<YYYY-MM>/<First>_<Last>_Resume_<Role>_{A-Classic,B-Modern}.{docx,pdf}`, updated skills/logs, all committed to `/Users/you/Projects/job-search-agent/`.
Details for every step live in `job-hunt-pipeline/SKILL.md` (§1–§4) and `resume-updater/SKILL.md`; this file is the order that worked.

## Steps
1. **One-line status**, then a task list (collect · score · dashboard · resumes · skills).
2. **GitHub lists** (container `…/scratchpad/jobs/src/`): fresh `git clone --depth 1` into `src_new/`, swap directories, keep the old copy as `src_<date>/`. Never `git pull` (shallow clones fail) and never `git fetch` + `reset --hard` (he rejected it). Look for role-specific lists (for DA: `jobright-ai/2026-Data-Analysis-{New-Grad,Internship}`, `jobright-ai/2026-Business-Analyst-{New-Grad,Internship}`).
3. **Chrome collection** (Claude in Chrome):
   - ATS boards from an example.org tab with the new titles added to the title regex → download `jsa_ats_and_hn_<MMDD>.json`.
   - LinkedIn: 6–8 role queries (intern + new grad), rows labelled `<ROLE>-intern` / `<ROLE>-ft` → download `jsa_linkedin_<role>.json`.
   - Built In: role queries via in-page `fetch('/jobs?search=…&country=USA&allLocations=true&page=N')`, keep intern/entry/junior rows not already collected.
   - Handshake visa-open filter: usually already covered by the "data" query — one check query is enough.
   - Downloads: one automatic download per site, and the limit **persists across days**. When blocked, put rows in `window.__X` as `id|title|company|loc|salary|posted|level` lines, read 950-char slices with `javascript_tool`, Write them to `raw/<source>_<MMDD>.txt`.
   - Downloads land in `~/Downloads/jsa_*.json` → `device_bash` copy to `data/raw/<date>/` → `device_stage_files` → container `raw/`.
4. **`build_jobs.py`**: add `("<Role>", regex)` to `TRACKS` in the right priority slot (DA sits after Data Engineer, before Product Manager) and to `TRACK_W` (25); parse the new lists (Jobright: "↳" = previous company; dates "Oct 23"); load the new raw files; set `force_track` on rows from role searches, applied only when the **stripped title** is role-type and not scientist/quant/engineer/researcher. Rerun, then sample 30 random titles of the new track and the top 25 rows and fix leaks before moving on.
5. **`export_dash.py`**: add the track to `TRACK`, add `META` rows for new sources, set `last_run`. Export the live tracker first: `python3 scripts/store/store.py --export applications out/dash_applications_prev.json` — the export keeps his tracker rows (re-matched on company + title) and appends the top 15 tier A/B roles of the new track (≤2 per company).
6. **Dashboard**: edit the method text in `skills/job-hunt-pipeline/scripts/dashboard_index.html` (tracks are data-driven, nothing else changes). Import the 5 outputs into the store — `python3 scripts/store/store.py --import <jobs|companies|contacts|sources|applications> out/dash_<name>.json` (one call each) — then `python3 scripts/store/store.py --check` and commit + push `data/store/`. `scripts/dashboard/build_dash.py` (`com.jobagent.dash`) rebuilds `dashboard/index.html` within 60 s. No uploads: the claude.ai dashboard is read-only until 2026-11-12, then retired.
7. **Resumes** (`resume-updater`): add `ROLES["<Role>"]` to `content.py` using only facts from `candidate-profile.md`, plus a `HEADLINES` entry in `build_a.py`. Build A + B, `soffice` → PDF, `fill.py` (target 1 page, bottom ≈ 741–758). To balance the two styles without changing facts, use `skills_a` (A-only skill lines), `lead_short_b`, and `drop_b`. Look at both renders. Remove any claim that isn't in the profile.
8. **Deliver**: `SendUserFile` the 2 PDFs + 2 DOCX; copy outputs, scripts and data to `/mnt/user-data/outputs/job-search-agent/…`; update `job-hunt-pipeline`, `resume-updater`, `CLAUDE.md`, `job-search-agent/SKILL.md`, `candidate-profile.md`, `decisions-log.md`, session log; `device_commit_files` everything.
9. **Report** in his language: role counts by level/tier, top roles, dashboard/tracker changes, resumes, anything left out.

## Verify at the end
- New track appears in the dashboard Track filter; tracker row count = old + new.
- Both resumes are 1 page, fill target met, no unverified claims.
- `device_commit_files` returned no rejections.

## 2026-10-23 numbers (Data Analyst)
31,721 raw rows from 20 sources → 12,388 roles; DA 1,248 (537 intern, 442 new grad; A 23, B 160); tracker 40 → 55; resumes DA-A bottom 741, DA-B 756.

## Example: AI Product Manager (2026-11-03)
A split, not a new field: the track goes FIRST in every `TRACKS` list (complete_jobs.py, append_new.py, build_jobs.py) with a two-part pattern (an AI word AND a PM word), plus `TRACK_W` / `TRACK_LBL` / `export_dash.TRACK`, the runners' track → resume maps (→ Product_Manager resume) and `cert_supply.track_of`; existing rows re-tracked through store.py; tests `scripts/test_track_aipm.py` (DeepSeek 24). Scoring already treats AI PM as the top value (`features.role_category` = ai_pm), so scores do not change.
