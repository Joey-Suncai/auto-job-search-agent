#!/usr/bin/env python3
"""One-command batch apply (JSA-229, spec docs/specs/batch-apply-pipeline.md; Joey 2026-11-06 「一条命令连着交」).

The scripts take ~40 s per job; the time went to the agent running each step and reporting. This chains them so a batch
costs the agent two turns (prepare → Joey answers + approves → submit), with every runner gate unchanged.

  ~/.job-agent-venv/bin/python batch_apply.py prepare data/runner/batches/<name>.json [--fresh] [--max N]
  ~/.job-agent-venv/bin/python batch_apply.py approve data/runner/batches/<name>.json --by "<Joey's words>" [--only F …]
  ~/.job-agent-venv/bin/python batch_apply.py submit  data/runner/batches/<name>.json [--only F …]

Platforms (JSA-230): Ashby / Lever (run_form.py) and Greenhouse (run.py) prepped by prep_batch.py; Workday (run_wd.py, prep_wd.py,
≤ 5 per batch, one at a time, its tab closed after each); Oracle, SmartRecruiters, SuccessFactors, iCIMS / Jibe, Workable
(their runners with --folder, prepped here: folder + job.json + jd.md from eligibility_fetch). A batch may mix platforms.

prepare: prep_batch.py on the whole batch → ds_materials.py in parallel (≤ 4) → dry-run one at a time → <batch>.apply.md /
.apply.json + one list of every question that needs Joey. approve: only after Joey's yes in chat (rule 7). submit (→ <batch>.submit.md / .json): the
platform runner with --submit per approved folder, in order; a stopped job never stops the rest. Batch cap 10 (Joey: 8 recommended);
5 when any job needs a sign-in (Workday, Oracle, SuccessFactors, iCIMS).
"""
import argparse, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home, ADR-0008)
sys.path.insert(0, HERE)
import app_folder as AF  # noqa: E402  (JSA-319: one folder per job — found by job id first)
import posting as PO  # noqa: E402  (JSA-331/332: which URL a job uses, which platform it is on)

MAX_JOBS = 10
MAX_LOGIN = 5                       # Workday / Oracle / SuccessFactors / iCIMS: 2–3 min each + sign-in (Joey 2026-11-06)
LOGIN = {'workday', 'oracle', 'successfactors', 'icims'}
GAL = {'greenhouse', 'ashby', 'lever'}   # prepped by prep_batch.py
OFFLINE = GAL | {'workable'}             # public form data → questions without a browser (JSA-235; Joey 11-06: every such platform)
OWN = {'oracle', 'smartrecruiters', 'successfactors', 'icims', 'workable'}   # prepped here
PARALLEL_MATERIALS = 4
DS = os.path.join(ROOT, 'skills', 'auto-apply', 'scripts', 'ds_materials.py')
RULES = os.path.join(ROOT, 'skills', 'auto-apply', 'scripts', 'answer_rules.js')

TRACKS = {'data analyst': 'Data_Analyst', 'data sci / analytics': 'Data_Analyst', 'data engineer': 'Data_Engineer',
          'product manager': 'Product_Manager', 'ai product manager': 'Product_Manager',
          'ai agentic eng': 'AI_Agentic_Engineer', 'ai agentic engineer': 'AI_Agentic_Engineer'}
NORMAL = {'Data_Analyst', 'Data_Engineer', 'Product_Manager', 'AI_Agentic_Engineer'}
OK_REASONS = {'dry-run', 'batch not approved'}
OK_PREFIX = ('batch not approved',)                 # runner_common: 'batch not approved (data/runner/approved_batches.json)'
DS_SPOT = re.compile(r'^\d+ DeepSeek answers?(\(s\))? to spot-check\b')   # Workday: approvable; `submit --ds-ok` still needs Claude's spot-check (JSA-271)


# ----------------------------------------------------------------------------- pure (tested: test/t_batch_apply.py)
def track(name):
    """Store track name → material track (ds_materials --track)."""
    n = (name or '').strip()
    if n in NORMAL:
        return n
    return TRACKS.get(n.lower(), 'Data_Analyst')


RUNNERS = {'ashby': 'run_form.py', 'lever': 'run_form.py', 'greenhouse': 'run.py', 'workday': 'run_wd.py',
           'oracle': 'run_oracle.py', 'smartrecruiters': 'run_smartrecruiters.py', 'successfactors': 'run_successfactors.py',
           'icims': 'run_icims.py', 'jibe': 'run_icims.py', 'workable': 'run_workable.py'}


def runner(ats):
    """Platform → runner script, or None when the platform is not in this pipeline."""
    return RUNNERS.get((ats or '').strip().lower())


