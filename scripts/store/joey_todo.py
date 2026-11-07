#!/usr/bin/env python3
"""Joey's to-do list — one view of everything that waits for him (JSA-189).

Three ledgers used to hold it separately: `data/runner/queue.md` (one line per stopped attempt), `human_checks.jsonl`
(CAPTCHAs / human checks parked by the runners) and `apply_requests.jsonl` (dashboard Apply → needs-you). This merges them:
**one row per application folder** (the latest open entry, with how many there were), **closed by itself** when the folder
was submitted (results.jsonl), its tracker row moved on (Applied / Archived / Rejected …) or its job is 已关闭 / 不可投 / 重复.

Each row names its problem type (answers · sign-in · captcha · unconfirmed · materials · gate · runner error · …) and a
suggested next step; for "answers" rows the folder's open questions are re-answered with the current rules, so a row the
rules can now answer says "rerun" instead of asking Joey again.

    python3 scripts/store/joey_todo.py                    # the open list, grouped by problem type
    python3 scripts/store/joey_todo.py --json             # → data/runner/joey_todo.json (the dashboard reads it)
    python3 scripts/store/joey_todo.py --close <folder> --how "<what happened>"   # tick its queue lines, resolve its checks
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402

QLINE = re.compile(r'^- \[( |x)\] (\S+) \*\*(.+?)\*\* — (.*?)(?: — (https?://\S+))?\s*$')
DONE_TRACKER = {'Applied', 'Assessment', 'Interview', 'Offer', 'Rejected', 'Archived', 'No response', 'Withdrawn'}
DEAD_JOB = {'已关闭', '不可投', '重复'}
KINDS = [  # (problem type, pattern on the entry text) — first match wins
    ('unconfirmed', r'no confirmation|unconfirmed|check gmail'),
    ('captcha', r'captcha|human check|人机验证|hcaptcha|recaptcha|verify you are human'),
    ('sign-in', r'sign[- ]?in|account creation|create the account|login|log in|password|one-time code'),
    ('answers', r'needs answers|no rule answers|unknown|answers?\.json|wd_needs|question'),
    ('materials', r'materials|transcript|resume|cover letter|ds_materials|manifest'),
    ('gate', r'canonical|canon|not confirmed on the page|fields not confirmed|review page lacks|spot-check|not approved|referral'),
    ('runner error', r'runner error|timeout|timed out|traceback|exception'),
    ('refused', r'refused|correct the errors|please correct'),
]
NEXT = {'captcha': 'Joey solves the CAPTCHA in the job Chrome tab, then rerun with --attach',
        'sign-in': 'rerun (the sign-in wait has expired); a failed Keychain sign-in → Joey signs in once',
        'unconfirmed': 'check Gmail for the receipt; found → sync_results --manual, else Joey checks the site',
        'answers': 'Joey answers once → qa_add.py, then rerun',
        'materials': 'run ds_materials.py on the folder (or Joey supplies the file), then rerun',
        'gate': 'read the gate line; a wrong plan → fix (developing session), a confirmed value → canon --learn',
        'runner error': 'rerun on the current release; again → BACKLOG row for the problem type',
        'refused': 'read the page error; a missing field → developing session',
        'other': 'read the entry'}


def kind_of(text):
    """Pure (tested). The problem type of an entry's text."""
    t = (text or '').lower()
    for k, rx in KINDS:
        if re.search(rx, t):
            return k
    return 'other'


def parse_queue(text):
    """Pure (tested). queue.md → [{'open', 'at', 'folder', 'msg', 'url'}]."""
    out = []
    for line in (text or '').splitlines():
        m = QLINE.match(line.strip())
        if m:
            out.append({'open': m.group(1) == ' ', 'at': m.group(2), 'folder': m.group(3), 'msg': m.group(4), 'url': m.group(5) or ''})
    return out


def open_checks(rows):
    """Pure (tested). human_checks.jsonl rows → the open ones (the last state line per folder decides)."""
    last = {}
    for r in rows or []:
        if r.get('folder'):
            last[r['folder']] = r if r.get('state') == 'open' else (None if r.get('state') == 'resolved' else last.get(r['folder']))
    return [r for r in last.values() if r]


def needs_you(rows):
    """Pure (tested). apply_requests.jsonl → {job id: latest row} where the latest status is needs-you."""
    last = {}
    for r in rows or []:
        if r.get('id'):
            last[r['id']] = r
    return {k: r for k, r in last.items() if r.get('status') == 'needs-you'}


def merge(queue_rows, checks, asks, submitted, tracker, jobs, job_of, today):
    """Pure (tested). One row per folder: the newest open entry wins, `n` = open entries; closed folders are dropped.
    submitted = set of folders; tracker = {job id: status}; jobs = {job id: elig}; job_of = {folder: job id}."""
    rows = {}

    def add(folder, at, msg, url, src):
        r = rows.setdefault(folder, {'folder': folder, 'job_id': job_of.get(folder, ''), 'n': 0, 'sources': [], 'at': '', 'msg': '', 'url': ''})
        r['n'] += 1
        if src not in r['sources']:
            r['sources'].append(src)
        if str(at) >= r['at']:
            r.update(at=str(at), msg=msg, url=url or r['url'])
    for q in queue_rows:
        if q['open']:
            add(q['folder'], q['at'], q['msg'], q['url'], 'queue')
    for c in checks:
        qs = '; '.join(x.get('question', '') for x in c.get('checks') or []) or 'human check'
        add(c['folder'], c.get('at', ''), 'CAPTCHA / human check: ' + qs, c.get('url', ''), 'human_check')
    by_job = {v: k for k, v in job_of.items()}
    for jid, r in asks.items():
        add(by_job.get(jid) or jid, r.get('at', ''), 'dashboard Apply — needs you: ' + (r.get('note') or ''), '', 'apply_req')
    out = []
    for f, r in rows.items():
        jid = r['job_id'] or (f if re.match(r'^J\d+$', f) else '')
        if f in submitted or tracker.get(jid) in DONE_TRACKER or jobs.get(jid) in DEAD_JOB:
            continue
        r['kind'] = kind_of(r['msg']) if not r['msg'].startswith('CAPTCHA / human check') else 'captcha'
        r['next'] = NEXT.get(r['kind'], NEXT['other'])
        try:
            r['age_days'] = (datetime.fromisoformat(today[:10]) - datetime.fromisoformat(r['at'][:10])).days
        except ValueError:
            r['age_days'] = None
        out.append(r)
    order = [k for k, _ in KINDS] + ['other']
    return sorted(out, key=lambda r: (order.index(r['kind']) if r['kind'] in order else 99, r['at']))


