#!/usr/bin/env python3
"""JSA-412: data_git.commit_application / sweep / the ignore list — real git in temp folders. The case table
(cases_data_git_sweep.json) was written by DeepSeek from the spec alone (rule 13); every disagreement was judged by hand
(see JUDGED below).  python3 scripts/store/test_data_git_sweep.py"""
import json, os, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for k in ('JSA_NO_DATA_GIT', 'JSA_DATA_GIT_DEFER'):
    os.environ.pop(k, None)
import data_git as D  # noqa: E402

bad = 0
JUDGED = {}   # case name → why the table was wrong (filled below when needed)


def check(name, got, want):
    global bad
    if got != want:
        bad += 1; print('FAIL', name, '| got', repr(got)[:200], '| want', repr(want)[:200])


def g(home, *a):
    return subprocess.run(['git', '-C', home, *a], capture_output=True, text=True, env=D.ENV).stdout


def repo():
    h = tempfile.mkdtemp(prefix='jsa_dgs_')
    g(h, 'init', '-q', '-b', 'main'); g(h, 'config', 'user.email', 't@example.com'); g(h, 'config', 'user.name', 't')
    open(os.path.join(h, 'README'), 'w').write('x'); g(h, 'add', '.'); g(h, 'commit', '-q', '-m', 'init')
    return h


