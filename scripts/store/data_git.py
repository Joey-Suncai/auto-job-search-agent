#!/usr/bin/env python3
"""The data home's git (JSA-358): writers commit their own files on the spot, regenerable caches stay out of git, and a
file left uncommitted for more than 24 hours is reminded about.

    import data_git; data_git.commit_paths([results_path], 'data: runner result')   # best effort, never raises
    python3 scripts/store/data_git.py reminder      # prints the reminder (or nothing); exit 0
    python3 scripts/store/data_git.py sweep         # JSA-412: commits what unwired writers left (tracked roots only, quiet 2 min)
    python3 scripts/store/data_git.py ignore        # adds the cache patterns to the data home's .gitignore

Rules: only the named paths are committed (`git commit -- <paths>`). commit_tree / commit_application take a whole folder (the writer's own output unit; a file another
writer is still writing in the same folder can ride along — sweep() waits for a quiet period instead).
No commit when the data home is not a git repo, is the code repo itself (the open-source layout / fixtures), or
JSA_NO_DATA_GIT=1 (tests; JSA_DATA_GIT_DEFER=1 = the caller commits itself afterwards, as run_daily does).
Tests: scripts/store/test_data_git.py (real git in temp folders).
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)

ENV = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
# regenerable caches / bulk that never belong in the data home's history (the form corpus is rebuilt by scripts/learn)
IGNORE = ('data/forms/', 'data/work/', 'data/roles/',
          # JSA-412: regenerable screenshots / debug dumps / locks / the triage cache; submitted_confirmation.png (the proof),
          # the docx/pdf sent to the employer and every other file of an application folder stay in git
          'applications/*/filled_check.png', 'applications/*/after_submit.png', 'applications/*/page.png',  # paths-ok: a git pattern relative to the data home
          'applications/*/runner.out', 'applications/*/runner2.out', 'applications/*/ds_last_response.json',  # paths-ok: a git pattern relative to the data home
          'applications/*/ds_failed_response.json', '*.lock', 'data/learn/triage_cache.jsonl',  # paths-ok: git pattern
          'data/runner/qtype_cache.jsonl', 'data/runner/qtype_shadow.jsonl', 'data/runner/qtype_shadow_state.json',   # paths-ok: git patterns
          'data/runner/final_review_cache.jsonl')  # paths-ok: a git pattern relative to the data home
MARK = '# caches (JSA-358, JSA-412)'
# JSA-412: what sweep() / commit_application() may commit — never config/, data/store/ or results.jsonl (their writers commit them)
TRACK_ROOTS = ('applications', 'data/learn', 'data/runner/batches', 'data/releases.jsonl', 'resume',  # paths-ok: a git pattern relative to the data home
               'data/runner/fields', 'data/runner/replay', 'data/runner/audit', 'data/runner/queue.md', 'data/runner/final_review.jsonl', 'data/runner/linkedin', 'data/runner/whole_read_cache.jsonl', 'data/runner/apply_desk.json')   # tracked state files of the runner / learn loop  # paths-ok: a git pattern relative to the data home
QUIET_SECS = 120                                           # a file younger than this may still be being written
REMIND_HOURS = 24


def _git(home, *a, run=subprocess.run):
    return run(['git', '-C', home, *a], capture_output=True, text=True, env=ENV)


def active(home=None, env=None):
    """Why committing is switched off: a reason string, or '' when the data home's git should be used."""
    env = os.environ if env is None else env
    home = home or jpaths.home()
    if env.get('JSA_NO_DATA_GIT') or env.get('JSA_DATA_GIT_DEFER'):
        return 'switched off'
    if not os.path.exists(os.path.join(home, '.git')):
        return 'not a git repo'
    if os.path.realpath(home) == os.path.realpath(jpaths.REPO):
        return 'data home is the code repo'
    return ''