# ----------------------------------------------------------------------------- data home
def _jsonl(p):
    out = []
    try:
        for line in open(p, encoding='utf-8'):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def load():
    R = lambda *p: jpaths.data('runner', *p)
    queue_rows = parse_queue(open(R('queue.md'), encoding='utf-8').read() if os.path.exists(R('queue.md')) else '')
    submitted = {r.get('folder') for r in _jsonl(R('results.jsonl')) if r.get('status') == 'submitted'}
    tracker = {r.get('job_id'): r.get('status') for r in _jsonl(jpaths.data('store', 'applications.jsonl'))}
    jobs = {r.get('id'): r.get('elig') for r in _jsonl(jpaths.data('store', 'jobs.jsonl'))}
    sys.path.insert(0, HERE)
    try:
        import sync_results
        job_of = sync_results.folder_job_ids()
    except Exception:
        job_of = {}
    return queue_rows, open_checks(_jsonl(R('human_checks.jsonl'))), needs_you(_jsonl(R('apply_requests.jsonl'))), submitted, tracker, jobs, job_of


def rules_answer_now(folder):
    """For an 'answers' row: the folder's open questions (wd_needs.json / form_check unknown) re-answered with the current
    rules → (answered, still_open) question lists. Empty lists when the folder records no questions."""
    qs = []
    d = jpaths.apps(folder)
    try:
        w = json.load(open(os.path.join(d, 'wd_needs.json'), encoding='utf-8'))
        for x in (w if isinstance(w, list) else w.get('needs') or w.get('fields') or []):
            if isinstance(x, dict) and x.get('label'):
                qs.append({'key': str(len(qs)), 'label': x['label'], 'type': x.get('type') or 'text', 'options': x.get('options') or []})
    except (OSError, ValueError):
        pass
    if not qs:
        return [], []
    try:
        r = subprocess.run(['node', os.path.join(ROOT, 'skills', 'auto-apply', 'runner', 'rules_bridge.js')], input=json.dumps(qs),
                           capture_output=True, text=True, timeout=60)
        got = json.loads(r.stdout or '{}')
    except Exception:
        return [], [q['label'] for q in qs]
    done = [q['label'] for q in qs if (got.get(q['key']) or {}).get('status') == 'ok']
    return done, [q['label'] for q in qs if q['label'] not in done]


def build(with_rules=True):
    rows = merge(*load(), today=datetime.now().isoformat())
    for r in rows:
        if with_rules and r['kind'] == 'answers' and not re.match(r'^J\d+$', r['folder']):
            done, still = rules_answer_now(r['folder'])
            r['rules_now'] = {'answered': done, 'open': still}
            if done and not still:
                r['next'] = f'rerun — the current rules answer all {len(done)} question(s) now'
            elif still:
                r['next'] = 'Joey answers once → qa_add.py: ' + ' | '.join(s[:70] for s in still[:4])
    return rows


def close(folder, how):
    """Tick every open queue line of the folder and resolve its open human checks."""
    p = jpaths.data('runner', 'queue.md')
    n = 0
    if os.path.exists(p):
        lines = open(p, encoding='utf-8').read().splitlines(True)
        for i, line in enumerate(lines):
            m = QLINE.match(line.strip())
            if m and m.group(1) == ' ' and m.group(3) == folder:
                lines[i] = line.replace('- [ ]', '- [x]', 1).rstrip('\n') + f' — closed {datetime.now().isoformat(timespec="minutes")}: {how}\n'; n += 1
        open(p, 'w', encoding='utf-8').writelines(lines)
    sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
    try:
        import human_check
        if any(c['folder'] == folder for c in open_checks(_jsonl(jpaths.data('runner', 'human_checks.jsonl')))):
            human_check.resolve(folder, how)
    except Exception:
        pass
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true'); ap.add_argument('--close'); ap.add_argument('--how', default='closed by hand')
    ap.add_argument('--no-rules', action='store_true', help='skip re-answering open questions with the current rules')
    a = ap.parse_args()
    if a.close:
        print(f'joey_todo: closed {close(a.close, a.how)} queue line(s) of {a.close}'); return 0
    rows = build(not a.no_rules)
    if a.json:
        out = jpaths.data('runner', 'joey_todo.json')
        json.dump({'built': datetime.now().isoformat(timespec='seconds'), 'rows': rows}, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'joey_todo: {len(rows)} open → {out}'); return 0
    print(f'Joey to-do — {len(rows)} application(s) wait for you')
    cur = None
    for r in rows:
        if r['kind'] != cur:
            cur = r['kind']; print(f'\n## {cur} ({sum(1 for x in rows if x["kind"] == cur)})')
        print(f"- {r['folder']} · {r['age_days']} d · {r['n']} entr{'y' if r['n'] == 1 else 'ies'} · {r['msg'][:110]}\n    → {r['next'][:160]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