def platform(url):
    """Pure. Platform of a posting URL — the shared rule in posting.py (JSA-332)."""
    return PO.platform(url)


def command(ats, folder, submit, ds_ok=False):
    """Pure. argv after the python executable for one run; None when the platform has no runner here. Batch runs never
    wait in place for Joey (CAPTCHA / answers / sign-in go to his queue; the next job starts)."""
    r = runner(ats)
    if not r:
        return None
    a = (ats or '').strip().lower()
    sub = ['--submit'] if submit else []
    if a in ('ashby', 'lever', 'greenhouse'):
        return [r, folder] + sub
    if a == 'workday':
        return [r, folder, '--wait-min', '0', '--login-wait-min', '0'] + (['--ds-ok'] if ds_ok and submit else []) + sub
    return [r, '--folder', folder, '--wait-captcha', '0'] + sub


def parse(output):
    """Runner stdout → {status, secs, reasons}."""
    lines = [l.strip() for l in (output or '').splitlines()]
    status = secs = None
    reasons = []
    for l in lines:
        m = re.match(r'^STATUS\s+(\S+)', l)
        if m:
            status = m.group(1)
        m = re.search(r'(?:^|\s)TIME\s+([\d.]+)s', l)
        if m:
            secs = float(m.group(1))
        m = re.match(r'^NOT submitted:\s*(.*)$', l)
        if m:
            reasons = [r.strip() for r in m.group(1).split(' | ') if r.strip()]
    if status is None:
        last = [l for l in lines if l]
        return {'status': 'crashed', 'secs': secs, 'reasons': [last[-1]] if last else []}
    return {'status': status, 'secs': secs, 'reasons': reasons}


def last_note(output):
    """Pure. The last non-empty stdout line that is not a STATUS / TIME line, without its '- <time> ' log prefix."""
    for l in reversed([x.strip() for x in (output or '').splitlines()]):
        if l and not re.match(r'^(?:- \S+ )?(STATUS|TIME)\b', l):
            return re.sub(r'^- \d{4}-\d\d-\d\dT[\d:]+ ', '', l)[:200]
    return ''


def ready(status, reasons, output=''):
    """A dry-run that would submit once approved."""
    if status != 'dry-run':
        return False
    if 'all checks pass' in (output or ''):
        return True
    return all(r in OK_REASONS or r.startswith(OK_PREFIX) or DS_SPOT.match(r) for r in reasons)   # submit still re-applies every runner gate
    # a Workday dry run whose only open item is "N DeepSeek answer(s) to spot-check" is approvable: approve and the
    # spot-check were each waiting for the other (11-10, recert_wdB); run_wd refuses the submit until --ds-ok (JSA-271)


PREFETCH_MAX_AGE = 5          # days: a form prefetch record this fresh is trusted (JSA-239)


def prefetch_gate(rec, today):
    """Pure (tested, JSA-239). One job's form-prefetch record (data/forms/<id>.json, or None) → ('skip', status) for a FRESH
    closed / restricted record, ('prepare', needs-or-None) otherwise (fresh ok record → how many questions are still open;
    stale / error / missing / unreadable date → no change)."""
    if not isinstance(rec, dict):
        return 'prepare', None
    try:
        age = (datetime.strptime(str(today)[:10], '%Y-%m-%d') - datetime.strptime(str((rec or {}).get('read_at') or '')[:10], '%Y-%m-%d')).days
    except ValueError:
        return 'prepare', None
    if rec is None or age < 0 or age > PREFETCH_MAX_AGE:
        return 'prepare', None
    st = rec.get('status')
    if st in ('closed', 'restricted'):
        return 'skip', f"skipped: {st} (prefetch {str(rec['read_at'])[:10]})"
    if st == 'ok' and isinstance(rec.get('needs'), int):
        return 'prepare', rec['needs']
    return 'prepare', None


def screen_closed(jobs, today, a=None):
    """JSA-417. The batch's jobs minus those the public Greenhouse / Lever / Ashby API no longer lists (marked 已关闭 in the store).
    An unreachable API (403, timeout) keeps the job; --keep-closed skips the check."""
    if getattr(a, 'keep_closed', False):
        return jobs
    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
        import job_closed
        keep, dropped = job_closed.screen(jobs, today=today, source='prepare')
    except Exception as e:                      # the check never stops a batch
        print(f'  (closed check skipped: {type(e).__name__}: {str(e)[:80]})'); return jobs
    if dropped:
        print(f'closed check: {len(dropped)} of {len(jobs)} job(s) closed — dropped, store marked 已关闭')
    return keep