def commit_paths(paths, subject, home=None, run=subprocess.run):
    """Commit exactly these files (absolute or relative to the data home) → 'committed' | 'nothing' | 'skipped: …' |
    'failed: …'. Never raises: a data write must not fail because git is busy."""
    home = home or jpaths.home()
    why = active(home)
    if why:
        return 'skipped: ' + why
    try:
        rel = [os.path.relpath(p, home) if os.path.isabs(p) else p for p in paths]
        rel = [os.path.normpath(p) for p in rel]
        rel = [p for p in rel if not p.startswith('..') and (os.path.exists(os.path.join(home, p)) or _tracked(home, p, run))]   # a deleted tracked file is committed too
        if not rel:
            return 'nothing'                               # nothing of ours inside this data home: touch nothing, not even .gitignore
        ensure_ignore(home)                                # the cache patterns reach the data home with the first writer's commit
        if '.gitignore' not in rel and _ours_only('.gitignore', home, run):
            rel.append('.gitignore')                       # only when the pending change is our own cache lines
        for attempt in (0, 1):
            addable = [p for p in rel if os.path.exists(os.path.join(home, p)) or _git(home, 'ls-files', '-z', '--', p, run=run).stdout]
            ad = _git(home, 'add', '-A', '--', *addable, run=run) if addable else _git(home, 'status', '-s', run=run)   # an ignored path is refused quietly; -A stages deletions
            if ad.returncode != 0 and 'index.lock' in ad.stderr and attempt == 0:
                time.sleep(1.5)                            # another writer holds the index: once more
                continue
            st = _git(home, 'status', '--porcelain', '--', *rel, run=run).stdout
            if not [l for l in st.splitlines() if l[:2].strip() and not l.startswith('!!')]:
                return 'nothing'
            c = _git(home, 'commit', '-q', '-m', subject, '--', *rel, run=run)
            if c.returncode == 0:
                return 'committed'
            if 'index.lock' in c.stderr and attempt == 0:
                time.sleep(1.5)                            # another writer is committing: once more
                continue
            return 'failed: ' + c.stderr.strip()[-200:]
    except Exception as e:                                 # noqa: BLE001 — best effort by design
        return f'failed: {e}'
    return 'failed'


def ensure_ignore(home=None):
    """Add the cache patterns to the data home's .gitignore (idempotent) → the lines added."""
    home = home or jpaths.home()
    p = os.path.join(home, '.gitignore')
    have = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
    todo = [x for x in IGNORE if x not in have.splitlines()]
    if todo:
        with open(p, 'a', encoding='utf-8') as f:
            f.write(('' if have.endswith('\n') or not have else '\n') + (MARK + '\n' if MARK not in have else '') + '\n'.join(todo) + '\n')
    return todo


def _tracked(home, p, run=subprocess.run):
    return bool(_git(home, 'ls-files', '-z', '--', p, run=run).stdout) or _git(home, 'cat-file', '-e', 'HEAD:' + p, run=run).returncode == 0


def _ours_only(p, home, run=subprocess.run):
    """True when `p` is dirty and its pending change only adds our own cache lines (a hand edit of Joey's stays out)."""
    if not _dirty_under(home, [p], run=run, filt=False):
        return False
    d = _git(home, 'diff', 'HEAD', '--', p, run=run).stdout
    add = [l[1:] for l in d.splitlines() if l.startswith('+') and not l.startswith('+++')]
    rem = [l for l in d.splitlines() if l.startswith('-') and not l.startswith('---')]
    return not rem and all(not x.strip() or x in IGNORE or x == MARK for x in add)


def _dirty_under(home, roots, run=subprocess.run, filt=True):
    """Paths git shows as changed / untracked under `roots` (-z: any file name), minus files our ignore patterns cover —
    a tracked file matching IGNORE (a rerun's new screenshot) is not committed again."""
    out = _git(home, 'status', '--porcelain', '-uall', '-z', '--', *roots, run=run).stdout
    res, parts, i = [], out.split('\0'), 0
    while i < len(parts):
        e = parts[i]; i += 1
        if len(e) > 3 and not e.startswith('!!'):
            res.append(e[3:])
            if e[0] in 'RC':
                res.append(parts[i]) if i < len(parts) and parts[i] else None   # the rename's source path: its deletion is committed too
                i += 1
    if filt and res:
        ig = subprocess.run(['git', '-C', home, 'check-ignore', '--no-index', '-z', '--stdin'], input='\0'.join(res) + '\0',
                            capture_output=True, text=True, env=ENV).stdout.split('\0')
        res = [f for f in res if f not in set(ig)]
    return res


