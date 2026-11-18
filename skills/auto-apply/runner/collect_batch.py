#!/usr/bin/env python3
"""Before a batch is approved: every question the whole batch will ask Joey, on ONE sheet (JSA-189).

Today a runner meets a company question only on its page, stops (Workday waits, then times out) and the next folder does
the same — Joey is called once per folder. This collects them all first:

  1. offline where the form is known without a browser: Greenhouse / Lever / Ashby `plan.json` → `needs_user`;
  2. with `--run`, a DRY run of every other folder, one at a time (the runners share the job Chrome): Workday with
     `--wait-min 0 --login-wait-min 0` (it stops at the first unknown page instead of waiting), the newer runners as they
     are — then their records: Workday `wd_needs.json`, the others `form_check.json` → `unknown`;
  3. every question is re-answered with the current rules (a question they answer now is dropped), human checks
     (CAPTCHA, "verify you are human") are listed apart, the rest is merged by wording across folders.

Writes `<batch>.questions.md` (for Joey) and `<batch>.questions.json` (an `answer` slot per question). After Joey answers,
fill the slots and `--apply` it: each answer goes through `qa_add.py` (saved once in the profile's qa table, checked by the
rules, replayed over earlier forms — JSA-188); then run the batch as usual.

    python3 collect_batch.py <batch.json | folder …> [--name <name>] [--run] [--cdp …]
    python3 collect_batch.py --apply <name>.questions.json --source "Joey 2026-11-06 (batch <name>)"

Answer slot: {"text": "…"} | {"yes": true} | {"no": true} | {"pick": "<option>"}; leave null to skip.
"""
import argparse, json, os, re, subprocess, sys
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402

VENV = os.path.expanduser('~/.job-agent-venv/bin/python')
HUMAN = re.compile(r'captcha|verify you are human|are you a robot|not a robot|count the number of', re.I)
ESSAY = re.compile(r'^(why|how (does|do|would|will|have|did)|tell us|describe|explain|what (interests|excites|draws|motivates)|in (a few|\d+) (sentences|words))\b|\b(cover letter|motivation|in your own words)\b', re.I)
RUNNERS = {'workday': ('run_wd.py', ['--wait-min', '0', '--login-wait-min', '0'], 'positional'),
           'oracle': ('run_oracle.py', [], 'folder'), 'icims': ('run_icims.py', ['--wait-captcha', '0'], 'folder'),
           'workable': ('run_workable.py', ['--wait-captcha', '0'], 'folder'), 'smartrecruiters': ('run_smartrecruiters.py', ['--wait-captcha', '0'], 'folder'),
           'successfactors': ('run_successfactors.py', ['--wait-captcha', '0'], 'folder')}


# ----------------------------------------------------------------------------- pure helpers (tested)
def parse_unknown(s):
    """Pure. A runner's unknown line "[section 2: | step 3: ]<question> (options: A / B)" → (question, options)."""
    s = re.sub(r'^\s*(section|step|page)\s*\d+\s*:\s*', '', str(s or ''), flags=re.I).strip()
    m = re.search(r'\s*\(options:\s*(.*)\)\s*$', s)
    if m:
        return s[:m.start()].strip(), [o.strip() for o in m.group(1).split(' / ') if o.strip()]
    return s, []


def qnorm(q):
    """Pure. The merge key of a question: lower case, no numbering, no punctuation, single spaces."""
    q = re.sub(r'^\s*(\d+(\.\d+)*|[a-z]\)|q\d+)[.):]?\s+', '', str(q or '').lower())
    return ' '.join(re.sub(r'[^\w\s]', ' ', q).split())


def ats_of(folder_files):
    """Pure. Which platform a folder belongs to from the names / contents of its prep files:
    {'job.json': {...}, 'wd_job.json': {...}, 'plan.json': {...}} (only the ones present)."""
    if 'wd_job.json' in folder_files:
        return 'workday'
    p = folder_files.get('plan.json') or {}
    if p.get('ats'):
        return p['ats']
    j = folder_files.get('job.json') or {}
    if j.get('ats'):
        return j['ats']
    u = (j.get('url') or j.get('ats_url') or '').lower()
    for key, name in (('myworkday', 'workday'), ('oraclecloud', 'oracle'), ('icims', 'icims'), ('jibeapply', 'icims'),
                      ('workable', 'workable'), ('smartrecruiters', 'smartrecruiters'), ('greenhouse', 'greenhouse'),
                      ('lever.co', 'lever'), ('ashbyhq', 'ashby')):
        if key in u:
            return name
    return 'successfactors' if re.search(r'/job/[^/]+/\d{7,}/?', u) else 'other'


