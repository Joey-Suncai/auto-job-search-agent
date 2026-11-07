#!/usr/bin/env python3
"""One job Chrome, one driver at a time (JSA-236, 2026-11-06).

2026-11-06 02:17–02:19 a worktree's batch_apply.py prepare (Workday: Microchip, Dell) and a main-folder session's run.py
loop drove CDP 9222 at the same time. Every runner that opens the job Chrome takes this lock first:

  data/runner/chrome.lock — an fcntl lock (released by the OS when the process dies, so a crash never leaves it held) plus
  the holder's {pid, who, at} written inside for the message.

A second process waits up to JSA_CHROME_LOCK_WAIT seconds (default 300), saying once who holds it, then gives up with
`STATUS chrome-busy` and the holder. batch_apply.py holds the lock for the whole batch and passes its pid in
JSA_CHROME_LOCK_HOLDER, so the runners it starts (its children) go ahead instead of waiting for their parent.

    import chrome_lock; chrome_lock.hold('run.py <folder>')     # returns, or exits with STATUS chrome-busy
"""
import json, os, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))
_HELD = []            # keeps the open file (and so the lock) alive for the life of the process
ENV_HOLDER = 'JSA_CHROME_LOCK_HOLDER'


def path():
    d = os.environ.get('CX_DATA')
    if not d:
        import paths as jpaths
        d = jpaths.data('runner')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'chrome.lock')


def inherited(holder, env_pid, parent_chain):
    """Pure. True when the lock's holder is an ancestor that handed it down (JSA_CHROME_LOCK_HOLDER = its pid)."""
    try:
        hp, ep = int((holder or {}).get('pid') or 0), int(env_pid or 0)
    except (TypeError, ValueError):
        return False
    return bool(hp) and hp == ep and hp in set(parent_chain or [])


def describe(holder, now=None):
    """Pure. One line naming the holder: 'pid 123 (run.py X) since 02:17:05'."""
    h = holder or {}
    return f"pid {h.get('pid') or '?'} ({h.get('who') or '?'}) since {str(h.get('at') or '')[11:19] or '?'}"


def _parents():
    out, pid = [], os.getpid()
    for _ in range(12):
        try:
            import subprocess
            pp = int(subprocess.run(['ps', '-o', 'ppid=', '-p', str(pid)], capture_output=True, text=True).stdout.strip() or 0)
        except Exception:
            break
        if pp <= 1:
            break
        out.append(pp); pid = pp
    return out


def _read(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return {}


def hold(who, wait=None, log=print):
    """Take the job-Chrome lock for this process (or go ahead under an ancestor that holds it). On timeout: print the
    holder and `STATUS chrome-busy`, exit 3."""
    if os.environ.get('JSA_CHROME_LOCK') == 'off':          # tests with their own browser
        return True
    if _HELD:                                                 # this process holds it already (a second Run in one process)
        return True
    import fcntl
    p = path()
    wait = float(os.environ.get('JSA_CHROME_LOCK_WAIT', 300) if wait is None else wait)
    f = open(p, 'a+')
    t0, told = time.time(), False
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            h = _read(p)
            if inherited(h, os.environ.get(ENV_HOLDER), _parents()):
                f.close(); return True
            if not told:
                log(f'job Chrome busy: {describe(h)} — waiting up to {int(wait)} s'); told = True
            if time.time() - t0 >= wait:
                log(f'job Chrome still busy after {int(wait)} s: {describe(h)} — not started')
                print('STATUS chrome-busy'); sys.exit(3)
            time.sleep(2)
    f.seek(0); f.truncate()
    f.write(json.dumps({'pid': os.getpid(), 'who': who, 'at': datetime.now().isoformat(timespec='seconds')})); f.flush()
    _HELD.append(f)
    os.environ[ENV_HOLDER] = str(os.getpid())                 # children (batch_apply → runners) go ahead
    return True