def prefetch_record(job_id):
    p = jpaths.data('forms', f'{job_id}.json')
    try:
        return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
    except (OSError, ValueError):
        return None


def size(n, mx=None, login=False):
    """None when a batch of n jobs is allowed, else 'too many'. login = some job needs a sign-in (cap 5)."""
    cap = MAX_LOGIN if login else MAX_JOBS
    cap = min(cap, mx) if mx else cap
    return 'too many' if n > cap else None


def offline_items(needs_user, gate_items, given=()):
    """Pure (JSA-235). The questions for Joey from a Greenhouse / Ashby / Lever folder without opening the form:
    plan.json `needs_user` (rule unknowns and open questions without a drafted answer) minus the ones answers.json already
    answers (matched by label or field key), plus every required materials-gate problem (a file slot with no file, e.g. a
    research supplement). → [{'question', 'options', 'kind': 'question' | 'file'}] in that order."""
    done = {str(g).strip().lower() for g in given or ()}
    out = []
    for n in needs_user or []:
        label, key = str(n.get('label') or '').strip(), str(n.get('key') or '').strip()
        if not label or label.lower() in done or (key and key.lower() in done):
            continue
        out.append({'question': label, 'options': list(n.get('options') or []), 'kind': 'question'})
    for g in gate_items or []:
        if g.get('required', True) and (g.get('msg') or g.get('evidence')):
            out.append({'question': str(g.get('evidence') or g.get('msg')).strip(), 'options': [], 'kind': 'file'})
    return out


def offline(ats, dry_run=False):
    """Pure. True when prepare collects this platform's questions offline (no browser): every platform with public form
    data — Greenhouse / Ashby / Lever / Workable — unless --dry-run."""
    return (ats or '').strip().lower() in OFFLINE and not dry_run


def outcome(status):
    """Pure. What a run's status means for the batch: 'done' (submitted / already submitted), 'needs-joey' (stopped on a
    gate he resolves — an answer, a file, a CAPTCHA, a sign-in, an unconfirmed submit; nothing was submitted unless
    confirmed), 'rerun' (crashed, failed, timed out, job Chrome busy) — rerun only that folder with --only."""
    s = (status or '').strip().lower()
    if s in ('submitted', 'already-submitted'):
        return 'done'
    if s in ('crashed', 'failed', 'chrome-busy', 'timeout', ''):
        return 'rerun'
    return 'needs-joey'


def folder_name(date, company, title):
    """Pure. Same folder name as prep_batch.py / prep_wd.py."""
    sl = lambda s, n=40: re.sub(r'_+', '_', re.sub(r'[^A-Za-z0-9]+', '_', s or '')).strip('_')[:n]
    return f"{date}_{sl(company, 20)}_{sl(title)}"


def split(jobs):
    """Pure. Jobs by prep route: 'gal' (prep_batch.py), 'wd' (prep_wd.py), 'own' (prep_own here), 'none' (no runner)."""
    out = {'gal': [], 'wd': [], 'own': [], 'none': []}
    for j in jobs:
        p = platform(PO.posting_url(j))
        out['gal' if p in GAL else 'wd' if p == 'workday' else 'own' if p in OWN else 'none'].append(j)
    return out


# ----------------------------------------------------------------------------- I/O
def py():
    v = os.path.expanduser('~/.job-agent-venv/bin/python')
    return v if os.path.exists(v) else sys.executable


def sh(cmd, timeout=900):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=jpaths.home(), capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, 'CX_RULES': RULES})
    return p.returncode, (p.stdout or '') + (p.stderr or ''), round(time.time() - t0, 1)


def side(batch, ext):
    return re.sub(r'\.json$', '', batch) + ext


def ats_of(row, plan=None):
    """Pure. The platform of a prep status row: its own `ats`, else plan.json's, else read from the form URL (prep writes
    no `ats` for Greenhouse rows)."""
    a = (row.get('ats') or (plan or {}).get('ats') or '').lower()
    if a:
        return a
    u = ' '.join(str(row.get(k) or '') for k in ('embed', 'url')) + ' ' + str((plan or {}).get('url') or '')
    for key, name in (('greenhouse', 'greenhouse'), ('ashbyhq', 'ashby'), ('lever.co', 'lever')):
        if key in u.lower():
            return name
    return ''


def load_status(batch):
    p = side(batch, '.status.json')
    return json.load(open(p)) if os.path.exists(p) else []


