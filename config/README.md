# config/ — the candidate's personal data (JSA-077, ADR-0005)

Every personal fact the agent uses lives here; the code under `skills/` and `scripts/` only reads it.
Each file has a fictional **`.example`** twin (Alex Rivera, a U.S. citizen). A fresh clone runs on the examples; copy each
one without `.example` and fill in your own facts. The public export ships only the examples.

| File | What it holds | Read by |
| --- | --- | --- |
| `profile.json` | name, contact, accounts, education, employers, work authorization, transcript path, resume template, and **`answers`**: one entry per form rule id in `skills/auto-apply/scripts/answer_rules.js` (text / yes / pick / alts / combo / date / note) | `profile.js` (Node / browser) · `jsa_profile.py` (Python) |
| `canonical.json` | the high-stakes answers checked on every form before submit (work authorization, sponsorship, school, EEO …) with accept / reject patterns | `skills/auto-apply/runner/canon.py` |
| `wd_profile.json` | Workday repeat blocks: work experience, education, languages | `skills/auto-apply/runner/run_wd.py` |
| `resume_content.py` | resume content per target role (approved wording only) | `skills/resume-updater/scripts/content.py` → `build_a.py`, `ds_materials.py` |
| `connections.json` | LinkedIn connections by company (other people's names — never publish). **`connections` = the referrer pool** (JSA-195): 1st-degree people by the company they work at now (`{"<company, lower case>": [[name, headline]]}`; optional `aliases` `{"<other name>": "<key>"}`); `alumni_link` (people who used to work somewhere) is not the pool | `skills/job-hunt-pipeline/scripts/build_jobs.py` · `connections.js` / `jsa_profile.pool()` → `answer_rules.js` referral questions (in the pool → ask you, not in it → "no referral") · embedded in `cx_bundle.js` |
| `fixtures/f1_student/` | a fictional F-1 student (profile + canonical + Workday blocks) for the F-1 / CPT tests in a fresh clone (`jsa_profile.use_fixture_if_no_user()`) | tests |
| `examples/` | the candidate's own tailoring examples (an Ashby employer, AI product) | read by people, not by code |

**Rules**
- A file is chosen in this order: environment override (`JSA_PROFILE`, `JSA_CANONICAL`, `JSA_WD_PROFILE`, `JSA_RESUME_CONTENT`) →
  `config/<file>` → `config/<file>.example`.
- After changing `profile.json` or `connections.json`, run `python3 skills/auto-apply/scripts/build_bundle.py`: `cx_bundle.js` embeds the profile
  and the referrer pool (the pre-commit check blocks the commit otherwise for the profile).
- Delete a rule's entry from `answers` and that question is left for you (status "unknown") instead of guessed.
- **`qa`** — your own question-and-answer table for questions no rule knows (ADR-0007): add entries with
  `python3 skills/auto-apply/scripts/qa_add.py --q "<question>" (--text … | --yes | --no | --pick "<option>") --source "…"`
  (`--list` shows them). Used only where no rule answers; never over a rule. Tests: `scripts/test_qa_table.py`.
- `eligibility` = `{needs_sponsorship, citizen_or_pr, grad, degree_level, intern_summer, fulltime_from}` sets what the daily
  eligibility gate blocks (JSA-081) and the prefilter's start window (JSA-087); `degree_level` = bachelors | masters | phd.
- `work_auth.restricted = true` (e.g. F-1 / CPT) makes the rules prefer "Yes, with restrictions" and never pick an
  "unrestricted / permanent / citizen" Yes.
- New facts go here, never into code (ADR-0005).

Tests: `scripts/test_profile_layer.py` (DeepSeek cases: file order, `get`, answers from a profile, restricted vs. not).

## Optional API keys
- **USAJOBS** (U.S. federal jobs, `skills/job-hunt-pipeline/scripts/usajobs_search.py`): request a free key at developer.usajobs.gov, then `export USAJOBS_API_KEY=<key>` and `export USAJOBS_USER_AGENT=<the e-mail you registered>` (macOS: or store the key in the Keychain item `jobagent-usajobs`). Without it the source is skipped.
- Work-authorization facts in `profile.json` → `eligibility` (`needs_sponsorship`, `citizen_or_pr`) decide what the gate and the scoring rule out for you: a citizen keeps citizen-only roles (clearance roles stay "review").
