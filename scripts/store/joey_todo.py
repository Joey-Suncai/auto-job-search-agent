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
    python3 scripts/store/joey_todo.py --json             # → data/runner/joey_todo.json (full list; the dashboard shows dashboard_rows() of it)
    python3 scripts/store/joey_todo.py --close <folder> --how "<what happened>"   # tick its queue lines, resolve its checks
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402

QLINE = re.compile(r'^- \[( |x)\] (\S+) \*\*(.+?)\*\* — (.*?)(?: — (https?://\S+))?\s*$')
# Assessment / Interview are NOT here: a folder whose next step is Joey's assessment or interview stays open (JSA-389)
DONE_TRACKER = {'Applied', 'Offer', 'Rejected', 'Archived', 'No response', 'Withdrawn', 'Declined by Joey'}
ACTION_CLOSED = {'Rejected', 'Archived', 'Withdrawn', 'No response', 'Declined by Joey'}   # Offer stays: accepting it has a deadline (JSA-394)   # a tracker action of such a row is stale
ACTION_KINDS = [('assessment', r'assessment|challenge|hackerrank|coderbyte|hirevue|modern hire|spark ?hire|honorlock|codility|online test|coding test|skills test|take-home'),
                ('interview', r'interview|phone screen|screening call|schedul\w* (?:a |an |your |the )?(?:call|chat|screen|time|meeting|conversation)|(?:book|pick) (?:a |your )?(?:time|.{0,30}(?:call|screen|slot))|final round|scheduling link'),
                ('confirm', r'请确认|confirm|decide|check whether')]
NOISE = re.compile(r'one[- ]?time (pass)?code|pass ?code|verification code|security code|等结果|waiting for (the )?result', re.I)
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
        'other': 'read the entry',
        'assessment': 'Joey takes the assessment before the deadline (link in the e-mail)',
        'interview': 'Joey books / prepares the interview (link in the e-mail)',
        'form': 'Joey completes the form (link in the e-mail), then clicks Done on the dashboard',
        'offer': 'Joey answers the offer (accept / decline) before its deadline, then clicks Done on the dashboard',
        'confirm': 'Joey checks and clicks Done on the dashboard',
        'skill-gap': 'Joey says which of these he really did (becomes a fact); otherwise nothing is added'}


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


def tracker_actions(apps, today):
    """Pure (tested, JSA-389). Tracker rows → to-do rows for every open `action_needed` (e-mailed assessments, interviews,
    forms, confirmations). Left out: rows already Rejected / Archived / Withdrawn / No response, one-time passcodes / verification
    codes and "waiting for the result" notes. An action Joey ticked Done is cleared by action_done.py, so non-empty = open."""
    out = []
    for a in apps or []:
        txt = (a.get('action_needed') or '').strip()
        if not txt or a.get('status') in ACTION_CLOSED or (NOISE.search(txt) and not re.search(dict(ACTION_KINDS)['assessment'], txt.lower())):
            continue
        low = txt.lower()
        kind = 'offer' if a.get('status') == 'Offer' else next((k for k, rx in ACTION_KINDS if re.search(rx, low)), 'form')
        ddl = str(a.get('action_deadline') or '')[:10]
        left = None
        if re.match(r'^\d{4}-\d{2}-\d{2}$', ddl):
            try:
                left = (datetime.fromisoformat(ddl) - datetime.fromisoformat(today[:10])).days
            except ValueError:
                ddl = ''
        else:
            ddl = ''
        jid = a.get('job_id') or ''
        out.append({'folder': jid, 'job_id': jid, 'n': 1, 'sources': ['tracker'], 'at': '', 'url': '', 'kind': kind,
                    'msg': f"{a.get('company') or ''}: {txt}", 'next': NEXT[kind], 'age_days': None, 'deadline': ddl,
                    'days_left': left, 'overdue': left is not None and left < 0,
                    'conditional': bool(re.match(r'if\b', low)),
                    'last_email': a.get('last_email') or '', 'last_email_date': a.get('last_email_date') or '',   # JSA-413: the link to the mail
                    'email_url': a.get('email_url') or ''})
    return sorted(out, key=lambda r: (r['deadline'] == '', r['deadline']))


