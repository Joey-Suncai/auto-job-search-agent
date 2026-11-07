#!/usr/bin/env python3
"""Dashboard "Apply" requests (JSA-179, Joey 2026-11-05: 「在dashboard里点击职位也能让你申请」, option A = an open Claude
session does the work).

A click on Apply in a job's detail panel (after the page's confirm dialog) POSTs to scripts/scoring/pref_server.py
(/apply); the server calls queue() here. The job row gets
    apply_req = 'queued' | 'applying' | 'submitted' | 'needs-you' | 'cancelled',  apply_req_at, apply_req_note,
    apply_req_by = "Joey (dashboard Apply <time>)"   ← the approval words for this one-job batch (rule 7)
and data/runner/apply_requests.jsonl gets one line per change (history). The store is written only through store.py.

The open session runs `python3 scripts/store/apply_req.py --watch` in the background: it exits on the first new queued
request (printing it), the session handles it with skills/auto-apply (live JD + form re-read → materials → runner with
--submit, every check must pass; the folder is added to data/runner/approved_batches.json with apply_req_by as
approved_by), sets the status with `--set`, and starts the next watch.

    python3 scripts/store/apply_req.py --list                       # open requests (queued / applying / needs-you)
    python3 scripts/store/apply_req.py --watch                      # block until a new queued request, print it
    python3 scripts/store/apply_req.py --set J01234 applying|submitted|needs-you|cancelled [--note "…"]
    python3 scripts/store/apply_req.py --beat                       # the desk's heartbeat (background, whole session)
    python3 scripts/store/apply_req.py --desk                       # is a desk listening?

One desk at a time (JSA-182, Joey 2026-11-05: 「同时点多个 apply…应该自动在那个已经打开的会话里面排队…因为 runner 会占同一个
浏览器」): the desk session keeps `--beat` running, which writes data/runner/apply_desk.json every BEAT s; a second
`--beat` refuses while the first is fresh, so only one session ever takes requests and the runner never shares the job
Chrome. Every click only queues; the desk takes them one at a time, oldest first. A click when no desk is alive pushes
one notification (at most every NOTIFY_GRACE s) asking Joey to open the 投递 session. Starting a session automatically
from the server was refused by the auto-mode safety check (2026-11-05) — it waits for Joey's decision.
Tests (rule 13): scripts/test_apply_req.py (DeepSeek cases, scripts/test_cases/apply_req_*).
"""
import datetime as dt, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'config'))

STATUSES = ('queued', 'applying', 'submitted', 'needs-you', 'cancelled')
OPEN = ('queued', 'applying', 'needs-you')
NO_SUBMIT = {'tiktok'}           # Joey presses Submit himself (2 slots per half-year) — never from a dashboard click


def skip_names(text):
    """Pure (tested). skip_companies.txt text → lower-case company names (the part before " | "; # lines and blanks skipped)."""
    out = []
    for line in str(text or '').splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        out.append(s.split('|')[0].strip().lower())
    return [x for x in out if x]


BLOCKED_ELIG = ('不可投', '已关闭', '重复')


def apply_mode(job, runner):
    """Pure (tested). How the desk applies (JSA-183, Joey 2026-11-05 「在所有能看到 Jobs 的地方都可以点 Apply」):
    'runner' = 可投 and a runner that can submit ('ready', or 'testing' not on tiktok); 'verify-first' = eligibility is
    待核实 (or empty): the desk reads the full JD and stops if anything rules Joey out, then applies like the others;
    'by-hand' = 可投 but no runner that can submit (none / unknown platform): the desk looks for the company's apply link
    (a runner platform → the runner), else fills the form in the job Chrome by hand and verifies every field. A row
    that is both 待核实 and without a runner is 'verify-first' (the JD check comes first)."""
    if (job.get('elig') or '待核实') == '待核实':
        return 'verify-first'
    r, plat = runner.get('runner'), runner.get('platform') or ''
    if r == 'ready' or (r == 'testing' and plat not in NO_SUBMIT):
        return 'runner'
    return 'by-hand'


