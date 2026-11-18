#!/usr/bin/env python3
"""Tracker actions Joey marked done on the dashboard (JSA-126; the Done button is JSA-125).

    python3 scripts/store/done_since.py                  # done since the newest session log's date (data home logs/)
    python3 scripts/store/done_since.py --since 2026-11-03
    python3 scripts/store/done_since.py --watch          # block until a NEW done mark appears, print it, exit 0

`--watch` is for a live session: run it in the background; it reads data/store/applications.jsonl every 10 s and exits
as soon as a done entry exists that was not there when it started (an undo never counts), so the session wakes up,
handles it and starts the next watch. Reads only — never writes the store.
"""
import glob, json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
APPS = os.path.join(os.environ.get('JOB_STORE_DIR', jpaths.data('store')), 'applications.jsonl')
# the using sessions' logs live in the data home (ADR-0011: logs/session-log-<date>.md); the repo's old place is the fallback
LOGS = [jpaths.at('logs', 'session-log-*.md'), os.path.join(ROOT, 'skills', 'job-search-agent', 'references', 'session-log-*.md')]


def entries(rows):
    """Pure (tested). Applications rows → [(on, job_id, company, title, action)] for every action_done entry, sorted by
    on, then job_id, then the entry's position in the row's list. Rows without a list, or entries without an "on" date,
    give nothing."""
    out = []
    for r in rows:
        for k, e in enumerate(r.get('action_done') or []):
            if isinstance(e, dict) and e.get('on'):
                out.append((str(e['on']), str(r.get('job_id', '')), str(r.get('company', '')), str(r.get('title', '')),
                            str(e.get('action', '')), k))
    out.sort(key=lambda x: (x[0], x[1], x[5]))
    return [x[:5] for x in out]


def since(rows, day):
    """Pure (tested). Entries whose "on" date is on or after `day` (ISO dates compare as text)."""
    return [e for e in entries(rows) if e[0] >= day]


def new_since(before, rows):
    """Pure (tested). Entries in `rows` that are not in the `before` list (multiset: a second identical entry is new)."""
    left = list(before)
    out = []
    for e in entries(rows):
        if e in left:
            left.remove(e)
        else:
            out.append(e)
    return out


def last_session_day():
    days = [re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(p)).group(1) for g in LOGS for p in glob.glob(g)]
    return max(days) if days else '0000-00-00'


def load():
    return [json.loads(l) for l in open(APPS, encoding='utf-8') if l.strip()]


def show(es):
    for on, jid, co, title, act in es:
        print(f'- {co} · {title} ({jid}): {act} — marked done {on}')


def main(a):
    if '--watch' in a:
        before = entries(load())
        while True:
            time.sleep(10)
            try:
                rows = load()
            except (OSError, ValueError):            # mid-write: read again next round
                continue
            new = new_since(before, rows)
            if new:
                print(f'{len(new)} new done mark(s):')
                show(new)
                return 0
            before = entries(rows)                   # nothing new: an undo shrinks the baseline, so a re-mark counts
    day = a[a.index('--since') + 1] if '--since' in a else last_session_day()
    es = since(load(), day)
    print(f'done since {day}: {len(es)}')
    show(es)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