def merge(queue_rows, checks, asks, submitted, tracker, jobs, job_of, today, actions=None):
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
    out = sorted(out, key=lambda r: (order.index(r['kind']) if r['kind'] in order else 99, r['at']))
    acts = list(actions or [])   # kept even when the job also has a runner stop: the deadline must not be hidden
    dated = [x for x in acts if x['deadline']]
    for r in out:
        r['group'] = 'stopped'
    for x in acts:
        x['group'] = 'action'
    # two blocks (JSA-395): what Joey does himself (dated actions soonest first, then undated), then runner stops
    return dated + [x for x in acts if not x['deadline']] + out


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
    apps = _jsonl(jpaths.data('store', 'applications.jsonl'))
    tracker = {r.get('job_id'): r.get('status') for r in apps}
    jobs = {r.get('id'): r.get('elig') for r in _jsonl(jpaths.data('store', 'jobs.jsonl'))}
    sys.path.insert(0, HERE)
    try:
        import sync_results
        job_of = sync_results.folder_job_ids()
    except Exception:
        job_of = {}
    return queue_rows, open_checks(_jsonl(R('human_checks.jsonl'))), needs_you(_jsonl(R('apply_requests.jsonl'))), submitted, tracker, jobs, job_of, apps


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


DASH_KINDS = ('assessment', 'interview', 'form', 'offer')


def dashboard_rows(rows):
    """Pure (tested, JSA-397). What the dashboard shows: only the next steps a company asks of Joey after receiving his
    application (assessment / OA, interview, a form the company wants, take-home, offer). Runner stops, rows the
    classifier was unsure of, codes, submit-confirmations and "if …" notes stay in the command-line list only."""
    return [r for r in rows if r.get('group') == 'action' and r.get('kind') in DASH_KINDS and not r.get('conditional')]


def add_tiers(rows, jobs):
    """Pure (tested, JSA-404). Each row gets `tier` = the fit tier of the job with the row's job_id (a Blocked job shows its
    original tier); "—" when there is no job_id, no such job or no tier — never a guess."""
    t = {}
    for j in jobs or []:
        v = (j.get('tier_orig') if j.get('tier') == 'Blocked' else j.get('tier')) or ('Blocked' if j.get('tier') == 'Blocked' else '')
        t.setdefault(j.get('id'), v)
    return [{**r, 'tier': (t.get(r.get('job_id')) if r.get('job_id') else '') or '—'} for r in rows]


def add_roles(rows, applications):
    """Pure (tested, JSA-423). Each row gets `role` = the `title` of the application with the row's job_id (the Tracker's
    Role field), trimmed; "—" when there is no job_id, no such application, or the title is empty / "(unknown role)" —
    never a guess."""
    t = {}
    for a in applications or []:
        t.setdefault(a.get('job_id'), str(a.get('title') or '').strip())
    out = []
    for r in rows:
        v = t.get(r.get('job_id')) if r.get('job_id') else ''
        out.append({**r, 'role': '—' if not v or v.lower() == '(unknown role)' else v})
    return out


def group_by_kind(rows):
    """Pure (tested, JSA-395). [(kind, [rows])] — each kind once, in order of first appearance, rows keep their order."""
    groups = {}
    for r in rows:
        groups.setdefault(r['kind'], []).append(r)
    return list(groups.items())


def build(with_rules=True):
    *args, apps = load()
    today = datetime.now().isoformat()
    rows = merge(*args, today=today, actions=tracker_actions(apps, today))
    for r in rows:
        if with_rules and r['kind'] == 'answers' and not re.match(r'^J\d+$', r['folder']):
            done, still = rules_answer_now(r['folder'])
            r['rules_now'] = {'answered': done, 'open': still}
            if done and not still:
                r['next'] = f'rerun — the current rules answer all {len(done)} question(s) now'
            elif still:
                r['next'] = 'Joey answers once → qa_add.py: ' + ' | '.join(s[:70] for s in still[:4])
    try:   # JSA-194: the daily skill-gap list is one row (recurring JD terms none of his facts show)
        sys.path.insert(0, HERE)
        import skill_gap
        gr = skill_gap.todo_row(skill_gap.build(), today)
        if gr:
            rows.append(gr)
    except Exception as e:   # a broken list must not hide the rest of the to-do list, but it is not silent
        print('joey_todo: skill-gap list skipped:', e, file=sys.stderr)
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
    for gname, title in (('action', 'FOR YOU TO DO'), ('stopped', 'RUNNER STOPPED (CAPTCHA / sign-in / answers …)')):
      part = [r for r in rows if r.get('group') == gname]
      print(f'\n=== {title} — {len(part)} ===')
      for kind, grp in group_by_kind(part):
        print(f'\n## {kind} ({len(grp)})')
        for r in grp:
            print(f"- {r['folder']} · {('due ' + r['deadline'] + (' OVERDUE' if r.get('overdue') else '')) if r.get('deadline') else str(r['age_days']) + ' d'} · {r['n']} entr{'y' if r['n'] == 1 else 'ies'} · {r['msg'][:110]}\n    → {r['next'][:160]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
