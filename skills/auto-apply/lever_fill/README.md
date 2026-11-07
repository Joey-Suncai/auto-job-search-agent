# Lever one-click fill (JSA-058, 2026-10-31)

Lever's hCaptcha challenges every submit from the job Chrome (10 of 10 on 2026-10-31). A CAPTCHA is always Joey's
(rule 7) and is never solved or bypassed by the agent. So: the runner fills + reads back the form in the job Chrome
(dry-run, `form_check.json`), and Joey submits in **his own Chrome** with this extension doing the typing.

## One-time setup (Joey's Edge — 2026-11-02)
The job Chrome is the only Chrome running on this Mac and it has the debugging port, so hCaptcha rejects submits there even
when Joey clicks. Lever submits go through **Microsoft Edge**, which no program controls.
1. `edge://extensions` → turn on **Developer mode** → **Load unpacked** → choose
   `~/Projects/job-search-agent/skills/auto-apply/lever_fill/extension`.
2. The local server starts at login: LaunchAgent `com.jobagent.leverfill` (`scripts/launchagent/`, log `/tmp/jobagent_leverfill.log`).
   By hand: `cd ~/Projects/job-search-agent && python3 skills/auto-apply/lever_fill/server.py`.

Since v0.2.0 the extension fills on page load (no click); pages the agent has no folder for stay untouched. `run_form.py`
opens every hCaptcha-stopped Lever page in Edge by itself.

## Per application (~30 s)
The runner opens the apply link in Edge (or open it yourself) → the extension fills it (or click **Fill from job agent**) → the panel says "all N fields + files filled and
read back" (or lists what to fix) → look at the page → **Submit** (solve a CAPTCHA yourself if one appears). On Lever's
thanks page the extension records the submit (results line `by: joey`, tracker row) and shows a green note.
If Lever shows "There was an error verifying your application": check Gmail for the company's confirmation first.

## Rules
- Serves only folders whose dry-run read back every field with no problems; refuses submitted folders.
- Never clicks Submit, never touches a CAPTCHA. Data and record requests need the header the extension sends
  (`X-Lever-Fill`), so a web page cannot read the answers or fake a submit.
- **Stands back while the runner works (JSA-083):** the extension is in the job Chrome too. While `run_form.py` owns a
  folder (`<folder>/runner_active.json`, its pid still running) the server refuses the fill and does not record a /thanks
  page — the runner records its own submit (`by: runner`). The mark is gone before an Edge hand-off, so Joey's submit there
  is recorded as before.
- Name-less fields: the Lever survey's country select is key `candidate-location` → `select.candidate-location` (JSA-075).
- After an update, reload the extension (`edge://extensions` → reload; same in the job Chrome) — v0.2.1.
- Tests: `python3 scripts/test_lever_fill.py` (DeepSeek-written cases for `server.payload`), `scripts/test_runner_owns.py`.
