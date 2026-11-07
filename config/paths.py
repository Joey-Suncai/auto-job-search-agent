"""Where the using system's files live (ADR-0008 stage 3, step 1 — docs/specs/ops-use-dev-split.md).

The data home (data/, applications/, resume/, config/ facts) = $JSA_HOME, else the path in ~/.config/job-search-agent/home,
else this repository (the layout before the split). Code never builds those paths itself any more:

    sys.path.insert(0, <repo>/config); import paths
    paths.data('store', 'jobs.jsonl')   paths.apps('<folder>')   paths.resume('2026-10', 'x.pdf')   paths.config('profile.json')
    paths.folder('applications/<folder>')   # a folder argument as typed on the command line → an existing absolute path
    paths.at('dashboard')   paths.bundle()       # other using-system output: the dashboard page, the browser bundle

Tests: scripts/test_paths.py (DeepSeek cases) and scripts/test_paths_literal.py (no hard-coded data paths in code).
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POINTER = os.path.join('~', '.config', 'job-search-agent', 'home')   # one line: the data home's path (ADR-0008 step 4)


def pointed(pointer=None):
    """The data home named in the pointer file (~/.config/job-search-agent/home), or None when there is none / it is empty."""
    p = os.path.expanduser(pointer or os.environ.get('JSA_HOME_POINTER') or POINTER)
    try:
        h = open(p, encoding='utf-8').read().strip()
    except OSError:
        return None
    return os.path.abspath(os.path.expanduser(h)) if h else None


def home():
    """The data home: $JSA_HOME (~ expanded), else the pointer file, else the repository. Every program on this Mac —
    routines, runners, terminals, sessions — finds the data the same way; deleting the pointer file goes back to the old
    layout. A release checkout (it holds .jsa-release, made by scripts/release.py) never uses itself as the data home:
    with neither set it stops (JSA_ALLOW_REPO_HOME=1 lets its own tests use the repo's fixtures)."""
    h = os.environ.get('JSA_HOME')
    if h:
        return os.path.abspath(os.path.expanduser(h))
    p = pointed()
    if p:
        return p
    if os.path.exists(os.path.join(REPO, '.jsa-release')) and not os.environ.get('JSA_ALLOW_REPO_HOME'):
        raise RuntimeError(f'{REPO} is a release (read-only code): set JSA_HOME or {POINTER} to the data home (ADR-0008)')
    return REPO


def data(*p):
    return os.path.join(home(), 'data', *p)


def apps(*p):
    return os.path.join(home(), 'applications', *p)


def resume(*p):
    return os.path.join(home(), 'resume', *p)


def config(*p):
    """The user's own config files (facts). The fictional .example files and fixtures stay in the repository."""
    return os.path.join(home(), 'config', *p)


def at(*p):
    """Any other output that belongs to the using system (the dashboard page, the live map page) — under the data home."""
    return os.path.join(home(), *p)


def bundle():
    """The browser bundle cx_bundle.js (it embeds the profile, so it is data): the repo's old place until JSA_HOME is set,
    then the data home's data/ folder."""
    if home() != REPO:
        return data('cx_bundle.js')
    return os.path.join(REPO, 'skills', 'auto-apply', 'scripts', 'cx_bundle.js')


def folder(arg, cwd=None):
    """An application-folder argument → absolute path. An absolute argument is used as is. A relative one is looked up
    under the data home FIRST ("applications/<name>" or "<name>" → home/applications/<name>) — the code checkout may hold a
    stale partial copy of a folder — then relative to `cwd`. Returns the first that exists, else the cwd-relative path
    (so the caller's own "not found" message still names what was typed)."""
    if not arg:
        return arg
    a = os.path.expanduser(str(arg))
    if os.path.isabs(a):
        return a
    given = os.path.abspath(os.path.join(cwd or os.getcwd(), a))
    rel = os.path.normpath(a)
    name = rel[len('applications' + os.sep):] if rel.startswith('applications' + os.sep) else rel
    return next((t for t in (apps(name), given) if os.path.isdir(t)), given)
