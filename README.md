# auto-job-search-agent

A job-search agent that runs on your Mac: it collects internship and new-grad postings every morning, reads every job
description to decide whether you can actually apply, keeps a local dashboard, and fills in application forms
(Greenhouse, Workday, Ashby, Lever, and more in beta) from **your** verified facts. It only submits inside a batch you approved, and only
when every automated check passes.

Built for international students (F-1 / CPT / OPT) but works for anyone. You drive it with
[Claude Code](https://claude.com/claude-code); the daily routines run without any model.

> **Status: v0.1 (November 2026).** Used by its author for about 300 real applications. macOS only. Expect rough edges.

## What it does

| Stage | What happens | Model? |
| --- | --- | --- |
| **Collect** (daily 08:15) | 13 curated GitHub internship lists + ~460 Lever / Ashby job boards via their public APIs, append-only into `data/store/jobs.jsonl` | no |
| **Check eligibility** (daily 08:45) | reads every new job description: sponsorship, citizenship / clearance, degree level, start date, closed postings, duplicates → 可投 eligible / 待核实 review / 不可投 not eligible / 已关闭 closed / 重复 duplicate | no |
| **Dashboard** | `dashboard/index.html`, rebuilt within 60 s of any data change | no |
| **Materials** | resume tailored lightly from **your approved wording only**, cover letter only when the form takes one | DeepSeek (optional) |
| **Fill forms** | the runners fill the real form over Chrome DevTools, read every field back, check high-stakes answers (work authorization, sponsorship, EEO) against your profile | rules first; DeepSeek / Claude only for open questions |
| **Submit** | only inside a batch you approved, only when every gate passes; anything unknown stops and asks you | no |
| **Track** | reads job e-mail (Gmail, read-only) and texts (Messages, read-only) and updates each application's status | Claude (optional) |

Platforms (author's submitted applications, Nov 2026):

| Platform | Status | Submitted |
| --- | --- | --- |
| Greenhouse | stable | 55 |
| Workday | stable (tenants differ a lot; stops at Review when anything is unexpected) | 60 |
| Ashby | stable | 52 |
| Lever | the agent fills the form, **you click Submit** in your own browser (Lever's hCaptcha rejects automated browsers) | 30 |
| SAP SuccessFactors · SmartRecruiters · Oracle Recruiting Cloud · Workable | beta | 3–6 each |
| iCIMS · TikTok / ByteDance | fill and read back only; you press the final button | — |

## Safety rules (built in)

- **Truth only.** Every answer comes from your `config/` files. Nothing is invented; unknown questions stop and ask you.
- **One approval per batch.** No submit outside a batch you approved; a failed check stops that application.
- **CAPTCHAs are yours.** The agent never solves or bypasses a CAPTCHA and never disguises the browser.
- **Passwords stay in the macOS Keychain.** Scripts read them at the moment they type them; no model sees them.
- **Read-only mail.** The e-mail and text readers never send, move or mark anything.

You are responsible for following each job site's terms of use.

## Install (macOS)

Needs: macOS, Python ≥ 3.10, git, Google Chrome. Optional: Node 18+, LibreOffice (resume PDFs), a DeepSeek API key,
an Anthropic API key.

```bash
git clone https://github.com/Joey-Suncai/auto-job-search-agent.git
cd auto-job-search-agent
./setup.sh --smoke
```

`setup.sh` creates a venv (`~/.job-agent-venv`), installs the packages, copies the `config/*.example.*` files to your own
copies, enables the git hooks, checks the Keychain items and runs an offline smoke test. It never overwrites your files.

1. **Fill in your facts.** Edit `config/profile.json` (name, contact, education, work authorization, and `answers`: one entry
   per standard form question), `config/canonical.json`, `config/wd_profile.json`, `config/resume_content.py`.
   See [`config/README.md`](config/README.md). The examples describe a fictional person, Alex Rivera.
2. **Add the secrets you need** (the setup output prints the exact commands), e.g. a Gmail app password:
   `security add-generic-password -s jobagent-gmail -a you@gmail.com -w`
3. **Start the daily routines:** `./setup.sh --agents --load` (LaunchAgents: refresh 08:15, eligibility 08:45, e-mail 07:30 then every 30 min until 22:00,
   texts 5 minutes after each e-mail check, dashboard and the job Chrome always on). Check with `python3 scripts/launchagent/install.py --check`.
4. **Open Claude Code in this folder** and say what you want ("show me eligible AI PM internships", "prepare a batch of
   five Greenhouse applications"). `CLAUDE.md` tells the agent how the pieces fit and which rules to keep.

## Costs

The daily routines are free (public APIs, no model). Form filling is rule-based; open questions use DeepSeek at about
**$0.003–0.006 per application**. Claude is used through your own Claude Code plan and, optionally, the Anthropic API for
reading job mail.

## Layout

```
config/        your facts + form answers (the only personal data; every file has a fictional .example)
skills/        one SKILL.md per job (auto-apply, ats-<platform> for each applicant-tracking system, resume-updater, …) + scripts
scripts/       daily/ (routines) · store/ (data layer) · dashboard/ · launchagent/ (plist templates) · public/ (export) · tests
data/store/    your jobs, applications, e-mails (created on first run, git-ignored here)
```

## Using vs. developing

Using the agent needs no tests and no second model: the daily routines and the form rules run on their own, and a
question the rules cannot answer stops that application and asks you. Your answer is saved with `qa_add.py` into
`config/profile.json → qa`, so the next form that asks the same question is answered without you. Changing the code is a separate kind of session
with its own rules (tests written by a second model from the spec, `scripts/test_all.sh`) — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Limits

- macOS only (launchd, Keychain, Messages). No Windows / Linux yet.
- Lever: the last click is yours (hCaptcha).
- Workday tenants vary; the runner stops at Review whenever something is unexpected.
- The eligibility rules are written for U.S. internships / new-grad roles.

## Contributing and releases

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). This repository is generated from the
author's private working copy; each release is one ordinary commit with a version tag, and history is never rewritten.

## License

[PolyForm Noncommercial 1.0.0](LICENSE): free to use, study, change and share for personal, research, educational and other
noncommercial purposes. Commercial use needs a separate license from the author — open an issue. This makes the project
source-available rather than OSI "open source". Third-party parts keep their own licenses ([NOTICE](NOTICE)). Not affiliated
with any job board or applicant-tracking system.