def can_queue(job, applied_ids, skip, runner):
    """Pure (tested). May this job be queued from the dashboard? → (True, '') or (False, reason).
    job = store row; applied_ids = set of job ids that already have an applications row; skip = lower-case company names
    from the skip list; runner = {'platform', 'runner'} (platform_counts.runner_fields). Checks, in order: eligibility is
    not 不可投 / 已关闭 / 重复; no applications row yet; no open or submitted request (apply_req queued / applying /
    needs-you / submitted); company not on the skip list (exact name, case-insensitive); the platform is not tiktok
    (Joey submits those himself). Any runner status is fine otherwise (apply_mode says how)."""
    if (job.get('elig') or '') in BLOCKED_ELIG:
        return False, f"eligibility is {job.get('elig')}"
    if job.get('id') in applied_ids:
        return False, 'already in the tracker (applied or in progress)'
    if (job.get('apply_req') or '') in OPEN + ('submitted',):
        return False, f"already requested ({job.get('apply_req')})"
    if str(job.get('company') or '').strip().lower() in skip:
        return False, 'company is on the skip list'
    plat = runner.get('platform') or ''
    if plat in NO_SUBMIT:
        return False, f'{plat}: Joey submits these himself'
    return True, ''


def set_fields(job, status, now, note='', by=''):
    """Pure (tested). The job row with apply_req = status, apply_req_at = now, apply_req_note = note (removed when ''),
    and apply_req_by = by when given (kept otherwise). Unknown status → ValueError."""
    if status not in STATUSES:
        raise ValueError(f'status must be one of {", ".join(STATUSES)}')
    r = dict(job)
    r.update(apply_req=status, apply_req_at=now)
    if note:
        r['apply_req_note'] = note
    else:
        r.pop('apply_req_note', None)
    if by:
        r['apply_req_by'] = by
    return r


def queued(rows):
    """Pure (tested). [(apply_req_at, id, company, title)] of rows whose apply_req is 'queued', oldest first."""
    return sorted((str(r.get('apply_req_at') or ''), r.get('id'), r.get('company') or '', r.get('title') or '')
                  for r in rows if r.get('apply_req') == 'queued')


BEAT, STALE, NOTIFY_GRACE = 10, 60, 600


def desk_alive(state, now, stale=STALE):
    """Pure (tested). state = the desk file's dict (or None); now = epoch seconds. True when state has a numeric "beat"
    no older than `stale` seconds (a beat in the future counts as fresh)."""
    try:
        return now - float((state or {}).get('beat')) <= stale
    except (TypeError, ValueError):
        return False


def should_notify(state, now, stale=STALE, grace=NOTIFY_GRACE):
    """Pure (tested). Push "no desk is listening"? Only when no desk is alive AND no such push went out in the last
    `grace` seconds (state "notified_at", epoch seconds; missing or not a number = never)."""
    if desk_alive(state, now, stale):
        return False
    try:
        return now - float((state or {}).get('notified_at')) > grace
    except (TypeError, ValueError):
        return True


def _desk_path():
    import paths as jpaths
    return jpaths.data('runner', 'apply_desk.json')


def _desk_read():
    try:
        return json.load(open(_desk_path(), encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _desk_write(d):
    p = _desk_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
    os.replace(tmp, p)


def ensure_desk(push=None):
    """After a click: 'alive' (a desk is listening; the request waits its turn) or 'none' (no desk; Joey is pushed at
    most once per NOTIFY_GRACE s to open the 投递 session — the request stays queued until a desk takes it)."""
    now = time.time()
    st = _desk_read()
    if desk_alive(st, now):
        return 'alive'
    if should_notify(st, now):
        st['notified_at'] = now
        _desk_write(st)
        try:
            (push or _push)('求职：Apply 已排队，没有投递会话在接', '打开「使用：接看板 Apply 请求」会话（主文件夹 job-search-agent），它会按顺序一个一个投。')
        except Exception:
            pass
    return 'none'


def _push(title, body):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'daily'))
    from notify import notify
    notify(title, body)


