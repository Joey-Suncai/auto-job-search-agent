#!/usr/bin/env python3
"""Submitted runner results → the local tracker (JSA-014).

Every `status: submitted` line in data/runner/results.jsonl becomes an Applied row in data/store/applications.jsonl
(through store.py), and the folder's open `- [ ]` lines in data/runner/queue.md are ticked. Both runners call
sync_folder() right after a confirmed submit; the CLI is the backfill / safety pass.

Rules: a row that is already Applied / Assessment / Interview / Rejected / Offer is never changed (and applied_on is never
rewritten); a Shortlisted or "Applied (unconfirmed)" row is promoted; a job with no row gets one built from the jobs store.
A folder whose job id cannot be found is reported, never guessed.

    python3 scripts/store/sync_results.py            # sync everything, print what changed
    python3 scripts/store/sync_results.py --dry-run
    python3 scripts/store/sync_results.py --manual "<folder>" [--note "…"]   # Joey submitted by hand (Lever, JSA-042)

--manual: Joey's own submit (from manual_submit.md) becomes a `status: submitted, by: joey` line in results.jsonl, then the
same sync runs for that folder (tracker row + queue ticked) and application_record.md gets a line. The folder must exist
under applications/ and have a job id; a folder already recorded as submitted gets no second line (re-running is safe).
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, HERE)
import store  # noqa: E402
import data_git  # noqa: E402  (JSA-358: the writer commits its own file)
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'scripts'))
import tiktok_slots  # noqa: E402  (TikTok / ByteDance rows carry their half-year `period`, JSA-097)

RUNNER = jpaths.data('runner')
APPS = jpaths.apps()
PROMOTE = ('Shortlisted', 'Archived', '', None, 'Applied (unconfirmed)')   # Archived = never applied (JSA-013)


def folder_job_ids(apps_dir=APPS, batches_dir=os.path.join(RUNNER, 'batches')):
    """folder → J-id from the batch files (Greenhouse) and each folder's wd_job.json / job.json (Workday)."""
    out = {}
    for p in glob.glob(os.path.join(batches_dir, '*.json')):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        for r in (d if isinstance(d, list) else d.get('jobs', []) if isinstance(d, dict) else []):
            if isinstance(r, dict) and r.get('folder') and str(r.get('id', '')).startswith('J'):
                out[r['folder']] = r['id']
    for fn in ('wd_job.json', 'job.json'):
        for p in glob.glob(os.path.join(apps_dir, '*', fn)):
            try:
                jid = json.load(open(p, encoding='utf-8')).get('id')
            except Exception:
                continue
            if str(jid or '').startswith('J'):
                out.setdefault(os.path.basename(os.path.dirname(p)), jid)
    return out


RESUME_FILE = re.compile(r'_Resume_.*_([A-Z]-[A-Za-z]+)\.(?:pdf|docx)$')


def resume_version(files):
    """Pure (tested). The résumé version (A-Classic …) named in a folder's file names, '' when none (JSA-360)."""
    for f in sorted(files or []):
        m = RESUME_FILE.search(f)
        if m:
            return m.group(1)
    return ''


def new_row(job, folder, day):
    return {'action_needed': '', 'applied_on': day, 'company': job.get('company', ''), 'cycle': 'Summer 2027' if 'intern' in (job.get('level') or '').lower() else '',
            'days_since_applied': 0, 'email_url': '', 'job_id': job['id'], 'last_checked': day, 'last_email': '暂无回应', 'last_email_date': '',
            'level': job.get('level', ''), 'next_step': 'Daily email check',
            'notes': f'Submitted by the runner {day} (results.jsonl); row added by sync_results. Record: applications/{folder}',
            'referral_status': 'Cold', 'score': job.get('score'), 'status': 'Applied', 'title': job.get('title', ''),
            'track': job.get('track', ''), 'updated': day, 'url': job.get('url', '')}