def prep_own(j, date):
    """Oracle / SmartRecruiters / SuccessFactors / iCIMS / Workable: folder + job.json + jd.md (their runners read the form
    live; JD text from eligibility_fetch — a closed posting stops here)."""
    url = PO.posting_url(j); ats = platform(url)
    row = {'id': j['id'], 'company': j['company'], 'title': j['title'], 'ats': ats, 'track': j.get('track')}
    sys.path.insert(0, os.path.join(ROOT, 'skills', 'job-hunt-pipeline', 'scripts'))
    try:
        import eligibility_fetch as EF
        d = EF.load(url) or {}
    except Exception as e:                                   # network / parser: the runner can still read the page
        d = {'status': 'unreadable', 'why': f'{type(e).__name__}: {str(e)[:100]}'}
    if d.get('status') == 'closed':
        row.update(status='closed_or_unreadable', why=d.get('why')); return row     # cmd_prepare marks the store (JSA-417)
    try:
        from prefilter import RX as FLAGS
    except Exception:
        FLAGS = {}
    text = d.get('text') or ''
    flags = [k for k, rx in FLAGS.items() if text and rx.search(text)]
    folder = AF.for_job(j['id'], date, j['company'], j['title'], jpaths.apps(), AF.submitted_fn())   # JSA-319: one folder per job
    name = os.path.basename(folder)
    json.dump({'id': j['id'], 'company': j['company'], 'title': d.get('title') or j['title'], 'url': url, 'ats': ats,
               'track': j.get('track')}, open(os.path.join(folder, 'job.json'), 'w'), ensure_ascii=False, indent=1)
    if text or not os.path.exists(os.path.join(folder, 'jd.md')):
        open(os.path.join(folder, 'jd.md'), 'w', encoding='utf-8').write(
            f"# {d.get('title') or j['title']} — {j['company']}\nURL: {url}\nLocation: {d.get('loc') or ''}\n\n{text.strip()}\n")
    row.update(status='flagged' if flags else 'ok', flags=flags, folder=name)
    if ats == 'workable':                                      # essay boxes → questions.json before ds_materials drafts them
        try:
            import run_workable as RW
            RW.offline_plan(url, folder)
        except Exception as e:
            row['why'] = f'Workable form schema: {type(e).__name__}: {str(e)[:100]}'

    if not text:
        row['why'] = 'JD not readable by script (' + (d.get('why') or d.get('status') or '?') + ') — materials from the title only'
    return row


def prep_all(batch, b):
    """Prep every job by its route; one status row per job, in batch order."""
    parts = split(b['jobs']); rows = {}
    for key, script in (('gal', 'prep_batch.py'), ('wd', 'prep_wd.py')):
        if not parts[key]:
            continue
        sub = side(batch, f'__{key}.json')
        json.dump({**b, 'jobs': parts[key]}, open(sub, 'w'), indent=1, ensure_ascii=False)
        code, out, secs = sh([py(), os.path.join(HERE, script), sub], timeout=900)
        print(f'prep {key}: {secs}s (exit {code})' + ('' if code == 0 else ' — ' + out.strip().splitlines()[-1][:160] if out.strip() else ''))
        for r in load_status(sub):
            rows[r['id']] = r
    for j in parts['own']:
        rows[j['id']] = prep_own(j, b.get('date') or datetime.now().strftime('%Y-%m-%d'))
    for j in parts['none']:
        rows[j['id']] = {'id': j['id'], 'company': j['company'], 'title': j['title'], 'status': 'no runner in batch_apply',
                         'ats': platform(PO.posting_url(j))}
    return [rows[j['id']] for j in b['jobs'] if j['id'] in rows]


def materials(folder, trk, fresh):
    st = os.path.join(jpaths.apps(folder), 'ds_status.json')
    if not fresh and os.path.exists(st) and json.load(open(st)).get('status') == 'ok':
        return 'ok (kept)', 0
    base = [py(), DS, jpaths.apps(folder), '--track', trk]
    code, out, secs = sh(base + (['--fresh'] if fresh else []), timeout=300)
    if code == 3:
        code, out, s2 = sh(base, timeout=300); secs += s2
    if code == 1:
        code, out, s2 = sh(base + ['--fresh'], timeout=300); secs += s2
    ok = os.path.exists(st) and json.load(open(st)).get('status') == 'ok'
    return ('ok' if ok else 'materials failed: ' + (out.strip().splitlines() or ['?'])[-1][:160]), secs


def last_result(folder, since):
    """The newest data/runner/results.jsonl line for this folder written at or after `since` (ISO time), else None."""
    p = jpaths.data('runner', 'results.jsonl')
    if not os.path.exists(p):
        return None
    hit = None
    for line in open(p, encoding='utf-8'):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('folder') == folder and str(d.get('at') or '') >= since:
            hit = d
    return hit


