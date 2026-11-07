# CLAUDE.md — job-search agent

This folder is the user's job-search agent. Read this file first, then `config/README.md` (where the user's facts live),
then `skills/auto-apply/SKILL.md` before any application work. Talk to the user in their language; files stay in English.

## Where things are
- `config/` — the user's facts and form answers (`profile.json` → `answers`), high-stakes answers (`canonical.json`),
  Workday blocks (`wd_profile.json`), resume content (`resume_content.py`). **New facts go here, never into code.**
  After editing `profile.json` run `python3 skills/auto-apply/scripts/build_bundle.py`.
- `data/store/*.jsonl` — all data (jobs, applications, e-mails). Change it only through `scripts/store/store.py`.
- `dashboard/index.html` — the local dashboard (rebuilt automatically).
- `skills/<name>/SKILL.md` — how each job is done: `auto-apply` (orchestrator), one `ats-<platform>` per applicant-tracking
  system (greenhouse, workday, ashby, lever; beta: successfactors, smartrecruiters, oracle, workable, icims, tiktok),
  `job-hunt-pipeline` (collection + eligibility gate), `daily-job-refresh`, `resume-updater`, `cover-letter-writer`,
  `add-target-role`.
- Daily routines (LaunchAgents, no model): refresh 08:15 → eligibility gate 08:45 → e-mail 07:30 then every 30 min → texts 5 min after each; dashboard,
  map and the job Chrome (CDP port 9222) always on. Install / check: `python3 scripts/launchagent/install.py [--check|--load]`.

## Two kinds of session: using and developing
**Using** (most sessions: collect, pick a batch, apply, track) **never changes code** and needs no test work and no second
model. **Developing** (changing a script, a rule or a runner) happens in its own session on its own branch, with tests.
When a using session hits something the code cannot handle, it does not fix the code on the spot: it stops that one
application, writes the problem to `data/runner/queue.md` and tells the user; the fix is a development session.

## Rules for using the agent
1. **Truth only.** Every claim on a form, resume or letter must exist in `config/`. Never invent a fact, number, story or
   motivation; report the gap and ask the user. Log the user's answer (with the date) and put the fact into `config/`.
2. **Eligibility gate first.** Only jobs the gate marks 可投 (eligible) go into a batch; 待核实 (review) means read the job
   description and ask the user. Re-read the live posting before filling a form.
3. **One approval per batch.** The user approves a batch in chat; inside it, submit only when every automated check passes.
   Any failure or unknown → stop that application and ask.
4. **CAPTCHAs, passwords and anything that speaks for the user in public are the user's.** Never solve or bypass a CAPTCHA,
   never disguise the browser, never type a password a script does not read from the Keychain, never post or message
   without an explicit yes.
5. **Resumes:** light, job-specific tweaks only, wording only from the user's approved bullets; tell the user every change.
6. **Bulk data work runs as scripts**, not through the browser or the conversation (token cost).
7. **A submit counts only with proof:** the site's confirmation page (look at the saved screenshot) or its receipt e-mail.
   A form that thanks the candidate before Apply is not a confirmation.
8. **A question the rules cannot answer** → ask the user once, then save the answer with
   `python3 skills/auto-apply/scripts/qa_add.py --q "<question as the form wrote it>" (--text … | --yes | --no | --pick "<option>") --source "<who, date>"`.
   It goes into `config/profile.json → qa`, and every later form with that question is answered automatically — no code
   change, no test. A runner that misbehaves is not fixed in a using session: stop that application and tell the user.

## Rules for developing the agent
Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first. In short:
9. **Work on a branch / worktree**, never in the copy the daily routines run from; `scripts/test_all.sh` must pass before
   a commit.
10. **Tests are written by a second model from the spec, never from the code** (`scripts/ds_testgen.py`; DeepSeek by
    default, any other model works), and every disagreement gets a recorded verdict.
11. **After an application batch** add each new problem to its problem type in `skills/ats-<platform>/SKILL.md`:
    symptom, cause, rule, and the test that enforces it. Record the kind of problem, not which company showed it.

## Commands
```bash
./setup.sh --smoke                                   # (re)check the install
scripts/test_all.sh                                  # all offline tests
python3 scripts/daily/run_daily.py refresh --no-git  # run the morning collection by hand
python3 scripts/launchagent/install.py --check       # installed routines match the templates?
```
