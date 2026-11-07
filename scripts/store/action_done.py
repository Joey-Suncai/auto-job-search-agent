#!/usr/bin/env python3
"""Mark a tracker row's "Action needed" as done, or undo it (JSA-125, Joey 2026-11-03: a Done button in the tracker).

Done: the row's `action_needed` moves into its `action_done` history ({"on": date, "action": text}, newest last) and
`action_needed` becomes "". Undo: the newest history entry goes back into `action_needed`. `updated` = today either way.
Nothing else changes (status, next_step, last_email, applied_on). A later email with a new action sets action_needed
again (email_check reads each message once), so a done mark never hides new work.

Called by the dashboard through scripts/scoring/pref_server.py (POST /action), or by hand:
    python3 scripts/store/action_done.py <job_id> done|undo
"""
import datetime as dt, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
WAIT = ('', '等结果')          # "nothing to do" values: there is no action to mark done


def mark(row, done, today):
    """Pure (tested). One applications row → (new row, error or None). `done` True = mark done, False = undo."""
    r = dict(row)
    hist = list(r.get('action_done') or [])
    if done:
        act = (r.get('action_needed') or '').strip()
        if act in WAIT:
            return row, 'no open action on this row'
        hist.append({'on': today, 'action': act})
        r.update(action_needed='', action_done=hist, updated=today)
        return r, None
    if not hist:
        return row, 'nothing to undo'
    if (r.get('action_needed') or '').strip() not in WAIT:
        return row, 'the row has a new action since; nothing undone'
    last = hist.pop()
    r.update(action_needed=last['action'], updated=today)
    if hist:
        r['action_done'] = hist
    else:
        r.pop('action_done', None)
    return r, None


def apply(job_id, done, today=None):
    """Load applications, mark the row with this job_id, save. → the new row. KeyError = unknown id; ValueError = refused."""
    import store
    today = today or dt.date.today().isoformat()
    rows = store.load('applications')
    i = next((k for k, r in enumerate(rows) if r.get('job_id') == job_id), None)
    if i is None:
        raise KeyError(job_id)
    new, err = mark(rows[i], done, today)
    if err:
        raise ValueError(err)
    rows[i] = new
    store.save('applications', rows)
    return new


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[2] not in ('done', 'undo'):
        sys.exit('usage: action_done.py <job_id> done|undo')
    r = apply(sys.argv[1], sys.argv[2] == 'done')
    print(r['job_id'], r['company'], '| action_needed =', repr(r.get('action_needed')), '| history', len(r.get('action_done') or []))