def sync(results, apps, jobs, fmap, versions=None):
    """Pure step (tested). Mutates apps; returns (changes, unknown_folders, submitted_folders). versions = {folder: résumé
    version} (JSA-360): written as `resume_version` on a row this sync creates or promotes."""
    versions = versions or {}
    jobs_by = {j['id']: j for j in jobs}
    changes, unknown, done = [], [], []
    for r in results:
        if r.get('status') != 'submitted':
            continue
        folder, day = r['folder'], (r.get('at') or '')[:10]
        done.append(folder)
        jid = fmap.get(folder)
        if not jid:
            unknown.append(folder); continue
        rows = [a for a in apps if a.get('job_id') == jid]
        if rows and all(a.get('status') not in PROMOTE for a in rows):
            continue                                              # already tracked past Shortlisted: never touched
        if rows:
            a = next(a for a in rows if a.get('status') in PROMOTE)
            a.update(status='Applied', applied_on=a.get('applied_on') or day, updated=day, last_checked=day,
                     last_email=a.get('last_email') or '暂无回应',
                     notes=(a.get('notes', '') + f' | submitted {day} (runner, synced)').strip(' |'))
            if versions.get(folder): a['resume_version'] = versions[folder]
            if tiktok_slots.counted(a): a.setdefault('period', tiktok_slots.app_period(a))
            changes.append(f'{jid} {a.get("company")}: {rows[0].get("status") or "—"} → Applied')
        elif jid in jobs_by:
            apps.append(new_row(jobs_by[jid], folder, day))
            if versions.get(folder): apps[-1]['resume_version'] = versions[folder]
            if tiktok_slots.counted(apps[-1]): apps[-1]['period'] = tiktok_slots.app_period(apps[-1])
            changes.append(f'{jid} {jobs_by[jid].get("company")}: new Applied row')
        else:
            unknown.append(folder)
    return changes, unknown, sorted(set(done))


CLOSED_STATUS = ('Applied', 'Rejected')                       # tracker statuses that end a queue line (JSA-373)


def settled_reason(files, record_text, status):
    """Pure (tested; JSA-373). Why a folder's open queue lines are moot: the tracker says Applied / Rejected, the folder holds
    a confirmation page (submitted_confirmation.png), or its application_record.md has a `## Submitted…` section (a hand
    submit). '' when none — a folder that only reached review / needs-user stays open."""
    if status in CLOSED_STATUS:
        return f'tracker {status}'
    if 'submitted_confirmation.png' in (files or ()):
        return 'confirmation page'
    if any(re.match(r'## Submitted( by\b|\s*$|\s*[(—-])', l) for l in (record_text or '').split('\n')):
        return 'application record: Submitted'
    return ''


def queue_folders(text):
    """Pure. The folder names (the **bold** token) of the open `- [ ]` lines."""
    out = []
    for line in text.split('\n'):
        if line.startswith('- [ ]'):
            m = re.search(r'\*\*(.+?)\*\*', line)
            if m and m.group(1) not in out:
                out.append(m.group(1))
    return out


def settled_folders(text, apps_dir, apps, fmap):
    """folder → reason for the open queue lines whose application is over (settled_reason on the folder's files, record and
    tracker row). A folder that does not exist under applications/ is skipped."""
    by_job = {}
    for a in apps:
        by_job.setdefault(a.get('job_id'), []).append(a.get('status'))
    out = {}
    for f in queue_folders(text):
        d = os.path.join(apps_dir, f)
        if not os.path.isdir(d):
            continue
        rec = os.path.join(d, 'application_record.md')
        try:
            rtext = open(rec, encoding='utf-8').read() if os.path.exists(rec) else ''
        except OSError:
            rtext = ''
        sts = by_job.get(fmap.get(f), [])
        st = next((s for s in sts if s in CLOSED_STATUS), None)
        why = settled_reason(os.listdir(d), rtext, st)
        if why:
            out[f] = why
    return out


def close_queue(text, folders, day=''):
    """Tick every open queue line of a settled folder. `folders` = submitted folder names, or {folder: reason} (JSA-373).
    Returns (new_text, n_closed)."""
    n = 0
    out = []
    reasons = folders if isinstance(folders, dict) else {f: 'submitted (sync_results)' for f in folders}
    for line in text.split('\n'):
        m = re.search(r'\*\*(.+?)\*\*', line) if line.startswith('- [ ]') else None
        hit = m.group(1) if m and m.group(1) in reasons else None      # the line's own folder = its first bold token
        if hit:
            line = line.replace('- [ ]', '- [x]', 1) + f' · closed: {reasons[hit]}'
            n += 1
        out.append(line)
    return '\n'.join(out), n