def commit_tree(rel, subject, home=None, run=subprocess.run):
    """JSA-412: commit every dirty, non-ignored file below `rel` (a folder or file of the data home, e.g. data/learn) in one
    commit → like commit_paths. For writers whose output is a folder; never reaches outside `rel`."""
    home = home or jpaths.home()
    why = active(home)
    if why:
        return 'skipped: ' + why
    try:
        if not os.path.exists(os.path.join(home, rel)):
            return 'nothing'
        ensure_ignore(home)                                # the patterns first: ignored files must not show as dirty
        files = _dirty_under(home, [rel], run=run)
        return commit_paths(files, subject, home=home, run=run) if files else 'nothing'   # .gitignore rides with the first real commit
    except Exception as e:                                 # noqa: BLE001
        return f'failed: {e}'


def commit_application(folder, subject, home=None, run=subprocess.run):
    """JSA-412: commit every dirty, non-ignored file below applications/<folder> in one commit → like commit_paths.
    The unit of a writer's output is the application folder, so one call after a step covers whatever the step wrote."""
    home = home or jpaths.home()
    f = os.path.normpath(folder)
    if os.path.isabs(f):
        f = os.path.relpath(f, home)                       # an absolute path outside the data home is refused below
    elif not f.startswith('applications' + os.sep):
        f = os.path.join('applications', f)  # paths-ok: relative to the data home
    parts = f.split(os.sep)
    if len(parts) != 2 or parts[0] != 'applications' or parts[1] in ('', '.', '..'):
        return 'nothing'                                   # exactly applications/<one folder>: never '.', '..', config/ …
    return commit_tree(f, subject, home=home, run=run)


def sweep(home=None, quiet_secs=QUIET_SECS, now=None, run=subprocess.run):
    """JSA-412 safety net for writers nobody wired: commit the dirty, non-ignored files under TRACK_ROOTS that have been
    quiet for `quiet_secs` → number of files committed (0 when switched off / nothing). Deletes nothing."""
    home = home or jpaths.home()
    if active(home):
        return 0
    try:
        now = now or time.time()
        ensure_ignore(home)                                # the patterns first: ignored files must not show as dirty
        files = []
        for f in _dirty_under(home, list(TRACK_ROOTS), run=run):
            try:
                if now - os.path.getmtime(os.path.join(home, f)) >= quiet_secs:
                    files.append(f)
            except OSError:
                continue
        if not files:
            return 0
        done = 0
        for i in range(0, len(files), 400):                # argv stays short even for a big backlog
            chunk = files[i:i + 400]
            if commit_paths(chunk, f'data: sweep ({len(chunk)} file(s))', home=home, run=run) == 'committed':
                done += len(chunk)
        return done
    except Exception:                                      # noqa: BLE001
        return 0


def dirty_files(home=None, run=subprocess.run):
    """Paths git shows as changed or untracked (not ignored) in the data home."""
    home = home or jpaths.home()
    return _dirty_under(home, ['.'], run=run, filt=False)


def stale(files, home, now=None, hours=REMIND_HOURS):
    """Pure-ish (tested). [(path, age_hours)] of files whose mtime is older than `hours`, oldest first."""
    now = now or time.time()
    out = []
    for f in files:
        try:
            age = (now - os.path.getmtime(os.path.join(home, f))) / 3600
        except OSError:
            continue
        if age > hours:
            out.append((f, age))
    return sorted(out, key=lambda x: -x[1])


def reminder(home=None, now=None, hours=REMIND_HOURS, run=subprocess.run):
    """'' when nothing is overdue; else a short English note naming the count and the oldest files."""
    home = home or jpaths.home()
    if not os.path.exists(os.path.join(home, '.git')) or os.path.realpath(home) == os.path.realpath(jpaths.REPO):
        return ''
    old = stale(dirty_files(home, run=run), home, now, hours)
    if not old:
        return ''
    names = ', '.join(f'{f} ({a / 24:.0f} d)' if a >= 48 else f'{f} ({a:.0f} h)' for f, a in old[:3])
    return (f'DATA HOME GIT (JSA-358): {len(old)} file(s) uncommitted for more than {hours} h — oldest: {names}. '
            "A writer should have committed them: tell the dev lead, or commit them if they are the user's own.")


def main(a):
    cmd = a[0] if a else 'reminder'
    if cmd == 'ignore':
        added = ensure_ignore()
        print('added: ' + ', '.join(added) if added else 'already ignored')
        return 0
    if cmd == 'sweep':
        n = sweep()
        print(f'swept {n} file(s)')
        return 0
    if cmd == 'reminder':
        r = reminder()
        if r:
            print(r)
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