def merge(d, res):
    """Pure. Runner stdout parse + its results.jsonl line → one outcome: the results line fills status (when stdout had
    no STATUS line), seconds, and reasons (its `problems`, when stdout gave none)."""
    out = dict(d)
    if res:
        if out.get('status') in (None, 'crashed') and res.get('status'):
            out['status'] = res['status']; out['reasons'] = []
        if not out.get('secs') and res.get('secs'):
            out['secs'] = res['secs']
        if not out.get('reasons') and res.get('problems'):
            out['reasons'] = [str(x) for x in res['problems']]
    return out


def run_one(folder, ats, submit, ds_ok=False):
    since = datetime.now().strftime('%Y-%m-%dT%H:%M')
    c = command(ats, jpaths.apps(folder), submit, ds_ok)
    cmd = [py(), os.path.join(HERE, c[0])] + c[1:]
    try:
        _, out, secs = sh(cmd, timeout=1200)
    except subprocess.TimeoutExpired:
        return {'status': 'crashed', 'secs': 1200, 'reasons': ['runner timed out'], 'ready': False}
    d = merge(parse(out), last_result(folder, since))
    if d.get('status') == 'closed':                           # JSA-417: the runner read the page; the public API must agree before the store is marked
        try:
            job = json.load(open(os.path.join(jpaths.apps(folder), 'job.json')))
            sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
            import job_closed
            d['store_closed'] = job_closed.confirm_mark(job, '; '.join(d.get('reasons') or []) or 'runner: posting closed', 'runner')
        except Exception:
            pass
    d['secs'] = d['secs'] or secs
    if not d['reasons'] and d['status'] not in ('dry-run', 'submitted', 'already-submitted'):
        d['reasons'] = [last_note(out)] if last_note(out) else []      # e.g. Workday sign-in handed to Joey
    d['ready'] = ready(d['status'], d['reasons'], out)
    return d


