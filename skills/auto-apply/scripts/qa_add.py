#!/usr/bin/env python3
"""Save the user's answer to a form question the rules did not know (JSA-164, Joey 2026-11-05) — the using-session way:
no code change, no new test. The answer goes into config/profile.json → qa; answer_rules.js reads it for every later form
that asks the same question (only where no rule answers it).

    python3 qa_add.py --q "Do you have a valid driver's license?" --no --source "Joey 2026-11-05 (Acme form)"
    python3 qa_add.py --q "Preferred shift" --pick "Day shift" --source "…"          # a list: the option to choose
    python3 qa_add.py --q "Years of Python experience" --text "3" --source "…"       # a text box
    python3 qa_add.py --q "…" --match "/driver'?s licen[cs]e/i" --yes --source "…"  # also other wordings (regex)
    python3 qa_add.py --q "…" --pick "/chicago/i" --box "Chicago, IL" --source "…"    # a list pick AND the text for a text box (JSA-419)
    python3 qa_add.py --extend-entry 117 --q "<the wording>" --pick "/^none$/i" --box "0" --source "…"   # more picks / a box value on a saved entry
    python3 qa_add.py --batch answers.json                                              # many answers: one replay + one commit (JSA-420)
    python3 qa_add.py --list                                                          # what the table holds
    python3 qa_add.py --check-overlaps                                                # entries that catch the same question (0 = clean)

Before saving, it checks the new entry against the table (JSA-277, Joey 2026-11-10): when an existing entry's question or
--match regex also catches the new question, or the new --match catches an existing entry's question, it stops and names
those entries — nothing is saved. The user then decides, and the command is run again with one of:
    --replace-entry N                     the new entry takes entry N's place (N from the stop message or --list)
    --narrow-entry N --narrow-match "/re/i"   entry N's regex becomes the narrower one ("-" drops its regex), then the new entry is added
    --add-anyway                          keep both (answer_rules tries the newest matching entry first, then older ones)

Run it from the checkout the runners use (the main folder), so the live runners see the answer. It writes the profile,
rebuilds cx_bundle.js (the browser bundle embeds the profile), checks that answer_rules now answers the question, adds a
dated line to the decisions log (the data home's facts/decisions-log.md via paths.fact — the repo's old
skills/_shared/decisions-log.md only while the data home has none; JSA-339) and commits those files (--no-commit to skip).
Turning a frequent entry into a real rule (answer_rules.js + DeepSeek cases) is development work (CONTRIBUTING.md).
"""
import argparse, fcntl, json, os, re, subprocess, sys, tempfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))


class ProfileLock:
    """JSA-420: one writer at a time on config/profile.json (+ the bundle, the log, the data home's commit). Held from reading
    the profile to the commit, NOT during the replay (which only reads): two qa_add runs, or qa_add and a batch session, no
    longer lose each other's entry (read-modify-write) and never wait on a 30 s replay. flock on <profile>.lock: the OS drops
    it when the process dies, so a crashed run never leaves it held. Re-entrant per object only; run_batch holds one lock for
    the whole batch and its items run in-process with `lock=` that object."""
    def __init__(self, profile_path):
        self.path = os.path.abspath(profile_path) + '.lock'
        self.fd = None

    def acquire(self):
        if self.fd is None:
            self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def release(self):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN); os.close(self.fd); self.fd = None

    __enter__ = acquire
    def __exit__(self, *x): self.release()


def write_atomic(path, text):
    """JSA-420: a temp file + os.replace — a reader that does not take the lock (prepare, replay, the runners) sees the old
    or the new profile, never a half-written one."""
    tmp = f'{path}.tmp{os.getpid()}'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(text)
    os.replace(tmp, path)


def norm(s):
    """Pure (tested). The same normalisation answer_rules.js uses for qa questions."""
    s = str(s or '').lower().replace('‘', "'").replace('’', "'")
    s = re.sub(r'\(?\brequired\b\)?|\*', ' ', s)
    return re.sub(r"[^a-z0-9']+", ' ', s).strip()


