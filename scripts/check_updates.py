#!/usr/bin/env python3
"""Pre-commit check: files that must change together (docs/agent/developing.md "What to update after each kind of work", Joey 2026-10-31).

Looks only at the staged file list (+ the staged / HEAD text of BACKLOG.md and the runner ledgers). It catches a
forgotten companion file, not wrong content. Blocks the commit on an error; warnings are printed only.
Routine commits that touch only data/store/ (08:15 / 08:45 / 10:00 / 10:05 LaunchAgents) always pass.

    python3 scripts/check_updates.py            # what the hook runs (staged changes)
    git commit --no-verify                      # skip on purpose (e.g. a typo fix)
When you add a row to that table (docs/agent/developing.md), add its rule here and a case in scripts/test_check_updates.py.
"""
import datetime, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = ('skills/auto-apply/runner/run.py', 'skills/auto-apply/runner/run_wd.py', 'skills/auto-apply/runner/run_form.py',
          'skills/auto-apply/runner/plan_build.py', 'skills/auto-apply/runner/prep_batch.py')
CODE = re.compile(r'\.(py|js|sh|plist)$|SKILL\.md$')


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import backlog                                                    # placement rule (JSA-214)
except ImportError:
    backlog = None


def git(*a):
    return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True).stdout


def backlog_status(text):
    """{JSA-NNN: status} from a BACKLOG.md text (8-column table: ID | Pri | Area | Item | Owner | Status | …)."""
    out = {}
    for line in (text or '').splitlines():
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) >= 6 and re.fullmatch(r'JSA-\d{3}', c[0]):
            out[c[0]] = c[5]
    return out


def jsonl(text):
    rows = []
    for l in (text or '').splitlines():
        try: rows.append(json.loads(l))
        except Exception: pass
    return rows


def check(staged, new_text, old_text, today=None, fmap=None, session_log_exists=False):
    """Pure rules (tested). staged = list of paths; new_text / old_text(path) = staged / HEAD content or ''.
    fmap = application folder → job id. Returns (errors, warnings)."""
    S, E, W = set(staged), [], []
    if not S or all(p.startswith('data/store/') for p in S):
        return E, W                                                   # the daily routines
    has = lambda *ps: any(p in S for p in ps)
    if 'BACKLOG.md' in S:
        old, new = backlog_status(old_text('BACKLOG.md')), backlog_status(new_text('BACKLOG.md'))
        done = sorted(k for k, v in new.items() if v == 'done' and old.get(k) != 'done')
        if done and 'ROADMAP.md' not in S:
            E.append(f"BACKLOG: {', '.join(done)} moved to done — update ROADMAP.md (已完成 + Now / Next / Later)")
        if backlog:                                                   # JSA-214: a row in another status / area table
            key = lambda m: (m['id'], m['status'], m['area'], m['section'], m['group'])
            was = {key(m) for m in backlog.misplaced(old_text('BACKLOG.md'))}
            for m in backlog.misplaced(new_text('BACKLOG.md')):
                where = f"{m['section'] or '-'}/{m['group'] or '-'}"
                msg = (f"BACKLOG placement: {m['id']} is {m['status']}/{m['area']} but sits in the {where} table "
                       f"(line {m['line']}) — run `{backlog.FIX_CMD}` and re-stage BACKLOG.md")
                (W if key(m) in was else E).append(msg + (' (already there before this commit)' if key(m) in was else ''))
    if has('skills/auto-apply/scripts/answer_rules.js'):
        if not has('skills/auto-apply/scripts/cx_bundle.js'):
            E.append('answer_rules.js changed — run `python3 build_bundle.py` (skills/auto-apply/scripts) and stage cx_bundle.js')
        if not has('skills/auto-apply/scripts/test/t_rules.js'):
            W.append('answer_rules.js changed without a new case in test/t_rules.js')
    if has('config/profile.json') and not has('skills/auto-apply/scripts/cx_bundle.js'):   # JSA-077: the bundle embeds the profile
        E.append('config/profile.json changed — run `python3 build_bundle.py` (skills/auto-apply/scripts) and stage cx_bundle.js (it embeds the profile)')
    if has('skills/job-hunt-pipeline/scripts/eligibility_rules.js') and not has('skills/job-hunt-pipeline/scripts/eligibility_rules_test.js'):
        E.append('eligibility_rules.js changed — add a case to eligibility_rules_test.js')
    if any(p in S for p in RUNNER) and not any(re.match(r'skills/(ats-[\w-]+|auto-apply)/SKILL\.md$', p) for p in S):
        E.append('runner code changed (' + ', '.join(os.path.basename(p) for p in sorted(S & set(RUNNER))) +
                 ') — record the flow change or pitfall in skills/ats-<platform>/SKILL.md or skills/auto-apply/SKILL.md')
    if 'data/runner/results.jsonl' in S:
        old_keys = {json.dumps(r, sort_keys=True) for r in jsonl(old_text('data/runner/results.jsonl'))}
        added = [r for r in jsonl(new_text('data/runner/results.jsonl')) if r.get('status') == 'submitted' and json.dumps(r, sort_keys=True) not in old_keys]
        tracked = {a.get('job_id') for a in jsonl(new_text('data/store/applications.jsonl') or old_text('data/store/applications.jsonl'))}
        for r in added:
            jid = (fmap or {}).get(r.get('folder'))
            if not jid:
                W.append(f"submitted {r.get('folder')}: no job id found — check the tracker by hand")
            elif jid not in tracked:
                E.append(f"submitted {r.get('folder')} ({jid}) is not in data/store/applications.jsonl — run scripts/store/sync_results.py")
    if any(re.match(r'scripts/launchagent/.+\.plist$', p) for p in S) and 'CLAUDE.md' not in S:
        E.append('a LaunchAgent plist changed — update the "Local routines" table in CLAUDE.md (and ARCHITECTURE.md)')
    if any(CODE.search(p) for p in S) and not session_log_exists and not any('references/session-log-' in p for p in S):
        W.append(f"no session log for {today or datetime.date.today().isoformat()} yet (skills/job-search-agent/references/)")
    return E, W


