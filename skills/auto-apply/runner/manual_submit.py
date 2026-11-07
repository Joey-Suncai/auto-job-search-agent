#!/usr/bin/env python3
"""Lever hand-off sheet (JSA-042, 2026-10-31): after a clean Lever dry-run, run_form.py writes <folder>/manual_submit.md —
every answer the runner filled and read back, plus the full path of every file — so Joey can submit the form in his own
Chrome (Lever's hCaptcha mostly rejects the job Chrome). After he submits, one command records it:

    python3 scripts/store/sync_results.py --manual "<folder>"

    ~/.job-agent-venv/bin/python manual_submit.py "<app folder>"      # (re)write the sheet from plan.json + form_check.json
Rules: only Lever; only when every check passed (no problems, every field read back ok); never after a confirmed submit;
when the checks fail an old sheet is removed, so Joey never types stale answers.
"""
import json, os, re, sys

NAME = 'manual_submit.md'
LONG = 160                                     # answers longer than this (or multi-line) go into their own copy block


def cell(s):
    return re.sub(r'\s*\n\s*', ' ', str(s)).replace('|', '\\|').strip()


def sheet(plan, results, folder, job=None, day=''):
    """Pure (tested): plan.json + form_check fields → markdown text. Field order = plan order; answers = what the runner
    filled (want), files = absolute paths in the folder; fields left empty are listed as 'leave blank'."""
    job = job or {}
    name = os.path.basename(folder.rstrip('/'))
    title = ' — '.join(x for x in (job.get('company'), job.get('title')) if x) or name
    out = [f'# {title} — manual submit (Lever, {day})', '',
           f'URL: {plan.get("url", "")} — open it in your own Chrome (not the job Chrome).', '',
           'Every answer below was filled and read back by the runner in the dry-run. Type them in this order.', '',
           '| # | Field | Answer |', '|---|---|---|']
    longs, blank, files, n = [], [], [], 0
    full = {f.get('key'): f.get('label') for f in plan.get('fields', [])}   # form_check cuts labels at 90 chars
    for r in results:
        r = dict(r, label=full.get(r.get('key')) or r.get('label', ''))
        want = r.get('want')
        if r.get('type') == 'file':
            if not want:
                blank.append(r.get('label', r.get('key', '')))
                continue
            path = os.path.join(os.path.abspath(folder), want)
            files.append(path)
            n += 1; out.append(f'| {n} | {cell(r.get("label", ""))} | upload `{path}` |')
            continue
        if want is None or str(want).strip() == '':
            blank.append(r.get('label', r.get('key', '')))
            continue
        n += 1
        if len(str(want)) > LONG or '\n' in str(want):
            longs.append((n, r.get('label', ''), str(want)))
            out.append(f'| {n} | {cell(r.get("label", ""))} | see answer {n} below |')
        else:
            out.append(f'| {n} | {cell(r.get("label", ""))} | {cell(want)} |')
    for i, lab, txt in longs:
        out += ['', f'## Answer {i} — {cell(lab)}', '', '```', txt, '```']
    if files:
        out += ['', '## Files', ''] + [f'- `{p}`' for p in files]
    if blank:
        out += ['', '## Leave blank', ''] + [f'- {cell(b)}' for b in blank]
    out += ['', '## After you click Submit', '',
            '- If the page says the application was submitted (or a confirmation e-mail arrives), record it:', '',
            '```bash', f'cd ~/Projects/job-search-agent && python3 scripts/store/sync_results.py --manual "{name}"', '```', '',
            '- If Lever shows "There was an error verifying your application": check Gmail for the company\'s confirmation '
            'first — it may have gone through. Retry only when no confirmation arrives (a blind retry can send a duplicate).', '']
    return '\n'.join(out)


def should_write(ats, problems, results, status):
    """Pure (tested): a sheet only for a Lever form whose checks all passed and that is not already submitted."""
    return ats == 'lever' and status != 'submitted' and not problems and bool(results) and all(r.get('ok') for r in results)


def write(folder, plan, results, problems, status, day, log=print):
    p = os.path.join(folder, NAME)
    if not should_write(plan.get('ats'), problems, results, status):
        if plan.get('ats') == 'lever' and status != 'submitted' and os.path.exists(p):
            os.remove(p); log(f'{NAME} removed — the checks did not pass, its answers may be stale')
        return None
    try:
        job = json.load(open(os.path.join(folder, 'job.json'), encoding='utf-8'))
    except Exception:
        job = {}
    open(p, 'w', encoding='utf-8').write(sheet(plan, results, folder, job, day))
    log(f'{NAME} written — Joey submits by hand, then: python3 scripts/store/sync_results.py --manual "{os.path.basename(folder)}"')
    return p


if __name__ == '__main__':
    f = os.path.abspath(sys.argv[1])
    pl = json.load(open(os.path.join(f, 'plan.json'), encoding='utf-8'))
    fc = json.load(open(os.path.join(f, 'form_check.json'), encoding='utf-8'))
    print(write(f, pl, fc['fields'], fc.get('problems'), 'dry-run', (fc.get('at') or '')[:10]) or 'no sheet (checks did not pass or not Lever)')