def entry(q, text=None, yes=None, pick=None, match=None, source='', today=None, box=None):
    """Pure (tested). The qa entry for one answer; ValueError when it holds no answer or more than one kind. box (JSA-419) = the
    value for a TEXT box, only beside --pick (a list answer saved as a pattern cannot be typed into a box)."""
    if not norm(q) and not match:
        raise ValueError('the question is empty')
    kinds = [k for k, v in (('text', text), ('yes', yes), ('pick', pick)) if v not in (None, '', [])]
    if len(kinds) != 1:
        raise ValueError('give exactly one answer: --text, --yes / --no, or --pick')
    if match and not re.fullmatch(r'/.+/[a-z]*', match):
        raise ValueError('--match must look like /regex/i')
    e = {'q': q.strip()}
    if match:
        e['match'] = match
    if text not in (None, ''):
        e['text'] = text
    if yes is not None:
        e['yes'] = bool(yes)
    if pick:
        rx = lambda p: re.fullmatch(r'/.+/[a-z]*', p.strip())        # a pick already written as /regex/i (a pattern principle, JSA-237)
        e['pick'] = [p.strip() if rx(p) else '/^' + re.escape(p.strip()) + '$/i' for p in pick]
        e['text'] = next((p.strip() for p in pick if not rx(p)), re.sub(r'^/|/[a-z]*$', '', pick[0].strip()))
    if box not in (None, ''):
        if not pick:
            raise ValueError('--box is the text-box value beside --pick; for a text box alone use --text')
        e['box'] = box
    e['source'] = source or 'user'
    e['added'] = today or date.today().isoformat()
    return e


def extend(old, pick=None, box=None, source=None, today=None):
    """Pure (tested, JSA-419). A copy of a saved entry with more picks (list shape) and / or a text-box value — the entry's
    wording, regex, yes and earlier picks stay. ValueError when there is nothing to add."""
    if not pick and box in (None, ''):
        raise ValueError('--extend-entry needs --pick and / or --box')
    if old.get('retired'):
        raise ValueError('that entry is retired (it never answers)')
    e = dict(old)
    if pick:
        add = entry(old.get('q') or 'x', pick=pick)['pick']
        e['pick'] = list(old.get('pick') or []) + [p for p in add if p not in (old.get('pick') or [])]
    if box not in (None, ''):
        e['box'] = box
    if source:
        e['source'] = (old.get('source') or '') + '; ' + source
    e['added'] = today or date.today().isoformat()
    return e


def add(profile, e, replace=False):
    """Pure (tested). Profile dict + entry → (profile, 'added' | 'replaced'); ValueError on a duplicate without replace."""
    qa = profile.setdefault('qa', [])
    i = next((k for k, x in enumerate(qa) if norm(x.get('q')) == norm(e['q'])), None)
    if i is not None:
        if not replace:
            raise ValueError(f'already in the table (#{i + 1}): {qa[i].get("q")!r} — use --replace')
        qa[i] = e
        return profile, 'replaced'
    qa.append(e)
    return profile, 'added'


def change(profile, e, replace=False, replace_entry=None, narrow_entry=None, narrow_match=None):
    """Pure (tested). Profile + new entry + the user's choice on an overlap → (profile, how). replace_entry N = entry N
    (1-based) becomes the new one; narrow_entry N = entry N's match becomes narrow_match ('-' = no regex) first, then the
    new entry is added. ValueError on a bad number or an entry left with no question to match."""
    qa = profile.setdefault('qa', [])
    for n in (replace_entry, narrow_entry):
        if n is not None and not 1 <= n <= len(qa):
            raise ValueError(f'no entry #{n} (the table has {len(qa)})')
    if replace_entry is not None:
        if any(k != replace_entry - 1 and norm(x.get('q')) == norm(e['q']) for k, x in enumerate(qa)):
            raise ValueError('the same question is already another entry — use --replace')
        qa[replace_entry - 1] = e
        return profile, f'replaced #{replace_entry}'
    if narrow_entry is not None:
        old = qa[narrow_entry - 1]
        if narrow_match in (None, ''):
            raise ValueError('--narrow-entry needs --narrow-match "/regex/i" (or "-" to drop its regex)')
        if narrow_match == '-':
            if not norm(old.get('q')):
                raise ValueError(f'entry #{narrow_entry} has no question; it cannot lose its regex')
            old.pop('match', None)
        elif not re.fullmatch(r'/.+/[a-z]*', narrow_match):
            raise ValueError('--narrow-match must look like /regex/i')
        else:
            old['match'] = narrow_match
        profile, how = add(profile, e, replace)
        return profile, f'{how} (#{narrow_entry} narrowed)'
    return add(profile, e, replace)