def merge(items):
    """Pure. items = [{'folder', 'question', 'options', 'type'}] → one entry per question wording (qnorm), folders listed,
    options united (first-seen order); human checks apart. Returns (questions, human_checks)."""
    qs, human = {}, []
    for it in items:
        q = (it.get('question') or '').strip()
        if not q:
            continue
        if HUMAN.search(q):
            human.append(it); continue
        k = qnorm(q)
        e = qs.setdefault(k, {'id': f'Q{len(qs) + 1}', 'question': q, 'type': it.get('type') or '', 'options': [], 'folders': [], 'answer': None,
                              'kind': 'essay' if (not it.get('options') and (ESSAY.search(q) or it.get('type') == 'textarea')) else 'fact'})
        for o in it.get('options') or []:
            if o not in e['options']:
                e['options'].append(o)
        if it.get('folder') not in e['folders']:
            e['folders'].append(it.get('folder'))
    return sorted(qs.values(), key=lambda e: (-len(e['folders']), e['question'].lower())), human


def qa_args(entry, source):
    """Pure. A filled sheet entry → the qa_add.py arguments, or None when it has no answer. A merged entry (JSA-237 prefetch
    sheet) adds its --match regex; a pick may be a list (fallbacks, e.g. a pattern principle's option regexes)."""
    a = entry.get('answer')
    if not a:
        return None
    args = ['--q', entry['question'], '--source', source]
    if a.get('yes'):
        args.append('--yes')
    elif a.get('no'):
        args.append('--no')
    elif a.get('pick'):
        for p in (a['pick'] if isinstance(a['pick'], list) else [a['pick']]):
            args += ['--pick', p]
    elif a.get('text'):
        args += ['--text', a['text']]
    else:
        return None
    if entry.get('match'):
        args += ['--match', entry['match']]
    sets = entry.get('option_sets') or ([entry['options']] if entry.get('options') else [])
    if len(sets) == 1 and not any('|' in str(o) for o in sets[0]):
        args += ['--options', '|'.join(sets[0])]
    else:                                                       # JSA-241: one shape per form's list; JSON, an option may hold "|"
        for lst in sets:
            args += ['--options-json', json.dumps(lst, ensure_ascii=False)]
    return args


def sheet_answer(sheet, entry):
    """Pure. The answer slot to apply: the entry's own `answer`; else, when Joey accepted the derived block
    (`accept_derived`: true, the form-prefetch sheet's one click), its `suggested` slot — only for a 'derived' entry that
    is not high-risk. A slot marked `draft` is never applied (JSA-366)."""
    if entry.get('answer'):
        return None if isinstance(entry['answer'], dict) and entry['answer'].get('draft') else entry['answer']
    if sheet.get('accept_derived') and entry.get('block') == 'derived' and not entry.get('risk') and entry.get('kind') != 'high_risk':
        return entry.get('suggested') or None
    return None


CLAIM_MAX_AGE = 6 * 3600                                       # seconds: an older claim is stale whatever its pid


def claim_sheet(forms_dir, name, pid=None):
    """JSA-366. Take the apply claim of one sheet: (True, None), or (False, holder) when a live process of another session
    holds it. A claim whose process is gone is taken over. The claim file is created exclusively, so two sessions starting
    together cannot both get it."""
    path = _claim_path(forms_dir, name)
    os.makedirs(forms_dir, exist_ok=True)
    for _ in range(3):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = {}
            try:
                holder = json.load(open(path, encoding='utf-8'))
                if (datetime.now() - datetime.fromisoformat(holder['at'])).total_seconds() > CLAIM_MAX_AGE:
                    raise ValueError('too old (a recycled pid must not block the sheet)')
                os.kill(int(holder['pid']), 0)
                return False, holder
            except PermissionError:                               # alive, another user
                return False, holder
            except (OSError, ValueError, KeyError, TypeError):    # unreadable or its process is gone: stale
                try:                                              # takeover by rename: only one session moves the stale file away
                    os.rename(path, path + f'.stale{os.getpid()}')
                    os.remove(path + f'.stale{os.getpid()}')
                except OSError:
                    pass
                continue
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'pid': pid or os.getpid(), 'at': datetime.now().isoformat(timespec='seconds')}, f)
        return True, None
    return False, {}