def run(dry=False, only=None, log=print):
    rp = os.path.join(RUNNER, 'results.jsonl')
    results = [json.loads(l) for l in open(rp, encoding='utf-8') if l.strip()] if os.path.exists(rp) else []
    if only:
        results = [r for r in results if r.get('folder') == only]
    apps, jobs = store.load('applications'), store.load('jobs')
    versions = {}
    for r in results:
        try:
            v = resume_version(os.listdir(os.path.join(APPS, r.get('folder') or '')))
        except OSError:
            v = ''
        if v: versions[r['folder']] = v
    changes, unknown, done = sync(results, apps, jobs, folder_job_ids(), versions)
    qp = os.path.join(RUNNER, 'queue.md')
    qraw = open(qp, encoding='utf-8').read() if os.path.exists(qp) else ''
    reasons = {f: 'submitted (sync_results)' for f in done}
    if not only:                                                 # the full pass also ticks folders settled by hand or by the tracker (JSA-373)
        for f, why in settled_folders(qraw, APPS, apps, folder_job_ids()).items():
            reasons.setdefault(f, f'{why} (sync_results)')
    qtext, closed = close_queue(qraw, reasons) if qraw else ('', 0)
    if not dry:
        if changes:
            store.save('applications', apps)
        if closed:
            open(qp, 'w', encoding='utf-8').write(qtext)
            data_git.commit_paths([qp], f'data: queue — {closed} line(s) closed by sync_results')   # JSA-358
    for c in changes:
        log('tracker: ' + c)
    for u in unknown:
        log(f'tracker: no job id for submitted folder {u} — add it by hand')
    log(f'sync_results: {len(changes)} tracker change(s), {closed} queue line(s) closed' + (' (dry run)' if dry else ''))
    return changes, unknown, closed


def manual_line(folder, results, url='', ats='', at='', note=''):
    """Pure (tested): the results.jsonl line for Joey's hand submit, or None when the folder is already submitted."""
    if any(r.get('folder') == folder and r.get('status') == 'submitted' for r in results):
        return None
    return {'at': at, 'folder': folder, 'url': url, 'ats': ats, 'status': 'submitted', 'by': 'joey',
            'note': note or 'submitted by Joey by hand from manual_submit.md'}


def manual(arg, note='', at=None, log=print):
    """CLI --manual: record Joey's hand submit of one folder. Returns run()'s result, or None when refused."""
    from datetime import datetime
    name = os.path.basename(os.path.normpath(arg))
    folder = os.path.join(APPS, name)
    if not name or not os.path.isdir(folder):
        log(f'--manual: no folder applications/{name} — nothing recorded'); return None
    if not folder_job_ids().get(name):
        log(f'--manual: no job id for {name} (job.json / batch file) — nothing recorded'); return None
    meta = {}
    for fn in ('plan.json', 'job.json'):
        try:
            d = json.load(open(os.path.join(folder, fn), encoding='utf-8'))
            meta.setdefault('url', d.get('url')); meta.setdefault('ats', d.get('ats'))
        except Exception:
            pass
    at = at or datetime.now().isoformat(timespec='seconds')
    rp = os.path.join(RUNNER, 'results.jsonl')
    results = [json.loads(l) for l in open(rp, encoding='utf-8') if l.strip()] if os.path.exists(rp) else []
    line = manual_line(name, results, meta.get('url') or '', meta.get('ats') or '', at, note)
    if line is None:
        log(f'--manual: {name} is already recorded as submitted — no new line')
    else:
        os.makedirs(RUNNER, exist_ok=True)
        with open(rp, 'a', encoding='utf-8') as out:
            out.write(json.dumps(line, ensure_ascii=False) + '\n')
        with open(os.path.join(folder, 'application_record.md'), 'a', encoding='utf-8') as rec:
            rec.write(f"\n## Submitted by Joey by hand {at}\n- URL: {line['url']}\n- Recorded with sync_results.py --manual"
                      + (f"\n- Note: {note}" if note else '') + '\n')
        log(f'--manual: results.jsonl line added for {name}')
    return run(only=name, log=log)


def test_data(cx, runner=RUNNER):
    """Pure (tested). True when CX_DATA points at test data — a folder other than the real data/runner (symlinks and a
    trailing slash resolved). The skills run live runners with CX_DATA=~/Projects/job-search-agent/data/runner, which is
    the real one: that is not test mode (an employer 11-04 got no tracker rows, JSA-146)."""
    if not cx:
        return False
    return os.path.realpath(os.path.expanduser(cx.rstrip('/') or '/')) != os.path.realpath(runner)


def sync_folder(folder, log=print):
    """Called by the runners right after a confirmed submit (never in test mode: CX_DATA pointing at test data)."""
    if test_data(os.environ.get('CX_DATA')):
        return None
    try:
        return run(only=os.path.basename(folder), log=log)
    except Exception as e:                                       # the submit already happened: never fail the runner here
        log(f'sync_results failed ({type(e).__name__}: {str(e)[:120]}) — run scripts/store/sync_results.py by hand')
        return None


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--manual'); ap.add_argument('--note', default='')
    a = ap.parse_args()
    if a.manual:
        sys.exit(0 if manual(a.manual, a.note) is not None else 1)
    run(dry=a.dry_run)