def overlap_lines(res):
    """Pure (tested). qa_overlap.js --entry result → the lines that name each overlapping entry; [] = no overlap."""
    out = []
    for key, what in (('catches_it', 'also catches this question'), ('it_catches', "is caught by this entry's regex")):
        for x in res.get(key) or []:
            pat = f" pattern {x['match']}" if x.get('match') else ''
            out.append(f"  #{x['n']} {what}: {x['q'][:90]!r}{pat} → {str(x.get('answer'))[:50]!r} ({x.get('source')}, {x.get('added')})")
    return out


def overlaps(profile_path, entry_n=None, options=None):
    """Ask qa_overlap.js (answer_rules.js matching) about one entry (1-based) or, with None, the whole table. options = the form
    field's option list ([] = a text box; None = shape unknown): an older entry that catches the question but gives no answer on
    that shape is no overlap (JSA-333: a list-answer entry on a text box, or whose picks match none of this form's options). Only the "older entry catches the new question" direction is filtered; a new entry with the same question or a regex over an old question always blocks."""
    env = dict(os.environ, JSA_PROFILE=profile_path)
    shape = [] if options is None else ['--options', '|'.join(options)]
    r = subprocess.run(['node', os.path.join(HERE, 'qa_overlap.js')] + (['--entry', str(entry_n)] + shape if entry_n else ['--all']),
                       capture_output=True, text=True, env=env, timeout=60)
    if r.returncode:
        raise RuntimeError('qa_overlap.js: ' + (r.stderr or r.stdout).strip()[:300])
    return json.loads(r.stdout)


def check_shapes(q, shapes, profile_path):
    """JSA-241: the question seen with several option lists (merged prefetch entry) → the first answer that is ok on any list,
    else the first miss. shapes = [] / [[]] = a text box."""
    miss = None
    for opts in shapes or [[]]:
        got = check(q, opts, profile_path)
        if got.get('status') == 'ok':
            return got
        miss = miss or got
    return miss or {}


def check(q, options, profile_path):
    """Ask answer_rules.js (through rules_bridge.js) for the question → its answer dict."""
    typ = 'text' if not options else ('checkbox' if len(options) == 1 else 'select')   # JSA-419: a one-option field is a tick box (the consent boxes)
    fields = [{'key': 'x', 'label': q, 'type': typ, 'options': options or []}]
    env = dict(os.environ, JSA_PROFILE=profile_path)
    r = subprocess.run(['node', os.path.join(HERE, '..', 'runner', 'rules_bridge.js'), os.path.join(HERE, 'answer_rules.js')],
                       input=json.dumps({'fields': fields, 'jd': '', 'company': ''}), capture_output=True, text=True, env=env, timeout=60)
    return (json.loads(r.stdout or '{}') or {}).get('x') or {}