def _claim_path(forms_dir, name):
    return os.path.join(forms_dir, re.sub(r'[^A-Za-z0-9._-]', '_', name) + '.apply.lock')


def release_sheet(forms_dir, name):
    try:
        os.remove(_claim_path(forms_dir, name))
    except OSError:
        pass


def applied_before(forms_dir, name):
    """The question texts a session already applied on this sheet (asked.jsonl lines with how == 'answered'; a deferred
    sheet is not an applied one — JSA-366). None = a legacy line without questions (the whole sheet)."""
    out = set()
    try:
        for l in open(os.path.join(forms_dir, 'asked.jsonl'), encoding='utf-8'):
            try:
                x = json.loads(l)
                if x['sheet'] != name or x.get('how') != 'answered':
                    continue
                if x.get('questions') is None:
                    return None
                out |= {str(q) for q in x['questions']}
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
    except OSError:
        pass
    return out


def unhandled(todo, done):
    """Pure (tested). The entries of a sheet apply not yet handled: `done` = handled question texts (None = the whole sheet)."""
    return [] if done is None else [e for e in todo if e.get('question') not in done]


# ----------------------------------------------------------------------------- folders
def _load(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return None


def folders_of(args):
    out = []
    for a in args:
        p = a if os.path.isabs(a) else (jpaths.data('runner', 'batches', a) if not os.path.exists(a) else a)
        if p.endswith('.json') and os.path.exists(p):
            d = _load(p) or {}
            rows = d if isinstance(d, list) else d.get('jobs') or d.get('folders') or []
            out += [r['folder'] if isinstance(r, dict) else r for r in rows if (r.get('folder') if isinstance(r, dict) else r)]
        else:
            out.append(os.path.basename(os.path.normpath(a)))
    return list(dict.fromkeys(out))


def files_of(folder):
    d = jpaths.apps(folder)
    return {n: _load(os.path.join(d, n)) for n in ('job.json', 'wd_job.json', 'plan.json') if os.path.exists(os.path.join(d, n))}


def questions_of(folder, ats):
    d, items = jpaths.apps(folder), []
    plan = _load(os.path.join(d, 'plan.json')) or {}
    for n in plan.get('needs_user') or []:
        items.append({'folder': folder, 'question': n.get('label'), 'options': n.get('options') or [], 'type': n.get('type') or ''})
    wd = _load(os.path.join(d, 'wd_needs.json')) or {}
    for n in (wd.get('needs') if isinstance(wd, dict) else wd) or []:
        if isinstance(n, dict):
            items.append({'folder': folder, 'question': n.get('label'), 'options': [o.rstrip('*') for o in n.get('options') or []], 'type': n.get('type') or ''})
    fc = _load(os.path.join(d, 'form_check.json')) or {}
    for u in fc.get('unknown') or []:
        q, opts = parse_unknown(u)
        items.append({'folder': folder, 'question': q, 'options': opts, 'type': 'select' if opts else 'text'})
    given = _load(os.path.join(d, 'answers.json')) or {}            # Joey already answered it for this folder
    done = {qnorm(k) for k in given if not str(k).startswith('files:')}
    return [it for it in items if qnorm(it.get('question')) not in done]


def still_unknown(items):
    """Drop the questions the current rules answer now (one node call)."""
    if not items:
        return []
    qs = [{'key': str(i), 'label': it['question'], 'type': it.get('type') or 'text', 'options': it.get('options') or []} for i, it in enumerate(items)]
    try:
        r = subprocess.run(['node', os.path.join(HERE, 'rules_bridge.js')], input=json.dumps(qs), capture_output=True, text=True, timeout=120)
        got = json.loads(r.stdout or '{}')
    except Exception:
        return items
    return [it for i, it in enumerate(items) if (got.get(str(i)) or {}).get('status') != 'ok']


def dry_run(folder, ats, cdp, log):
    spec = RUNNERS.get(ats)
    if not spec:
        return
    script, extra, how = spec
    cmd = [VENV if os.path.exists(VENV) else sys.executable, os.path.join(HERE, script)]
    cmd += ([jpaths.apps(folder)] if how == 'positional' else ['--folder', jpaths.apps(folder)]) + extra + ['--cdp', cdp]
    log(f'dry run {ats}: {folder}')
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        last = [l for l in (r.stdout or '').splitlines() if l.startswith('STATUS')]
        log('  ' + (last[-1] if last else f'exit {r.returncode}'))
    except subprocess.TimeoutExpired:
        log('  timeout (15 min) — its questions so far are still read')


def sheet_md(name, qs, human, skipped):
    L = [f'# Questions for batch {name} — answer once, every folder uses it', '',
         f'{len(qs)} question(s) the rules cannot answer · {len(human)} human check(s) · generated {date.today().isoformat()}', '']
    facts, essays = [e for e in qs if e.get('kind') != 'essay'], [e for e in qs if e.get('kind') == 'essay']
    if essays:
        L[2] = (f'{len(facts)} fact question(s) for Joey · {len(essays)} open-ended question(s) drafted from his approved stories · '
                f'{len(human)} human check(s) · generated {date.today().isoformat()}')
    for e in facts:
        L.append(f"**{e['id']}** ({len(e['folders'])} folder{'s' if len(e['folders']) != 1 else ''}) — {e['question']}")
        if e['options']:
            L.append('  options: ' + ' / '.join(e['options'][:20]))
        L.append('  folders: ' + ', '.join(e['folders'][:8]) + (' …' if len(e['folders']) > 8 else '')); L.append('')
    if essays:
        L += ['## Open-ended — not a fact question: ds_materials.py drafts them from Confirmed stories (add to the folder\'s questions.json), Joey only reviews', '']
        L += [f"- {e['id']} — {e['question'][:140]} · " + ', '.join(e['folders'][:4]) for e in essays] + ['']
    if human:
        L += ['## Human checks (Joey, in the job Chrome tab when the batch runs)', ''] + [f"- {h['folder']}: {h['question'][:120]}" for h in human] + ['']
    if skipped:
        L += ['## Not read (no prep files / platform without a runner)', ''] + [f'- {s}' for s in skipped] + ['']
    return '\n'.join(L)


def qa_spec(entry, source):
    """Pure. A filled sheet entry → one `qa_add.py --batch` item (same fields as qa_args), or None when it has no answer."""
    args = qa_args(entry, source)
    if not args:
        return None
    sp = {'q': entry['question'], 'source': source}
    a = entry['answer']
    if a.get('yes'):
        sp['yes'] = True
    elif a.get('no'):
        sp['yes'] = False
    elif a.get('pick'):
        sp['pick'] = list(a['pick']) if isinstance(a['pick'], list) else [a['pick']]
    elif a.get('text'):
        sp['text'] = a['text']
    if entry.get('match'):
        sp['match'] = entry['match']
    sets = entry.get('option_sets') or ([entry['options']] if entry.get('options') else [])
    if len(sets) == 1 and not any('|' in str(o) for o in sets[0]):
        sp['options'] = '|'.join(sets[0])
    elif sets:
        sp['options_json'] = [json.dumps(l, ensure_ascii=False) for l in sets]
    return sp


def apply_sheet(sheet, todo, a, fdir, log):
    """All answers of the sheet through ONE `qa_add.py --batch` (JSA-420): each is saved and checked like a single qa_add, the
    ~30 s replay of the stored forms and the data-home commit run once (16 answers: 465 s → ~45 s)."""
    import tempfile
    source = a.source or f"Joey {date.today().isoformat()} (batch {sheet.get('name', '')})"
    specs = [sp for sp in (qa_spec(e, source) for e in todo) if sp]
    n = len(specs)
    if specs:
        with tempfile.TemporaryDirectory() as td:
            bf = os.path.join(td, 'answers.json')
            json.dump(specs, open(bf, 'w', encoding='utf-8'), ensure_ascii=False)
            r = subprocess.run([sys.executable, os.path.join(HERE, '..', 'scripts', 'qa_add.py'), '--batch', bf], capture_output=True, text=True)
        for l in (r.stdout or r.stderr or '(no output)').strip().splitlines():
            log('qa_add: ' + l[:220] if not l.startswith(('qa_add:', ' ')) else l[:220])
        if r.returncode:
            log(f'collect_batch: qa_add --batch exit {r.returncode}: some answers were NOT saved (see "not saved" above)')
    log(f'collect_batch: {n} answer(s) sent through qa_add.py --batch')
    if str(sheet.get('name', '')).startswith('prefetch-'):   # JSA-243: today's morning sheet is handled (no more reminders)
        sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
        import prefetch_due
        prefetch_due.mark(sheet['name'], 'answered', n, fdir, questions=[e.get('question') for e in sheet.get('questions') or []])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('batch', nargs='*'); ap.add_argument('--name'); ap.add_argument('--run', action='store_true')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222')
    ap.add_argument('--apply'); ap.add_argument('--source', default='')
    ap.add_argument('--reapply', action='store_true', help='apply a prefetch sheet again although it was already applied (JSA-366)')
    a = ap.parse_args()
    log = print
    if a.apply:
        sheet = _load(a.apply) or {}
        fdir = os.path.dirname(os.path.abspath(a.apply))
        todo = [dict(e, answer=sheet_answer(sheet, e)) for e in sheet.get('questions') or []]
        if not str(sheet.get('name', '')).startswith('prefetch-'):
            return apply_sheet(sheet, todo, a, fdir, log)
        sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))   # JSA-366: one session per morning sheet
        import prefetch_due
        got, holder = claim_sheet(fdir, sheet['name'])
        if not got:
            log(f"collect_batch: NOT applied — another session is applying {sheet['name']} right now "
                f"(pid {holder.get('pid')}, since {holder.get('at')}); nothing was written. Wait for it, do not run this twice.")
            return 1
        try:
            done = applied_before(fdir, sheet['name'])
            if done != set() and not a.reapply:
                fresh = unhandled(todo, done)
                if any(e['answer'] for e in todo) and not any(e['answer'] for e in fresh):
                    log(f"collect_batch: NOT applied — {sheet['name']} was already applied by a session (asked.jsonl); nothing "
                        f"was written. A second apply would save the same answers twice (--reapply to do it on purpose).")
                    return 1
                for e in todo:
                    if e['answer'] and e not in fresh:
                        log(f"{e['id']}: skipped — already applied from this sheet (--reapply to save it again)")
                todo = fresh
            return apply_sheet(sheet, todo, a, fdir, log)
        finally:
            release_sheet(fdir, sheet['name'])
    folders = folders_of(a.batch)
    if not folders:
        ap.error('give a batch file or folder names')
    name = a.name or (os.path.splitext(os.path.basename(a.batch[0]))[0] if a.batch[0].endswith('.json') else date.today().isoformat())
    items, skipped = [], []
    for f in folders:
        fl = files_of(f)
        ats = ats_of(fl)
        if not fl:
            skipped.append(f'{f} (no prep files)'); continue
        if a.run and ats in RUNNERS:
            dry_run(f, ats, a.cdp, log)
        elif ats not in RUNNERS and ats not in ('greenhouse', 'lever', 'ashby'):
            skipped.append(f'{f} ({ats})')
        items += questions_of(f, ats)
    items = still_unknown(items)
    qs, human = merge(items)
    out = jpaths.data('runner', 'batches', name + '.questions')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({'name': name, 'folders': folders, 'questions': qs, 'human_checks': human}, open(out + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(out + '.md', 'w', encoding='utf-8').write(sheet_md(name, qs, human, skipped))
    nf = sum(1 for e in qs if e.get('kind') != 'essay')
    log(f'collect_batch: {len(folders)} folder(s) · {nf} fact question(s) for Joey · {len(qs) - nf} open-ended (drafted) · {len(human)} human check(s) → {out}.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