def offline_check(folder, ats):
    """Rebuild plan.json without a browser (Greenhouse: the saved gh_api.json; Ashby / Lever: run_form.replan, an HTTP
    read) so the drafted open answers and today's rules count, then run the materials gate offline."""
    import plan_build as PB
    d = jpaths.apps(folder)
    if ats == 'workable':                                     # the public form schema (run_workable.offline_plan)
        import run_workable as RW
        url = json.load(open(os.path.join(d, 'job.json'), encoding='utf-8')).get('url')
        form, fields, _, ans, missing, probs = RW.offline_plan(url, d)
        sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
        import materials_gate as MG
        MG.prepare(d, None, ats)
        items = RW.offline_unknowns(fields, ans, missing) + offline_items([], MG._items(d))
        items += [{'question': q['label'], 'options': [], 'kind': 'question'} for q in missing]   # ds_materials did not draft it
        if form is None:
            items.append({'question': probs[0] if probs else 'form schema not readable', 'options': [], 'kind': 'question'})
        return items
    plan = json.load(open(os.path.join(d, 'plan.json'), encoding='utf-8'))
    try:
        if ats == 'greenhouse' and os.path.exists(os.path.join(d, 'gh_api.json')):
            fields = PB.gh_fields(json.load(open(os.path.join(d, 'gh_api.json'), encoding='utf-8')))
            plan = PB.build(d, fields, plan.get('url'), 'greenhouse')
            json.dump(plan, open(os.path.join(d, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        elif ats in ('ashby', 'lever'):
            import run_form as RF
            plan = RF.replan(d, plan, lambda m: None)
    except BaseException as e:                                # keep prep's plan; its needs_user still counts
        print(f'  {folder}: offline replan failed ({str(e)[:100]}) — prep plan used')
    sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
    import materials_gate as MG
    MG.prepare(d, None, ats)
    gate = MG._items(d)
    try:
        given = list(json.load(open(os.path.join(d, 'answers.json'), encoding='utf-8')))
    except (OSError, ValueError):
        given = []
    return offline_items(plan.get('needs_user'), gate, given)


def needs_joey(folder):
    """Questions the rules could not answer: plan.json needs_user (Greenhouse / Ashby / Lever), wd_needs.json (Workday)."""
    out = []
    p = os.path.join(jpaths.apps(folder), 'plan.json')
    if os.path.exists(p):
        out += [{'question': q.get('label', ''), 'options': q.get('options') or []}
                for q in json.load(open(p)).get('needs_user') or []]
    w = os.path.join(jpaths.apps(folder), 'wd_needs.json')
    if os.path.exists(w):
        wn = json.load(open(w))
        for q in (wn.get('needs') if isinstance(wn, dict) else wn) or []:
            if isinstance(q, dict):
                out.append({'question': q.get('label') or q.get('question') or '', 'options': q.get('options') or []})
    return out


def approved(folder):
    p = jpaths.data('runner', 'approved_batches.json')
    if not os.path.exists(p):
        return False
    return any(folder in b.get('folders', []) for b in json.load(open(p)).get('batches', []))


def write_report(batch, rows, title, ext='.apply'):
    json.dump(rows, open(side(batch, ext + '.json'), 'w'), indent=1, ensure_ascii=False)
    L = [f'# {title} — {os.path.basename(batch)} · {datetime.now():%Y-%m-%d %H:%M}', '',
         '| folder | platform | materials | run | secs | why not (yet) |', '|---|---|---|---|---|---|']
    for r in rows:
        why = '; '.join(x for x in r.get('reasons', []) if x not in OK_REASONS) or ('ready' if r.get('ready') else '')
        if r.get('prefetch_left'):
            why = (why + '; ' if why else '') + f"{r['prefetch_left']} still open at the prefetch"
        L.append(f"| {r['folder'] or r.get('company', '?')} | {r.get('ats', '')} | {r.get('materials', '')} | "
                 f"{r.get('status', '')} | {r.get('secs') or ''} | {why} |")
    qs = [(r['folder'], q) for r in rows for q in r.get('questions', [])]
    tasks = [(r['folder'], t) for r in rows for t in r.get('joey_tasks', [])] + \
            [(r['folder'], 'file: ' + f[:200]) for r in rows for f in r.get('files', [])]
    if qs or tasks:
        L += ['', '## Needs Joey (answer once: qa_add.py / a file in the folder + answers.json, then prepare again —'
              ' or after a submit: `submit --only <folder>`)']
        L += [f"- **{f}** — {q['question'][:200]}" + (f"  [{' / '.join(q['options'])}]" if q['options'] else '')
              for f, q in qs]
        L += [f'- **{f}** — task: {t}' for f, t in tasks]
    txt = '\n'.join(L) + '\n'
    open(side(batch, ext + '.md'), 'w').write(txt)
    print(txt)


def flag_cleared(job):
    """Pure (JSA-418). True when Joey has cleared the JD pre-screen flag on this batch job: `flag_cleared` is a dict whose
    by / at / note are all non-blank strings (note = his own words)."""
    fc = (job or {}).get('flag_cleared')
    return isinstance(fc, dict) and all(isinstance(fc.get(k), str) and fc[k].strip() for k in ('by', 'at', 'note'))


def effective_prep(status, job):
    """Pure (JSA-418). The prep status prepare works with: 'flagged' counts as 'ok' once Joey cleared the flag; all else as is."""
    return 'ok' if status == 'flagged' and flag_cleared(job) else status


def clear_flag(batch, ident, by, note, at):
    """Pure (JSA-418). (new batch, job id) with flag_cleared {by, at, note} on the one job `ident` names (its id, else its
    company, case-insensitive). ValueError: blank by / note, no match, or a company name that fits several jobs."""
    if not (by or '').strip() or not (note or '').strip():
        raise ValueError('clear-flag needs --by and --note (Joey\'s words from the chat)')
    jobs = batch.get('jobs') or []
    ident = str(ident).strip()
    hit = [i for i, j in enumerate(jobs) if str(j.get('id')) == ident]
    if not hit:
        hit = [i for i, j in enumerate(jobs) if str(j.get('company') or '').strip().lower() == ident.lower()]
    if not hit:
        raise ValueError(f'no job in the batch matches {ident!r}')
    if len(hit) > 1:
        raise ValueError(f'{ident!r} matches {len(hit)} jobs — use the job id')
    new = [dict(j) for j in jobs]
    new[hit[0]]['flag_cleared'] = {'by': by.strip(), 'at': at, 'note': note.strip()}
    return {**batch, 'jobs': new}, jobs[hit[0]].get('id')


def cmd_clear_flag(a):
    b = json.load(open(a.batch))
    try:
        b, jid = clear_flag(b, a.job, a.by, a.note, datetime.now().astimezone().isoformat(timespec='minutes'))
    except ValueError as e:
        sys.exit(f'batch_apply clear-flag: {e}')
    json.dump(b, open(a.batch, 'w'), indent=1, ensure_ascii=False)
    print(f'flag cleared: job {jid} — prepare will now build its materials and dry-run it')


def cmd_prepare(a):
    b = json.load(open(a.batch))
    all_jobs = b.get('jobs', [])
    today = datetime.now().strftime('%Y-%m-%d')
    all_jobs = screen_closed(all_jobs, today, a)    # JSA-417: one public-API check; closed jobs are dropped and marked 已关闭
    gate = {j['id']: ('prepare', None) if getattr(a, 'no_prefetch', False) else prefetch_gate(prefetch_record(j['id']), today) for j in all_jobs}   # JSA-239; --no-prefetch = prepare every job anyway
    skipped = [j for j in all_jobs if gate[j['id']][0] == 'skip']
    jobs = [j for j in all_jobs if gate[j['id']][0] != 'skip']
    login = any(platform(PO.posting_url(j)) in LOGIN for j in jobs)
    if size(len(jobs), a.max, login):
        cap = min(MAX_LOGIN if login else MAX_JOBS, a.max or 99)
        sys.exit(f"batch_apply: {len(jobs)} jobs — at most {cap} per batch" + (' (a job needs a sign-in)' if login else ''))
    for j in jobs:
        j['track'] = track(j.get('track'))
    json.dump(b, open(a.batch, 'w'), indent=1, ensure_ascii=False)
    b = dict(b, jobs=jobs)                          # the skipped jobs are not prepared (their rows come below)
    t0 = time.time()
    rows = []
    by_id = {j['id']: j for j in jobs}
    for s in prep_all(a.batch, b):
        s = dict(s); job = by_id.get(s.get('id'))
        if s.get('status') == 'flagged' and effective_prep('flagged', job) == 'ok':   # JSA-418: Joey read the flag and said go
            s['status'] = 'ok'; print(f"  {s.get('company')}: flag cleared by {job['flag_cleared']['by']} — prepared")
        if s.get('status') in ('closed_or_not_greenhouse', 'closed_or_unreadable') and s.get('id') in by_id:   # JSA-417: prep saw no posting
            try:
                sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
                import job_closed
                if job_closed.confirm_mark(by_id[s['id']], s.get('why') or 'posting not found', 'prepare'):
                    print(f"  {s.get('company')}: closed — store marked 已关闭")
            except Exception as e:
                print(f'  (closed mark skipped: {type(e).__name__}: {str(e)[:80]})')
        pp = os.path.join(jpaths.apps(s['folder']), 'plan.json') if s.get('folder') else ''
        plan = json.load(open(pp)) if pp and os.path.exists(pp) else {}
        rows.append({'folder': s.get('folder') or '', 'company': s.get('company'), 'ats': ats_of(s, plan),
                     'track': track(s.get('track')), 'prep': s.get('status'), 'joey_tasks': s.get('joey_tasks') or [],
                     'materials': '', 'status': s.get('status') if s.get('status') != 'ok' else '',
                     'reasons': [s['why']] if s.get('why') else [],
                     'ready': False})
        if flag_cleared(job) and s.get('flags'):
            rows[-1]['flag_cleared'] = job['flag_cleared']; rows[-1]['flags'] = s['flags']
        left = gate[s['id']][1] if s.get('id') in gate else None
        if left is not None:
            rows[-1]['prefetch_left'] = left          # JSA-239: questions / files / tasks the prefetch still saw open
    for j in skipped:
        st = gate[j['id']][1]
        rows.append({'folder': '', 'company': j.get('company'), 'ats': platform(PO.posting_url(j)), 'track': track(j.get('track')),
                     'prep': 'skipped', 'joey_tasks': [], 'materials': '', 'status': st, 'reasons': [st], 'ready': False})
        print(f"  {j.get('company')}: {st} (prepare it anyway: --no-prefetch)")
    t1 = time.time(); print(f'prep: {round(t1 - t0, 1)}s')
    go = [r for r in rows if r['prep'] == 'ok' and r['folder'] and runner(r['ats'])]
    for r in rows:
        if r['prep'] == 'ok' and not runner(r['ats']):
            r['status'] = 'no runner in batch_apply'
    with ThreadPoolExecutor(PARALLEL_MATERIALS) as ex:
        for r, (m, _) in zip(go, ex.map(lambda r: materials(r['folder'], r['track'], a.fresh), go)):
            r['materials'] = m
    print(f'materials: {round(time.time() - t1, 1)}s for {len(go)} job(s)')
    if any(r['materials'].startswith('ok') and not offline(r['ats'], a.dry_run) for r in go):
        import chrome_lock; chrome_lock.hold(f'batch_apply prepare {os.path.basename(a.batch)}')   # JSA-236
    for r in go:                                   # one at a time: the job Chrome is shared; each runner closes its tab
        if not r['materials'].startswith('ok'):
            r['status'] = 'skipped'; continue
        if offline(r['ats'], a.dry_run):           # JSA-235: questions from the public form data, no browser
            items = offline_check(r['folder'], r['ats'])
            r.update(status='offline-ready' if not items else 'needs-user', secs=0, ready=not items,
                     reasons=[i['question'][:120] for i in items], questions=[i for i in items if i['kind'] == 'question'],
                     files=[i['question'] for i in items if i['kind'] == 'file'])
            print(f"  {r['folder']}: {r['status']} (offline){'' if r['ready'] else ' — ' + '; '.join(r['reasons'])[:160]}")
            continue
        r.update(run_one(r['folder'], r['ats'], submit=False))
        r['questions'] = needs_joey(r['folder'])
        print(f"  {r['folder']}: {r['status']} {r['secs']}s {'READY' if r['ready'] else '; '.join(r['reasons'])[:160]}")
    print(f'total: {round(time.time() - t0, 1)}s')
    write_report(a.batch, rows, 'Prepared')


def cmd_approve(a):
    if not a.by.strip():
        sys.exit('batch_apply approve: --by needs Joey\'s words from the chat')
    rows = json.load(open(side(a.batch, '.apply.json')))
    folders = [r['folder'] for r in rows if r.get('ready') and runner(r.get('ats')) and (not a.only or r['folder'] in a.only)]
    if not folders:
        sys.exit('batch_apply approve: no folder passed its dry-run — nothing approved')
    p = jpaths.data('runner', 'approved_batches.json')
    d = json.load(open(p)) if os.path.exists(p) else {'batches': []}
    d['batches'].append({'name': os.path.basename(a.batch).replace('.json', ''),
                         'approved_at': datetime.now().astimezone().isoformat(timespec='minutes'),
                         'approved_by': a.by, 'folders': folders})
    json.dump(d, open(p, 'w'), indent=1, ensure_ascii=False)
    print('approved:', *folders, sep='\n  ')


def cmd_submit(a):
    rows = json.load(open(side(a.batch, '.apply.json')))
    import chrome_lock; chrome_lock.hold(f'batch_apply submit {os.path.basename(a.batch)}')   # JSA-236
    t0 = time.time()
    out = []
    for r in rows:
        if a.only and r['folder'] not in a.only:
            continue
        if not r.get('folder') or not runner(r.get('ats')):
            continue
        if not approved(r['folder']):
            out.append({**r, 'status': 'not approved', 'reasons': ['not in approved_batches.json']}); continue
        d = run_one(r['folder'], r['ats'], submit=True, ds_ok=a.ds_ok)
        if d['status'] not in ('submitted', 'already-submitted'):     # met only on the live form (JSA-235): ask, rerun this one
            d['questions'] = needs_joey(r['folder'])
        out.append({**r, **d})
        print(f"  {r['folder']}: {d['status']} {d['secs']}s {'; '.join(d['reasons'])[:160]}")
    print(f'total: {round(time.time() - t0, 1)}s')
    write_report(a.batch, out, 'Submitted', '.submit')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('prepare'); p.add_argument('batch'); p.add_argument('--fresh', action='store_true')
    p.add_argument('--keep-closed', action='store_true', help='JSA-417: do not check the batch against the public ATS API first')
    p.add_argument('--no-prefetch', action='store_true', help='JSA-239: prepare every job, even one the form prefetch saw closed / restricted')
    p.add_argument('--dry-run', action='store_true', help='Greenhouse / Ashby / Lever too: fill once in the job Chrome first (demo, a board with conditional questions)')
    p.add_argument('--max', type=int)
    p = sub.add_parser('approve'); p.add_argument('batch'); p.add_argument('--by', required=True)
    p.add_argument('--only', nargs='*')
    p = sub.add_parser('clear-flag', help='JSA-418: Joey read the JD pre-screen flag of one job and said apply anyway')
    p.add_argument('batch'); p.add_argument('job', help='job id (or a company name that fits one job)')
    p.add_argument('--by', required=True); p.add_argument('--note', required=True, help="Joey's own words from the chat")
    p = sub.add_parser('submit'); p.add_argument('batch'); p.add_argument('--only', nargs='*')
    p.add_argument('--ds-ok', action='store_true', help='Workday: Claude spot-checked ds_used.json on Review (run_wd --ds-ok)')
    a = ap.parse_args()
    a.batch = os.path.abspath(a.batch)
    {'prepare': cmd_prepare, 'clear-flag': cmd_clear_flag, 'approve': cmd_approve, 'submit': cmd_submit}[a.cmd](a)


if __name__ == '__main__':
    main()