def main(argv=None, lock=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--q', help='the question exactly as the form wrote it')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--text'); g.add_argument('--yes', action='store_true'); g.add_argument('--no', action='store_true')
    g.add_argument('--pick', action='append', help='the option to choose (repeat for fallbacks)')
    ap.add_argument('--match', help='also match other wordings: /regex/i')
    ap.add_argument('--box', help='with --pick: the value to type when the same question is a TEXT box (JSA-419)')
    ap.add_argument('--extend-entry', type=int, help='add --pick values and / or a --box value to entry N (its wording and earlier picks stay); --q = the wording to check (JSA-419)')
    ap.add_argument('--options', help='the options the form showed, "|"-separated (for the check)')
    ap.add_argument('--options-json', action='append', help='one option list as JSON (repeat per list a merged question was seen with; options may hold "|")')
    ap.add_argument('--source', default='', help='who answered and where, e.g. "Joey 2026-11-05 (Acme form)"')
    ap.add_argument('--replace', action='store_true'); ap.add_argument('--no-commit', action='store_true')
    ap.add_argument('--no-replay', action='store_true', help='skip the form replay (about 30 s over the stored forms); --batch runs it once at the end (JSA-420)')
    ap.add_argument('--batch', help='JSON file: a list of answers [{q, text | yes | no | pick[], box, match, options, options_json[], source, replace, replace_entry, extend_entry}] saved in one go: '
                    'one profile write per answer, ONE replay and ONE commit for all (JSA-420)')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--check-overlaps', action='store_true', help='list entries that catch the same question (JSA-277)')
    ap.add_argument('--replace-entry', type=int, help='on an overlap: the new entry replaces entry N')
    ap.add_argument('--narrow-entry', type=int, help='on an overlap: give entry N the regex --narrow-match, then add')
    ap.add_argument('--narrow-match', help='with --narrow-entry: /regex/i, or - to drop its regex')
    ap.add_argument('--add-anyway', action='store_true', help='on an overlap: keep both entries')
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import paths as jp0
    ap.add_argument('--profile', default=os.environ.get('JSA_PROFILE') or jp0.config('profile.json'))   # the data home's profile (ADR-0008)
    a = ap.parse_args(argv)
    own = lock is None
    lk = lock or ProfileLock(a.profile)
    if not (a.list or a.check_overlaps or a.batch):
        lk.acquire()
    try:
        return _main(a, ap, lk, own)
    finally:
        if own:
            lk.release()


