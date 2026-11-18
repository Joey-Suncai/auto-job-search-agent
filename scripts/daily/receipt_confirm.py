#!/usr/bin/env python3
"""Async receipt confirmation (JSA-193 step 8, 2026-11-17).

A Submit whose page shows no confirmation is recorded `unconfirmed` (results.jsonl). This job — called by email_check.py on
every run, or by hand — looks for each such application's company receipt e-mail (gmail_code.find_mail, Gmail read-only) since
its Submit click: found → a `submitted` results line (confirmed_by: email) + the application_record.md section + the tracker
row (sync_results) + the Joey to-do entry closed; none for 48 hours → one queue line asks Joey to check the site.

    python3 scripts/daily/receipt_confirm.py [--dry-run] [--days 7]
"""
import json, os, re, sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))

CLOSING = {'submitted', 'already-submitted'}


def _when(s):
    try:
        d = datetime.fromisoformat(str(s))
        return d if d.tzinfo else d.astimezone()
    except (TypeError, ValueError):
        return None


def open_unconfirmed(rows, now, days=7):
    """Pure (tested). The last `unconfirmed` row of every folder that is still open: no submitted row after it (a later blocked / needs-user row changes nothing), not a dry run, ≤ `days` old; oldest first."""
    last = {}                                          # folder → its last unconfirmed row; a submitted row after it closes the folder
    for r in rows or []:
        if not isinstance(r, dict) or r.get('mode') == 'dry-run' or _when(r.get('at')) is None or not r.get('folder'):
            continue
        if r.get('status') in CLOSING: last.pop(r['folder'], None)
        elif r.get('status') == 'unconfirmed': last[r['folder']] = r
    out = [r for r in last.values() if now - _when(r['at']) <= timedelta(days=days)]
    return sorted(out, key=lambda r: _when(r['at']))


def receipt_decision(at, subject, now, hours=48):
    """Pure (tested). 'confirm' (a receipt e-mail was found) | 'joey' (none for ≥ `hours`) | 'wait'."""
    if subject and str(subject).strip():
        return 'confirm'
    return 'joey' if now - _when(at) >= timedelta(hours=hours) else 'wait'


def company_of(folder_path):
    for fn in ('wd_job.json', 'job.json', 'plan.json'):
        try:
            c = str(json.load(open(os.path.join(folder_path, fn), encoding='utf-8')).get('company') or '').strip()
            if c: return c
        except (OSError, ValueError):
            pass
    return ''


def title_of(folder_path):
    import gmail_code; return gmail_code.folder_meta(folder_path, 'title')


def run(runner=None, apps=None, finder=None, now=None, dry=False, days=7, log=print, sync=None, close=None):
    """Returns {'confirmed': [...], 'joey': [...], 'waiting': [...]}. `finder(since, company, role=, exclude_folder=)` → subject | None (default: Gmail read-only).
    Safeguards (JSA-193 review): one run at a time (flock); the mailbox is asked only while the Submit is < 48 h old (later: Joey);
    a company with two open folders confirms none by itself (one mail could belong to either); a mail error is never 'no receipt'."""
    import fcntl, socket
    runner = runner or jpaths.data('runner'); apps = apps or jpaths.apps(); now = now or datetime.now().astimezone()
    if finder is None:
        import gmail_code; finder = gmail_code.find_mail
    if sync is None:
        import sync_results; sync = lambda name: sync_results.run(only=name, log=log)
    if close is None:
        import joey_todo; close = joey_todo.close
    res = {'confirmed': [], 'joey': [], 'waiting': []}
    os.makedirs(runner, exist_ok=True)
    lock = open(os.path.join(runner, '.receipt_confirm.lock'), 'w')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: log('receipt_confirm: another run is active — skipped'); return res
    old_to = socket.getdefaulttimeout(); socket.setdefaulttimeout(30)          # a hung IMAP socket must not stall the mail check
    try:
        rp = os.path.join(runner, 'results.jsonl')
        rows = [json.loads(l) for l in open(rp, encoding='utf-8') if l.strip()] if os.path.exists(rp) else []   # read under the lock
        qp = os.path.join(runner, 'queue.md')
        todo = open_unconfirmed(rows, now, days)
        company = {r['folder']: company_of(os.path.join(apps, r['folder'])).lower() for r in todo}
        for r in todo:
            name, fp = r['folder'], os.path.join(apps, r['folder'])
            fresh = now - _when(r['at']) < timedelta(hours=48)
            shared = bool(company[name]) and sum(1 for x in todo if company[x['folder']] == company[name]) > 1
            subj, err = None, False
            if fresh and company[name] and not shared:
                try: subj = finder(_when(r.get('submit_at') or r['at']) - timedelta(seconds=30), company_of(fp), role=title_of(fp), exclude_folder=name)   # JSA-390: this job's role words, siblings except itself
                except Exception as e: err = True; log(f'{name}: e-mail check failed ({type(e).__name__}) — tried again next run')
            if shared: log(f'{name}: another open application at {company_of(fp)} — not confirmed by e-mail (one mail could be either)')
            d = receipt_decision(r['at'], subj, now)
            if err and d == 'joey': d = 'wait'                                  # a mailbox error is not proof of no receipt
            if d == 'confirm':
                log(f'{name}: receipt e-mail "{str(subj)[:80]}" → submitted (confirmed_by email)'); res['confirmed'].append(name)
                if dry: continue
                line = {'at': now.isoformat(timespec='seconds'), 'folder': name, 'url': r.get('url'), 'ats': r.get('ats'), 'status': 'submitted',
                        'by': 'receipt_confirm', 'confirmed_by': 'email', 'note': f'receipt e-mail: {str(subj)[:120]}'}
                with open(rp, 'a', encoding='utf-8') as out: out.write(json.dumps(line, ensure_ascii=False) + '\n')
                os.makedirs(fp, exist_ok=True)
                with open(os.path.join(fp, 'application_record.md'), 'a', encoding='utf-8') as rec:
                    rec.write(f"\n## Submitted — confirmed later by receipt e-mail {now.isoformat(timespec='seconds')}\n- URL: {r.get('url') or ''}\n"
                              f"- Confirmation: company e-mail \"{str(subj)[:120]}\" (the page showed no thank-you at the time)\n")
                sync(name)
                try: close(name, 'receipt e-mail found')
                except Exception as e: log(f'{name}: to-do close failed ({type(e).__name__})')
            elif d == 'joey':
                res['joey'].append(name)
                text = open(qp, encoding='utf-8').read() if os.path.exists(qp) else ''
                if not dry and not re.search(r'^- \[[ x]\] \S+ \*\*' + re.escape(name) + r'\*\* — no receipt e-mail in 48', text, re.M):   # open or ticked: asked once
                    with open(qp, 'a', encoding='utf-8') as q:
                        q.write(f"- [ ] {now.isoformat(timespec='seconds')} **{name}** — no receipt e-mail in 48 h (unconfirmed since {r['at'][:16]}) — check the site; submitted → sync_results --manual"
                                + (f" — {r['url']}" if r.get('url') else '') + '\n')
                log(f'{name}: no receipt e-mail in 48 h → Joey')
            else:
                res['waiting'].append(name)
    finally:
        socket.setdefaulttimeout(old_to); lock.close()
    return res


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--days', type=int, default=7)
    a = ap.parse_args()
    r = run(dry=a.dry_run, days=a.days)
    print(f"receipt_confirm: confirmed {len(r['confirmed'])} · to Joey {len(r['joey'])} · waiting {len(r['waiting'])}")
