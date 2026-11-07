# Spec: public export, personal-data scan, LaunchAgent rendering (JSA-078 / JSA-079)

## keep(path) — does a repo file go into the public tree?
- Always kept: data/processed/perm_ellis.txt, map/template.html and the three dummy test PDFs skills/auto-apply/runner/test/{app_fake,app_bad,app_notready}/resume_fixture.pdf.
- Under config/: only config/README.md, config/profile.js, config/jsa_profile.py, config/paths.py and files whose name contains ".example."
  and everything under config/fixtures/ (fictional test people)
  (e.g. config/profile.example.json kept; config/profile.json, config/resume_content.py, config/examples/x.py dropped).
- Dropped folders: applications/, data/ (except the file above), resume/, 资料/, maps/, map/, github-profile/, phase2-prompts/,
  docs/, .claude/, dashboard/, node_modules/, skills/job-search-agent/references/, skills/linkedin-updater/,
  skills/github-profile-builder/, skills/resume-updater/references/, skills/auto-apply/references/, skills/job-hunt-pipeline/references/.
- Dropped files: BACKLOG.md, ROADMAP.md, ARCHITECTURE.md, CLAUDE.md, README.md (public versions are swapped in separately),
  skills/_shared/candidate-profile.md, story-bank.md, bullet-bank.md, decisions-log.md, visa-and-sponsorship.md, prompts.md,
  skills/auto-apply/scripts/cx_bundle.js, scripts/daily/notify.json, and the author's development tools: scripts/backlog.py,
  scripts/land.py, scripts/sync_worktrees.py (+ their tests), .githooks/post-commit, .githooks/post-merge,
  scripts/store/claude_export.py, skills/daily-job-refresh/scripts/kit.py, skills/job-search-agent/SKILL.md.
- Dropped by name pattern anywhere: anything with "_bak" or "_archive" or "_before_" in the name, *.bak, and binaries/data dumps
  *.pdf *.docx *.png *.jpg *.jpeg *.tgz *.zip *.xlsx *.jsonl.
- Everything else (code, skills' SKILL.md, scripts, tests, LICENSE, setup.sh, requirements.txt, .githooks/…) is kept.

## phone_re(phone) — a regex for one phone number in any common U.S. format
Takes the last 10 digits of the input; fewer than 10 digits → None. Must match 5550102030, 555-010-2030, 555.010.2030,
(555) 010-2030, +1 555 010 2030, 1-555-010-2030; must NOT match when the 10 digits are part of a longer digit run
(e.g. 14479027580123) or a different number.

## find_hits(rel_path, text, terms) — scan one file
terms = [(label, regex)]; matching is case-insensitive unless the regex itself says otherwise. Returns one string per
(line, term) found, formatted "<rel_path>:<line number from 1>: <label>: <matched text>". A (path, label) pair in the allow
list is skipped: by default only ("LICENSE", "legal first name").

## render(template, values) — fill a LaunchAgent plist template
Replaces every {{KEY}} (KEY = upper-case letters / underscore) with values[KEY], XML-escaped (& → &amp;, < → &lt;, > → &gt;).
A placeholder whose key is missing or whose value is empty → error (ValueError). Text without placeholders is unchanged.
