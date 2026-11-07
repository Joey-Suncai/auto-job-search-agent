# Contributing / developing the agent

Using the agent (collecting jobs, applying, tracking) needs none of this. This page is for changing code: a rule, a
runner, a check, a script.

## Where to work
- Work on a branch or a git worktree, never in the checkout the daily routines (LaunchAgents) run from.
- Facts never go into code: a new fact is a value in `config/` (see `config/README.md`); code only reads it.
- `scripts/test_all.sh` must pass (offline, ~2 min; CI runs the same on macOS). `.githooks/pre-commit`
  (`scripts/check_updates.py`) checks that the companion files of a change were updated too.

## How tests are written
A rule's author is the worst judge of its tests. So for any new check, rule set or script:
1. Write a short spec of what it must do (facts + expected behaviour), **not** the code.
2. Let a second model write cases from the spec only:
   `python3 scripts/ds_testgen.py --spec spec.md --format format.md --n 24 --out scripts/test_cases/<name>_cases.json`
   (DeepSeek by default — `~/deepseek/api_key`; the script is small, swap in any model you like).
3. Run them with a harness (`scripts/test_<name>.py`, examples: `test_sf_background.py`, `test_sf_done.py`).
4. Judge every disagreement yourself: fix the code, or record in `<name>_verdicts.json` why the case misreads the spec.

Answer rules (`skills/auto-apply/scripts/answer_rules.js`) also get a case in `skills/auto-apply/scripts/test/t_rules.js`,
then `python3 skills/auto-apply/scripts/build_bundle.py`.

## From the question table to a rule
Users save answers to unknown questions in `config/profile.json → qa` (`qa_add.py`). A question that keeps coming back in
many wordings is worth a real rule in `answer_rules.js` (with cases as above); then remove its table entry.

## Platform skills
One `skills/ats-<platform>/SKILL.md` per applicant-tracking system. After a batch, each new problem goes under its
**problem type**: symptom, cause, rule, and the test that enforces it — the kind of problem, not the company that showed it.
A new platform starts from `skills/ats-greenhouse/SKILL.md` as the template.

## Pull requests and releases
This repository is **generated**: each release is exported from the author's private working copy (personal data removed,
then a scan that must find nothing, then the full test suite) and lands here as one ordinary commit with a version tag.
History is never rewritten. A merged pull request is ported by hand into the private source and ships with the next
release; a change made only here would be undone by the next export.

Maintainer release steps:

```bash
git -C ~/Projects/auto-job-search-agent pull --ff-only          # take any commits made on GitHub first
python3 scripts/public/export_public.py --update ~/Projects/auto-job-search-agent --version v0.2
git -C ~/Projects/auto-job-search-agent push origin main v0.2    # the script never pushes; it prints this line
```

`--update` refuses to run when the clone is not on `main`, has local changes, is behind the remote, or the version is not
above the last tag; it commits nothing when the scan finds a personal value, a test fails, or nothing changed.

## License of contributions

The project is licensed under the PolyForm Noncommercial License 1.0.0. By opening a pull request you agree that your
contribution is licensed under the same terms **and** that the author may also license it to others under different
terms, including commercial ones (so the project can keep one license holder). If you can't agree to that, open an issue
describing the change instead.