def beat():
    """The desk's heartbeat: refuses (exit 2) while another desk beats; else writes {pid, beat, started} every BEAT s
    and stops (exit 2) if a newer desk takes over."""
    st = _desk_read()
    if desk_alive(st, time.time()) and st.get('pid') != os.getpid():
        print(f"another apply desk is alive (pid {st.get('pid')}): this session must not take requests"); return 2
    started = time.time()
    print(f'apply desk heartbeat: pid {os.getpid()} → {_desk_path()}', flush=True)
    while True:
        st = _desk_read()
        if st.get('pid') not in (None, os.getpid()) and desk_alive(st, time.time()) and float(st.get('started') or 0) > started:
            print('a newer desk took over; stopping this heartbeat'); return 2
        _desk_write({'pid': os.getpid(), 'beat': time.time(), 'started': started, 'notified_at': st.get('notified_at')})
        time.sleep(BEAT)


def _now():
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def _log(rec):
    import paths as jpaths
    p = jpaths.data('runner', 'apply_requests.jsonl')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def queue(job_id):
    """Load jobs, check can_queue, set apply_req = queued, save, log. → the new row. KeyError = unknown id; ValueError =
    refused (the reason)."""
    import store, paths as jpaths, platform_counts as PC
    jobs = store.load('jobs')
    i = next((k for k, j in enumerate(jobs) if j.get('id') == job_id), None)
    if i is None:
        raise KeyError(job_id)
    applied = {a.get('job_id') for a in store.load('applications')}
    sp = jpaths.data('dashboard', 'skip_companies.txt')
    skip = skip_names(open(sp, encoding='utf-8').read()) if os.path.exists(sp) else []
    ok, why = can_queue(jobs[i], applied, skip, PC.runner_fields(jobs[i]))
    if not ok:
        raise ValueError(why)
    now = _now()
    mode = apply_mode(jobs[i], PC.runner_fields(jobs[i]))
    jobs[i] = set_fields(jobs[i], 'queued', now, note={'verify-first': 'verify the JD first', 'by-hand': 'no runner: find the apply link or fill by hand'}.get(mode, ''),
                         by=f'Joey (dashboard Apply {now})')
    jobs[i]['apply_mode'] = mode
    store.save('jobs', jobs)
    _log({'at': now, 'id': job_id, 'status': 'queued', 'mode': mode, 'company': jobs[i].get('company'), 'title': jobs[i].get('title'),
          'by': jobs[i]['apply_req_by']})
    return jobs[i]


def set_status(job_id, status, note=''):
    import store
    jobs = store.load('jobs')
    i = next((k for k, j in enumerate(jobs) if j.get('id') == job_id), None)
    if i is None:
        raise KeyError(job_id)
    now = _now()
    jobs[i] = set_fields(jobs[i], status, now, note)
    store.save('jobs', jobs)
    _log({'at': now, 'id': job_id, 'status': status, 'note': note})
    return jobs[i]


def main(a):
    import store
    if '--set' in a:
        k = a.index('--set')
        jid, st = a[k + 1], a[k + 2]
        r = set_status(jid, st, a[a.index('--note') + 1] if '--note' in a else '')
        print(r['id'], r.get('company'), '→', r['apply_req'], r.get('apply_req_note', ''))
        return 0
    if '--beat' in a:
        return beat()
    if '--desk' in a:
        st = _desk_read(); print('desk alive' if desk_alive(st, time.time()) else 'no desk listening', st); return 0
    if '--watch' in a:
        before = {x[1] for x in queued(store.load('jobs'))}
        while True:
            time.sleep(10)
            try:
                q = queued(store.load('jobs'))
            except (OSError, ValueError):
                continue
            new = [x for x in q if x[1] not in before]
            if new:
                print(f'{len(new)} new Apply request(s) from the dashboard:')
                for at, jid, co, title in new:
                    print(f'- {co} · {title} ({jid}), queued {at}')
                return 0
            before = {x[1] for x in q}
    rows = [j for j in store.load('jobs') if (j.get('apply_req') or '') in OPEN]
    print(f'open Apply requests: {len(rows)}')
    for j in sorted(rows, key=lambda r: str(r.get('apply_req_at'))):
        print(f"- {j['apply_req']:9} [{j.get('apply_mode', 'runner')}] {j.get('company')} · {j.get('title')} ({j['id']}) {j.get('apply_req_at')} {j.get('apply_req_note', '')}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
