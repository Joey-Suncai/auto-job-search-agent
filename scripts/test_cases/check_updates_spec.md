# Spec: pre-commit companion-file check

A commit is checked against these rules. ERROR = the commit is blocked. NOTE = printed, commit allowed.
Paths are repository-relative. Only the list of staged files and the staged/previous text of BACKLOG.md,
data/runner/results.jsonl and data/store/applications.jsonl are looked at.

0. A commit whose staged files are ALL under data/store/ always passes (daily routines). An empty commit passes.
1. If BACKLOG.md is staged and at least one row's Status changes to `done` (it was not `done` before, or the row is new
   and `done`), ROADMAP.md must be staged too — else ERROR.
2. If skills/auto-apply/scripts/answer_rules.js is staged, skills/auto-apply/scripts/cx_bundle.js must be staged — else ERROR.
   If skills/auto-apply/scripts/test/t_rules.js is not staged as well → NOTE only.
3. If skills/job-hunt-pipeline/scripts/eligibility_rules.js is staged, skills/job-hunt-pipeline/scripts/eligibility_rules_test.js
   must be staged — else ERROR.
4. Runner code = skills/auto-apply/runner/{run.py, run_wd.py, run_form.py, plan_build.py, prep_batch.py}. If any is staged,
   at least one of skills/ats-<anything>/SKILL.md or skills/auto-apply/SKILL.md must be staged — else ERROR.
   Other files in the runner folder (e.g. ladder.py, canonical.json) do not trigger this rule.
5. If data/runner/results.jsonl is staged and it gains lines with "status": "submitted", each such line's folder maps to a
   job id; that job id must appear in data/store/applications.jsonl (staged version, or the committed one if it is not
   staged) — else ERROR. A submitted line whose folder has no known job id → NOTE. Lines with other statuses are ignored,
   and lines that were already there before are ignored.
6. If any scripts/launchagent/*.plist is staged, CLAUDE.md must be staged — else ERROR.
7. If any staged file is code or a skill (*.py, *.js, *.sh, *.plist, or a file named SKILL.md) and there is no session log
   for today (skills/job-search-agent/references/session-log-<today>.md neither exists nor is staged) → NOTE only.
8. If config/profile.json is staged (the candidate's facts and form answers, JSA-077), skills/auto-apply/scripts/cx_bundle.js
   must be staged too, because the browser bundle embeds the profile — else ERROR. (Other files under config/ do not need it.)
Several ERRORs can appear at once; the commit is blocked if there is at least one.