def put(h, rel, text='a', age=0):
    p = os.path.join(h, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(text)
    if age:
        t = time.time() - age; os.utime(p, (t, t))
    return p


def norm(p):
    return p.strip('/')


def run_case(c):
    h = repo()
    for t in c.get('tracked_already') or []:
        put(h, norm(t), 'old')
    if c.get('tracked_already'):
        g(h, 'add', '-A'); g(h, 'commit', '-q', '-m', 'seed')
    for f in c['files']:
        put(h, norm(f['path']), f.get('content') or 'x', f.get('age_seconds') or 0)
    n0 = g(h, 'rev-list', '--count', 'HEAD').strip()
    if c['call'] == 'commit_application':
        got = D.commit_application(c['args']['folder'], 'data: t', home=h)
    else:
        got = D.sweep(home=h, quiet_secs=c['args'].get('quiet_secs', D.QUIET_SECS))
    committed = set(g(h, 'show', '--name-only', '--format=', 'HEAD').split()) - {'.gitignore'} if g(h, 'rev-list', '--count', 'HEAD').strip() != n0 else set()
    dirty = set(D.dirty_files(h))
    return h, got, committed, dirty


cases = json.load(open(os.path.join(HERE, 'cases_data_git_sweep.json'), encoding='utf-8'))
for c in cases:
    if c.get('ambiguous'):
        continue
    h, got, committed, dirty = run_case(c)
    n = c['name']
    check(n + ' | return', got, c['expect_return'])
    check(n + ' | committed', committed, {norm(p) for p in c['expect_committed']})
    check(n + ' | dirty after', {d for d in dirty if d != '.gitignore'}, {norm(p) for p in c['expect_dirty_after']})

# switched off (the two ambiguous cases, judged by hand): no repo / JSA_NO_DATA_GIT
plain = tempfile.mkdtemp(prefix='jsa_dgs_plain_'); put(plain, 'applications/a/x.txt', 'x', 9999)
check('no repo → commit_application skipped', D.commit_application('a', 's', home=plain)[:7], 'skipped')
check('no repo → sweep 0', D.sweep(home=plain, quiet_secs=0), 0)
h = repo(); put(h, 'applications/a/x.txt', 'x', 9999); os.environ['JSA_NO_DATA_GIT'] = '1'
check('env → commit_application skipped', D.commit_application('a', 's', home=h)[:7], 'skipped')
check('env → sweep 0', D.sweep(home=h, quiet_secs=0), 0)
del os.environ['JSA_NO_DATA_GIT']
# nothing is ever deleted; the ignore list is idempotent and carries the JSA-412 patterns
check('file still there', os.path.exists(os.path.join(h, 'applications/a/x.txt')), True)
D.ensure_ignore(h)
check('ignore idempotent', D.ensure_ignore(h), [])
lines = open(os.path.join(h, '.gitignore')).read().splitlines()
for pat in ('applications/*/filled_check.png', '*.lock', 'data/learn/triage_cache.jsonl', 'data/runner/qtype_cache.jsonl', 'data/runner/final_review_cache.jsonl'):
    check('ignored ' + pat, pat in lines, True)
check('proof screenshot not ignored', 'applications/*/submitted_confirmation.png' in lines, False)
# a rename inside the folder is parsed (porcelain -z has two entries)
h = repo(); put(h, 'applications/a/old.md', 'x'); g(h, 'add', '-A'); g(h, 'commit', '-q', '-m', 's')
g(h, 'mv', 'applications/a/old.md', 'applications/a/new.md')
check('rename committed', D.commit_application('a', 's', home=h), 'committed')
# --- review findings (JSA-412 review) ---
# tracked file matching an ignore pattern: a rerun's new screenshot is not committed again
h = repo(); put(h, 'applications/a/filled_check.png', 'v1'); put(h, 'applications/a/x.md', 'v1'); g(h, 'add', '-Af'); g(h, 'commit', '-q', '-m', 's')
put(h, 'applications/a/filled_check.png', 'v2'); put(h, 'applications/a/x.md', 'v2')
check('tracked+ignored png not recommitted', D.commit_application('a', 's', home=h), 'committed')
check('only x.md in commit', set(g(h, 'show', '--name-only', '--format=', 'HEAD').split()) - {'.gitignore'}, {'applications/a/x.md'})
# deletion is committed; rename commits both sides
os.remove(os.path.join(h, 'applications/a/x.md'))
check('deletion committed', D.commit_application('a', 's', home=h), 'committed')
check('deleted file gone from HEAD', 'applications/a/x.md' in g(h, 'ls-tree', '-r', '--name-only', 'HEAD').split(), False)
h = repo(); put(h, 'applications/a/old.md', 'x'); g(h, 'add', '-A'); g(h, 'commit', '-q', '-m', 's'); g(h, 'mv', 'applications/a/old.md', 'applications/a/new.md')
D.commit_application('a', 's', home=h)
tree = g(h, 'ls-tree', '-r', '--name-only', 'HEAD').split()
check('rename: new in HEAD, old gone, index clean', ('applications/a/new.md' in tree, 'applications/a/old.md' in tree, g(h, 'status', '--porcelain').strip()), (True, False, ''))
# folder argument cannot leave applications/<one folder>
h = repo(); put(h, 'config/profile.json', '{}'); put(h, 'applications/a/x.md', 'x'); put(h, 'applications/b/y.md', 'y')
for bad_arg in ('applications/../config', '.', '..', 'applications', '/tmp/elsewhere/applications/a'):
    check('refused ' + bad_arg, D.commit_application(bad_arg, 's', home=h), 'nothing')
check('nothing committed by refused calls', sorted(D.dirty_files(h)), ['applications/a/x.md', 'applications/b/y.md', 'config/profile.json'])
check('absolute path inside the home accepted', D.commit_application(os.path.join(h, 'applications/a'), 's', home=h), 'committed')
# non-ASCII names are seen by dirty_files (the reminder)
put(h, 'applications/公司/x.md', 'x', 10 * 3600)
check('non-ascii dirty', 'applications/公司/x.md' in D.dirty_files(h), True)
# a hand edit of .gitignore does not ride along
open(os.path.join(h, '.gitignore'), 'a').write('my_own_line\n')
put(h, 'applications/a/z.md', 'z'); D.commit_application('a', 's', home=h)
check('hand edit of .gitignore stays dirty', '.gitignore' in D.dirty_files(h), True)
print('data_git sweep: all passed' if not bad else f'{bad} FAILED'); sys.exit(1 if bad else 0)