def main():
    staged = [p for p in git('diff', '--cached', '--name-only', '--diff-filter=ACMR').splitlines() if p]
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        import use_guard                                             # the main checkout is the using system (ADR-0008)
    except ImportError:                                              # the public export ships without the author's two-system tools (Joey 11-05)
        use_guard = None
    if os.path.exists(os.path.join(ROOT, '.jsa-release')):          # a release checkout (scripts/release.py): never commit here
        print('use_guard: commit refused — this folder is a release (read-only code, ADR-0008); change code in a worktree', file=sys.stderr)
        return 1
    if use_guard and not os.environ.get('JSA_DEV_IN_MAIN') and use_guard.is_main_checkout(ROOT):
        gone = [p for p in git('diff', '--cached', '--name-only', '--diff-filter=D').splitlines() if p]
        bad = use_guard.blocked(staged + gone)
        if bad:
            print(use_guard.message(bad), file=sys.stderr)
            return 1
    new_text = lambda p: git('show', f':{p}')
    old_text = lambda p: git('show', f'HEAD:{p}')
    today = datetime.date.today().isoformat()
    log = os.path.exists(os.path.join(ROOT, 'skills', 'job-search-agent', 'references', f'session-log-{today}.md'))
    fmap = None
    if 'data/runner/results.jsonl' in staged:
        sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
        try:
            import sync_results; fmap = sync_results.folder_job_ids()
        except Exception:
            fmap = {}
    E, W = check(staged, new_text, old_text, today, fmap, log)
    if 'BACKLOG.md' in staged:
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'backlog.py'), '--check'], capture_output=True, text=True)
        if r.returncode:
            E.append('backlog.py --check failed: ' + (r.stdout + r.stderr).strip().splitlines()[0][:200])
    if 'skills/auto-apply/scripts/answer_rules.js' in staged:
        r = subprocess.run(['node', 'test/t_rules.js'], cwd=os.path.join(ROOT, 'skills', 'auto-apply', 'scripts'), capture_output=True, text=True)
        if r.returncode:
            E.append('node test/t_rules.js failed: ' + (r.stdout.strip().splitlines() or ['?'])[-1][:200])
    for w in W:
        print('check_updates: note —', w, file=sys.stderr)
    if E:
        print('check_updates: commit blocked — companion files missing (docs/agent/developing.md "What to update after each kind of work"):', file=sys.stderr)
        for e in E:
            print('  ✗', e, file=sys.stderr)
        print('  fix and re-commit, or `git commit --no-verify` if it really does not apply', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
