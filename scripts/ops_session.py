#!/usr/bin/env python3
"""The using session's start note (ADR-0011 step 5, JSA-342). The using session opens in the data home (~/JobAgent/data);
its .claude/settings.json (installed from ops/settings.json by the release) runs this as the SessionStart hook:

    python3 ~/JobAgent/app/scripts/ops_session.py --hook

It prints, for that session: the tracker actions Joey marked done since the last session (done_since.py), the form
questions waiting from the morning prefetch (prefetch_due.py, JSA-243) and the audit answers waiting for a judgment
(audit_sample.py --pending, JSA-245). Every part is '' on failure — the hook never breaks a session.
The instructions themselves are the data home's CLAUDE.md (= ops/CLAUDE.md of the release), loaded by Claude Code.
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def due_note(m, status_line):
    """Pure (tested). The morning-sheet line for the session note (JSA-243): using → ask Joey now; developing → only say a
    using session should (answers are written by the using system, never there); release / unknown / nothing waiting → ''."""
    if not status_line or m not in ('using', 'developing') or 'none waiting' in status_line or 'waiting' not in status_line:
        return ''
    if m == 'using':
        return ('FORM QUESTIONS WAITING (JSA-243) — ' + status_line + ' Ask them in your first reply (AskUserQuestion, '
                '≤ 4 per round, derived block first), then collect_batch.py --apply; Joey says 「今天不答」 → '
                'prefetch_due.py --done --how deferred.')
    return ('Note for Joey (JSA-243): ' + status_line.replace(' Ask Joey in the chat (docs/agent/using.md → Morning).', '')
            + ' They are answered in a using session (main folder), not in this developing session — mention it once in '
            'your first reply.')


def audit_note(m, n):
    """Pure (tested). JSA-245: answers of the independent audit waiting for a judgment → one line for using / developing
    sessions ('' when n is 0 or the mode is release / unknown)."""
    if not n or m not in ('using', 'developing'):
        return ''
    return (f'AUDIT (JSA-245): {n} answer(s) from the independent audit wait for a judgment — '
            '`python3 ~/JobAgent/app/scripts/audit_sample.py --pending`, then `--judge <key> right|wrong --note "…"` '
            '(ask Joey only what his facts do not settle).')


def _out(args, timeout=20):
    try:
        r = subprocess.run([sys.executable] + args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ''
    except Exception:
        return ''


def due_status(root=ROOT):
    return _out([os.path.join(root, 'scripts', 'store', 'prefetch_due.py')])


def audit_pending(root=ROOT):
    first = (_out([os.path.join(root, 'scripts', 'audit_sample.py'), '--pending']).splitlines() or [''])[0]
    try:
        return int(first.split()[1]) if first.startswith('audit:') else 0
    except (IndexError, ValueError):
        return 0


def done_since(root=ROOT):
    return _out([os.path.join(root, 'scripts', 'store', 'done_since.py')])


def git_note(root=ROOT):
    """JSA-358: files in the data home left uncommitted for more than 24 h ('' when none / on failure)."""
    return _out([os.path.join(root, 'scripts', 'store', 'data_git.py'), 'reminder'])


def note(root=ROOT):
    parts = ['SESSION SYSTEM: USING — this session opened in the data home (ADR-0011). Follow CLAUDE.md here; it never '
             'changes code: a runner problem goes to data/runner/queue.md for the dev lead. First status line: 「使用：…」.',
             done_since(root), due_note('using', due_status(root)), audit_note('using', audit_pending(root)), git_note(root)]
    return '\n\n'.join(p for p in parts if p)


if __name__ == '__main__':
    if '--hook' in sys.argv and not sys.stdin.isatty():
        try:
            sys.stdin.read()
        except OSError:
            pass
    print(note())