def _main(a, ap, lk, own=True):
    try:
        shapes = [json.loads(j) for j in (a.options_json or [])]
        if not all(isinstance(l, list) and all(isinstance(o, str) for o in l) for l in shapes):
            raise ValueError('each --options-json must be a JSON list of strings')
    except ValueError as ex:
        print('qa_add: --options-json:', ex); return 1
    shapes = [[o.strip() for o in l] for l in shapes] or ([[o.strip() for o in a.options.split('|') if o.strip()]] if a.options else [])
    union = [o for l in shapes for o in l]                         # JSA-241: the lists a merged question was seen with
    prof = json.load(open(a.profile, encoding='utf-8'))
    if a.list:
        for n, e in enumerate(prof.get('qa') or [], 1):
            ans = e.get('text') if 'text' in e else ('Yes' if e.get('yes') else 'No')
            print(f"{n:3}. {e.get('q')!r} → {ans!r}  ({e.get('source')}, {e.get('added')})")
        return 0
    if a.check_overlaps:
        res = overlaps(a.profile)
        print(f"qa_add: {len(prof.get('qa') or [])} entries; {len(res)} question(s) caught by 2+ entries")
        for o in res:
            print(f"\n#{o['n']} {o['q'][:100]!r}")
            for x in o['entries']:                                # newest first = the order answer_rules tries them
                print(f"  #{x['n']} {x.get('added')} → {str(x.get('answer'))[:50]!r}" + (f"  pattern {x['match'][:70]}" if x.get('match') else ''))
        return 1 if res else 0
    if a.batch:
        return run_batch(a)
    if not a.q:
        ap.error('--q is required')
    yes = True if a.yes else (False if a.no else None)
    try:
        if a.extend_entry is not None:
            n = a.extend_entry
            if not 1 <= n <= len(prof.get('qa') or []):
                raise ValueError(f'no entry #{n} (the table has {len(prof.get("qa") or [])})')
            if a.text or a.yes or a.no or a.match:
                raise ValueError('--extend-entry takes only --pick and --box')
            e = extend(prof['qa'][n - 1], a.pick, a.box, source=a.source)
            prof['qa'][n - 1] = e; how = f'extended #{n}'
        else:
            e = entry(a.q, a.text, yes, a.pick, a.match, a.source, box=a.box)
            prof, how = change(prof, e, a.replace, a.replace_entry, a.narrow_entry, a.narrow_match)
    except ValueError as ex:
        print('qa_add:', ex); return 1
    raw = open(a.profile, encoding='utf-8').read()
    indent = 1 if raw.startswith('{\n "') else 2
    pos = next(k for k, x in enumerate(prof['qa'], 1) if x is e)
    import tempfile
    with tempfile.TemporaryDirectory() as td:                    # JSA-277: the table as it would be, checked before it is saved
        tmp = os.path.join(td, 'profile.json')
        json.dump(prof, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
        res = {} if a.extend_entry is not None else overlaps(tmp, pos, options=union if (shapes or a.options is not None) else None)   # no --options = shape unknown: every catching entry blocks (an extended entry keeps its place: no new overlap)
    lines = overlap_lines(res)
    hits = {x['n'] for k in ('catches_it', 'it_catches') for x in res.get(k) or []}
    if lines and not a.add_anyway:
        print(f"qa_add: NOT saved — the new entry overlaps {len(hits)} saved entr{'y' if len(hits) == 1 else 'ies'} (#{', #'.join(map(str, sorted(hits)))}; the same question would match both):")
        print('\n'.join(lines))
        print("qa_add: ask the user, then run again with --replace-entry N, --narrow-entry N --narrow-match \"/re/i\", or --add-anyway")
        return 1
    if lines:
        print('qa_add: overlap kept (--add-anyway) — answer_rules tries the newest matching entry first:\n' + '\n'.join(lines))
    write_atomic(a.profile, json.dumps(prof, ensure_ascii=False, indent=indent) + '\n')
    got = check_shapes(a.q, shapes, a.profile)
    if got.get('status') == 'ok' and e.get('box') and e.get('yes') is None:    # JSA-419: the text-box shape of the same question
        gb = check(a.q, [], a.profile)
        if gb.get('status') != 'ok':
            got = gb
    if got.get('status') == 'ok' and len(shapes) > 1:             # JSA-241 review: an answer found on one list only is saved, but say so
        missed = [i + 1 for i, l in enumerate(shapes) if check(a.q, l, a.profile).get('status') != 'ok']
        if missed:
            print(f"qa_add: warning — the answer matches no option on list(s) {missed} of {len(shapes)}: forms with those lists will still ask")
    if got.get('status') != 'ok':                                 # never leave an entry that does not work: put the file back
        write_atomic(a.profile, raw)
        if got.get('ask') and got.get('rule') in ('referral', 'know_employee', 'how_heard'):   # JSA-195: decided per company by the referrer pool
            print("qa_add: NOT saved — referral questions are answered per company from the referrer pool (config/connections.json): "
                  "not in the pool = no referral, in the pool = the user is asked; the qa table cannot answer them"); return 1
        print(f"qa_add: NOT saved — answer_rules still does not answer it with this entry: {got}"); return 1
    if not str(got.get('rule', '')).startswith('qa:'):
        print(f"qa_add: note — a rule already answers this question ({got.get('rule')} → {got.get('value')!r}); the table entry is only a fallback")
    print(f"qa_add: {how} → answer_rules: {got.get('value')!r} ({got.get('rule')})")
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import paths as jp                                           # the data home (ADR-0008)
    if os.path.abspath(a.profile) == os.path.abspath(jp.config('profile.json')):
        subprocess.run([sys.executable, os.path.join(HERE, 'build_bundle.py')], check=True)
        home = jp.home()
        main_co = os.path.dirname(subprocess.run(['git', '-C', ROOT, 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                              capture_output=True, text=True).stdout.strip()) or ROOT   # the main checkout (docs live there)
        commits = {home: [os.path.relpath(a.profile, home), os.path.relpath(jp.bundle(), home)]}
        log = jp.fact('decisions-log.md')                       # JSA-339: the data home's facts/decisions-log.md
        in_home = log.startswith(os.path.join(home, 'facts') + os.sep)
        if not in_home:                                          # the data home has none yet: the main checkout's old copy (never a release)
            log = os.path.join(main_co, 'skills', '_shared', 'decisions-log.md')
        if os.path.exists(log):
            ans = e.get('text') if 'text' in e else ('Yes' if e.get('yes') else 'No')
            body = open(log, encoding='utf-8').read().rstrip('\n')
            note = '' if how in ('added', 'replaced') else f'; {how}'
            open(log, 'w', encoding='utf-8').write(body + f"\n- {e['added']} — {e['source']}: {e['q']!r} → **{ans}** (config/profile.json qa, qa_add.py{note})\n")
            repo = home if in_home else main_co
            commits.setdefault(repo, []).append(os.path.relpath(log, repo))
        if not a.no_commit:
            msg = f"qa: {e['q'][:60]} → {str(e.get('text', e.get('yes')))[:30]} ({e['source'][:40]})"
            for repo, files in commits.items():                  # one repo when the data home is still this repo
                subprocess.run(['git', '-C', repo, 'add', '--'] + files, check=True)
                r = subprocess.run(['git', '-C', repo, 'commit', '-q', '-m', msg, '--'] + files, capture_output=True, text=True)
                print(f'qa_add: committed in {repo}' if r.returncode == 0 else f'qa_add: not committed in {repo} — ' + (r.stdout + r.stderr).strip()[:300])
        if own:                                                  # a batch's lock (lock=…) is released by run_batch, after its commit
            lk.release()                                         # JSA-420: the replay only reads; never hold the profile for it
        if not a.no_replay:
            try:
                with tempfile.TemporaryDirectory() as td:        # JSA-351: the profile without this entry, to see what it changes
                    old = os.path.join(td, 'profile.json')
                    open(old, 'w', encoding='utf-8').write(raw)
                    replay_after(e, pos, old)                    # JSA-188: what this answer changes on earlier forms
            except OSError as ex:                                # the answer is saved either way
                print(f'qa_add: replay skipped ({ex})')
    return 0


def batch_argv(spec, profile):
    """Pure (tested, JSA-420). One --batch item → the qa_add argument list for it (no replay, no commit: the batch does both once)."""
    if not isinstance(spec, dict) or not spec.get('q') and spec.get('extend_entry') is None:
        raise ValueError(f'a batch item needs a "q": {spec!r}')
    argv = ['--profile', profile, '--no-replay', '--no-commit', f"--source={spec.get('source') or ''}"]   # --flag=value: a value may start with "-"
    if spec.get('q'):
        argv += [f"--q={spec['q']}"]
    if spec.get('yes') is True: argv += ['--yes']
    if spec.get('yes') is False: argv += ['--no']
    for k, flag in (('text', '--text'), ('match', '--match'), ('box', '--box'), ('options', '--options')):
        if spec.get(k) not in (None, ''): argv += [f'{flag}={spec[k]}']
    for p_ in spec.get('pick') or []: argv += [f'--pick={p_}']
    for o in spec.get('options_json') or []: argv += ['--options-json=' + (json.dumps(o) if not isinstance(o, str) else o)]
    for k, flag in (('replace_entry', '--replace-entry'), ('narrow_entry', '--narrow-entry'), ('extend_entry', '--extend-entry')):
        if spec.get(k) is not None: argv += [f'{flag}={spec[k]}']
    if spec.get('narrow_match'): argv += [f"--narrow-match={spec['narrow_match']}"]
    if spec.get('replace'): argv += ['--replace']
    if spec.get('add_anyway'): argv += ['--add-anyway']
    return argv


def changed_numbers(before, after):
    """Pure (tested). The 1-based numbers of the qa entries that are new or differ between two qa lists (an appended, replaced
    or extended entry; an unchanged one is left out) — what the batch's replay reason cites (JSA-420 review: a count range
    n_before+1..len was wrong for replace-only / extend-only batches)."""
    return [k for k, x in enumerate(after, 1) if k > len(before) or before[k - 1] != x]


def batch_reason_n(nums):
    """Pure (tested). qa numbers → the text after 'qa#' in the replay reason: '5,7,9', long lists cut with a count; '?' when none."""
    nums = list(nums)
    if not nums:
        return '?'
    return ','.join(map(str, nums[:12])) + (f' (+{len(nums) - 12} more)' if len(nums) > 12 else '')


def run_batch(a):
    """JSA-420 (Joey 2026-11-17: 16 answers took 8 minutes — each qa_add replayed all stored forms, ~30 s). Every item is saved and
    checked like a single qa_add (own overlap + answer check), but the replay and the commit run ONCE at the end, and the profile
    lock is held for the whole batch (released before the replay). An item that fails or raises is reported and skipped; the saved
    ones are still replayed and committed. Exit 1 when any failed."""
    try:
        specs = json.load(open(a.batch, encoding='utf-8'))
        if not isinstance(specs, list) or not specs:
            raise ValueError('the batch file must be a non-empty JSON list')
        argvs = [batch_argv(sp, a.profile) for sp in specs]
    except (OSError, ValueError) as ex:
        print('qa_add: --batch:', ex); return 1
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import paths as jp
    live = os.path.abspath(a.profile) == os.path.abspath(jp.config('profile.json'))
    failed, ok = [], []
    with ProfileLock(a.profile) as lk:
        before = open(a.profile, encoding='utf-8').read()
        for sp, argv in zip(specs, argvs):
            try:
                rc = main(argv, lock=lk)
            except (Exception, SystemExit) as ex:                # one bad item never stops the others (argparse exits, timeouts …)
                print(f'qa_add: item raised {type(ex).__name__}: {str(ex)[:200]}')
                rc = 1
            (ok if rc == 0 else failed).append(sp)
        print(f'qa_add: batch — {len(ok)} saved, {len(failed)} not saved')
        for sp in failed:
            print('  not saved:', (sp.get('q') or f"extend #{sp.get('extend_entry')}")[:100])
        srcs = list(dict.fromkeys(str(sp.get('source') or 'user') for sp in ok))
        pseudo = {'added': date.today().isoformat(), 'source': '; '.join(srcs)[:200], 'q': f'{len(ok)} answers'}
        if ok and live and not a.no_commit:
            home = jp.home()
            files = [os.path.relpath(a.profile, home), os.path.relpath(jp.bundle(), home)]
            log = jp.fact('decisions-log.md')
            if os.path.exists(log) and log.startswith(os.path.join(home, 'facts') + os.sep):
                files.append(os.path.relpath(log, home))
            try:
                subprocess.run(['git', '-C', home, 'add', '--'] + files, check=True)
                r = subprocess.run(['git', '-C', home, 'commit', '-q', '-m', f"qa: {len(ok)} answers ({pseudo['source'][:60]})", '--'] + files, capture_output=True, text=True)
                print(f'qa_add: committed in {home}' if r.returncode == 0 else 'qa_add: not committed — ' + (r.stdout + r.stderr).strip()[:300])
            except (OSError, subprocess.CalledProcessError) as ex:
                print(f'qa_add: not committed ({ex})')
    if ok and live and not a.no_replay:                           # the lock is released: the replay only reads
        try:
            now = json.load(open(a.profile, encoding='utf-8')).get('qa') or []
            nums = changed_numbers(json.loads(before).get('qa') or [], now)
            with tempfile.TemporaryDirectory() as td:
                old = os.path.join(td, 'profile.json')
                open(old, 'w', encoding='utf-8').write(before)
                replay_after(pseudo, batch_reason_n(nums), old)  # one replay for the whole batch
        except (OSError, ValueError) as ex:
            print(f'qa_add: replay skipped ({ex})')
    return 1 if failed else 0


def qa_reason(e, n):
    """Pure (tested). The replay reason for answers entry #n changed — cites the entry (qa#N) and its source (JSA-351)."""
    return f"qa#{n} ({e.get('added', '')}): {e.get('source', '')} — {e.get('q', '')[:80]}"


def replay_args(e, n, old_profile):
    """Pure (tested). replay.py arguments that give this entry's reason ONLY to the answers it changed: the keys whose
    answer differs between the rules on the profile without the entry (old_profile) and with it (JSA-351; before, every
    pending change got it — 424 on 2026-11-16)."""
    return ['--reason', qa_reason(e, n), '--changed-from', old_profile]


def replay_after(e, n, old_profile, extra=(), here=HERE):
    """JSA-188: re-answer every stored form with the new entry; the answers it changes on SUBMITTED forms get this answer
    as their reason (it is the user's own fact), and every change is printed so the session can tell him. Never fails
    qa_add."""
    rp = os.path.join(here, '..', '..', '..', 'scripts', 'learn', 'replay.py')
    if not os.path.exists(rp):
        return
    try:
        r = subprocess.run([sys.executable, rp] + replay_args(e, n, old_profile) + list(extra),
                           capture_output=True, text=True, timeout=600)
        out = [l for l in (r.stdout or '').splitlines() if l.strip()]
        print('qa_add: replay — ' + ('; '.join(out[:3]) if out else (r.stderr or 'no output').strip()[:200]))
        for l in out:
            if l.startswith('- '):
                print('  ' + l[:220])
    except Exception as ex:                                       # the answer is saved either way
        print(f'qa_add: replay skipped ({type(ex).__name__})')


if __name__ == '__main__':
    sys.exit(main())
