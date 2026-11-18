#!/usr/bin/env python3
"""Daily learning loop, step 6 of the runner self-optimisation (JSA-191): improvement PROPOSALS and a metric card.

Reads what the runners recorded in the data home (data/runner/results.jsonl, fields/*.jsonl, wrong_answers.jsonl, the replay
report) and writes
  data/learn/proposals.jsonl   one entry per problem: id (type:sha1[:8]), type fact | rule | runner, key, status
                               open | fixing | fixed | wontfix, evidence (folders), fixed_by (commit), reopened (count)
  data/learn/card-<date>.md    per platform: runs, submitted, first-run-clean rate, runs per submit, Joey touches per submit;
                               open / fixed proposals; hand fixes to answer_rules.js / profile.json not linked to a proposal
It ONLY proposes: it never changes an answer, a rule or a saved answer (facts come from Joey). A proposal whose problem shows
again after it was marked fixed reopens itself. Types follow rule 10 (problem type):
  fact    the same question the rules could not answer on ≥ 2 forms
  rule    an answer found wrong after a submit (wrong_answers.jsonl), or a submitted answer the replay shows changed without a reason
  runner  the same stop (platform | stopped at | first problem) on ≥ 2 forms
(materials proposals — recurring skill gaps, checker false alarms — come with JSA-194.)

    python3 scripts/learn/learn.py                      # daily run: replay, proposals, card (no network, no model)
    python3 scripts/learn/learn.py --no-replay          # skip the form replay
    python3 scripts/learn/learn.py --list [--status open]
    python3 scripts/learn/learn.py --mark <id> fixed --commit <hash>      # also: fixing | wontfix | open
Tests: scripts/test_learn.py (DeepSeek cases scripts/test_cases/learn_cases.json).
"""
import argparse, hashlib, json, os, re, statistics, subprocess, sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
import learn_triage as TR  # noqa: E402

RUNNER_STOPS = {'blocked', 'handoff', 'failed', 'login-timeout', 'unconfirmed'}
JOEY_TOUCH = {'needs-user', 'captcha', 'login-timeout', 'unconfirmed', 'handoff'}
STATUSES = {'open', 'fixing', 'fixed', 'wontfix', 'ignored', 'superseded'}


def _when(s):
    try:
        d = datetime.fromisoformat(str(s))
        return d if d.tzinfo else d.astimezone()
    except (TypeError, ValueError):
        return None


def norm_q(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', str(s or '').lower())).strip()


def _sig(r):
    p = (r.get('problems') or [''])[0] if r.get('problems') else ''
    p = re.sub(r'\s+', ' ', re.sub(r'"[^"]*"|\'[^\']*\'', '', re.sub(r'\d+', '', str(p).lower()))).strip()[:60]
    return f"{r.get('ats') or ''}|{r.get('stopped_at') or ''}|{p}"


def findings(results, fields, wrong, replay, now, days=14):
    """Pure (tested). The problems of the last `days` days: [{'type', 'key', 'at', 'evidence'}] sorted by key."""
    lo = now - timedelta(days=days)
    fresh = lambda r: (_when(r.get('at')) or lo - timedelta(days=1)) >= lo
    acc = {}
    def add(type_, key, folder, at):
        e = acc.setdefault((type_, key), {'type': type_, 'key': key, 'at': at, 'evidence': set()})
        e['evidence'].add(folder)
        if _when(at) and _when(at) > _when(e['at']): e['at'] = at
    unk = {}
    for f in fields or []:
        if fresh(f) and f.get('ok') is False and not f.get('planned') and f.get('folder') and f.get('type') not in ('file', 'hidden') and f.get('source') not in ('runner', 'page'):   # an upload / hidden box is not a question
            unk.setdefault(norm_q(f.get('question')), []).append(f)
    for q, rows in unk.items():
        if q and len({r['folder'] for r in rows}) >= 2:
            for r in rows: add('fact', q, r['folder'], r['at'])
    for w in wrong or []:
        at = _when(str(w.get('found') or '') + 'T00:00:00+00:00')
        if at and at >= lo and w.get('folder'):
            add('rule', 'wrong:' + norm_q(w.get('field')), w['folder'], at.isoformat())
    for r in replay or []:
        if r.get('submitted') and not r.get('reason') and r.get('folder'):
            add('rule', 'replay:' + norm_q(r.get('question')), r['folder'], now.isoformat())   # still listed by today's replay = the problem shows again (a fix records its --reason, which stops the listing)
    sigs = {}
    for r in results or []:
        if fresh(r) and r.get('status') in RUNNER_STOPS and (r.get('problems') or r.get('stopped_at')) and r.get('folder'):
            sigs.setdefault(_sig(r), []).append(r)
    for sg, rows in sigs.items():
        if len({r['folder'] for r in rows}) >= 2:
            for r in rows: add('runner', sg, r['folder'], r['at'])
    out = [dict(e, evidence=sorted(e['evidence'])) for e in acc.values()]
    return sorted(out, key=lambda e: e['key'])


def pid(type_, key):
    return f"{type_}:{hashlib.sha1(key.encode('utf-8')).hexdigest()[:8]}"


def update_ledger(ledger, found, now):
    """Pure (tested). The ledger after today's findings: new → open; fixed + newer evidence → reopened; wontfix untouched."""
    ledger = [dict(e) for e in ledger or []]
    by = {e['id']: e for e in ledger}
    stamp = now if isinstance(now, str) else now.isoformat()
    new = []
    for f in found:
        i = pid(f['type'], f['key']); e = by.get(i)
        if e is None:
            new.append({'id': i, 'type': f['type'], 'key': f['key'], 'status': 'open', 'first_seen': stamp, 'last_seen': stamp,
                        'evidence': sorted(f['evidence']), 'fixed_by': None, 'fixed_at': None, 'reopened': 0})
        elif e['status'] in ('open', 'fixing'):
            e['last_seen'] = stamp; e['evidence'] = sorted(set(e.get('evidence') or []) | set(f['evidence']))
        elif e['status'] == 'superseded':                       # the problem is classified as this one again (a tie flipped back): it is open again
            e['status'] = 'open'; e.pop('superseded_by', None); e['last_seen'] = stamp; e['evidence'] = sorted(set(e.get('evidence') or []) | set(f['evidence']))
        elif e['status'] == 'fixed':
            fa, at = _when(e.get('fixed_at')), _when(f['at'])
            if fa is None or (at and at > fa):
                e['status'] = 'open'; e['reopened'] = int(e.get('reopened') or 0) + 1
                e['last_seen'] = stamp; e['evidence'] = sorted(set(e.get('evidence') or []) | set(f['evidence']))
    return ledger + sorted(new, key=lambda e: e['key'])


def platform_metrics(results, now, days=7):
    """Pure (tested). Per platform over the last `days` days: runs, submitted, clean_first_rate, runs_per_submit, joey_per_submit."""
    lo = now - timedelta(days=days)
    rows = [r for r in results or [] if (_when(r.get('at')) or lo - timedelta(days=1)) >= lo and r.get('folder')]
    out = {}
    for ats in sorted({r.get('ats') or '' for r in rows}):
        rs = [r for r in rows if (r.get('ats') or '') == ats]
        folders = sorted({r['folder'] for r in rs})
        sub = {r['folder'] for r in rs if r.get('status') == 'submitted'}
        first = {}
        for r in sorted(rs, key=lambda r: _when(r['at'])): first.setdefault(r['folder'], r)
        clean = sum(1 for r in first.values() if not r.get('problems') and r.get('status') in ('submitted', 'dry-run'))
        touched = {r['folder'] for r in rs if r.get('status') in JOEY_TOUCH}
        out[ats] = {'runs': len(rs), 'submitted': len(sub),
                    'clean_first_rate': round(clean / len(folders), 2) if folders else None,
                    'runs_per_submit': round(len(rs) / len(sub), 2) if sub else None,
                    'joey_per_submit': round(len(touched) / len(sub), 2) if sub else None}
    return out


def phase_medians(results, now, days=7):
    """Median runner seconds by phase per platform (submitted rows with `phases`)."""
    lo = now - timedelta(days=days); out = {}
    for r in results or []:
        if r.get('status') == 'submitted' and isinstance(r.get('phases'), dict) and (_when(r.get('at')) or lo - timedelta(days=1)) >= lo:
            for k, v in r['phases'].items():
                out.setdefault(r.get('ats') or '', {}).setdefault(k, []).append(v)
    return {a: {k: round(statistics.median(v), 1) for k, v in ph.items()} for a, ph in out.items()}


def parse_replay_report(text):
    """Pure (tested by the card run). Rows of the replay report's 'Submitted answers changed without a reason' section."""
    rows, on = [], False
    for line in str(text or '').splitlines():
        if line.startswith('## '): on = line.startswith('## Submitted answers changed without a reason'); continue
        m = on and re.match(r"^- (?:\*\*SUBMITTED\*\* )?(\S+) · (['\"])(.*?)\2: ", line)
        if m: rows.append({'folder': m.group(1), 'question': m.group(3), 'submitted': True, 'reason': None})
    return rows


def hand_fixes(commits, ledger_ids):
    """Pure. Commits (hash, subject) to answer_rules.js whose subject names no proposal id and that no proposal was marked fixed by (`fixed_by`)."""
    linked = re.compile(r'\b(?:fact|rule|qtype|page|runner|ignore|unsure|materials):[0-9a-f]{8}\b')
    return [(h, s) for h, s in commits or [] if not linked.search(s or '') and not any(str(c)[:7] == h[:7] for c in ledger_ids or [] if c)]


def card(day, ledger, metrics, phases, hand, model_note=''):
    L = [f'# Learn card — {day}', '']
    if model_note: L += [f'> {model_note}', '']
    if not metrics:
        L += ['No runs in the last 7 days.', '']
    else:
        L += ['## Platforms (last 7 days)', '', '| platform | runs | submitted | first run clean | runs / submit | Joey touches / submit | seconds by phase |', '| --- | --- | --- | --- | --- | --- | --- |']
        pct = lambda v: '–' if v is None else f'{round(v * 100)} %'
        num = lambda v: '–' if v is None else str(v)
        for a, m in metrics.items():
            L.append(f"| {a or '?'} | {m['runs']} | {m['submitted']} | {pct(m['clean_first_rate'])} | {num(m['runs_per_submit'])} | {num(m['joey_per_submit'])} | "
                     + (', '.join(f'{k} {v}' for k, v in sorted(phases.get(a, {}).items())) or '–') + ' |')
        L.append('')
    cnt = lambda s: sum(1 for e in ledger if e['status'] == s)
    L += [f"## Proposals — open {cnt('open')} · fixing {cnt('fixing')} · fixed {cnt('fixed')} · wontfix {cnt('wontfix')} · ignored {cnt('ignored')}", '']
    cat = lambda e: e.get('category') or e['type']
    for c, title in (('fact', 'fact — a fact of Joey\'s is missing (the morning question sheet asks him)'), ('rule', 'rule — the fact exists, the rules missed or got it wrong'),
                     ('qtype', 'qtype — the rules took the question for another type'), ('page', 'page — page / options / control problem'),
                     ('runner', 'runner — program problem'), ('unsure', 'unsure — not confirmed (a second read disagreed, bad evidence) — the Sunday review clears these')):
        rows = [e for e in ledger if e['status'] in ('open', 'fixing') and cat(e) == c]
        if not rows: continue
        L += [f'### {title} — {len(rows)}', '']
        for e in rows:
            why = (f" — “{e['evidence_text'][:80]}”" if e.get('evidence_text') else '') + (f" [{e['reason']}]" if e.get('reason') else '')
            L.append(f"- `{e['id']}` {e['status']}{' (reopened ×%d)' % e['reopened'] if e.get('reopened') else ''} — {e['key'][:90]} — {len(e['evidence'])} form(s)"
                     + (f", {len(e['members'])} wordings" if len(e.get('members') or []) > 1 else '') + why)
        L.append('')
    L += [f'## Hand fixes outside the loop: {len(hand)}', ''] + [f'- {h} {s[:100]}' for h, s in hand] + ['']
    return '\n'.join(L)


def _jsonl(p):
    out = []
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            try: r = json.loads(l)
            except ValueError: continue
            if isinstance(r, dict): out.append(r)
    return out


def load_ledger(p): return _jsonl(p)


def save_ledger(p, ledger):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as o:
        for e in ledger: o.write(json.dumps(e, ensure_ascii=False) + '\n')
    os.replace(tmp, p)


def mark(ledger, pid_, status, commit=None, now=None):
    """Pure (tested by the CLI test). Set a proposal's status; 'fixed' records the commit and the time."""
    if status not in STATUSES: raise ValueError(f'status must be one of {sorted(STATUSES)}')
    for e in ledger:
        if e['id'] == pid_:
            e['status'] = status
            if status == 'fixed': e['fixed_by'] = commit; e['fixed_at'] = now or datetime.now().astimezone().isoformat(timespec='seconds')
            return True
    return False


def infer_ats(row):
    """Pure (tested, JSA-400). The platform of a run row: its `ats`, else read from its application link (25+ runs showed '?' on the card)."""
    if row.get('ats'): return row['ats']
    try:
        import posting
        return posting.platform(row.get('url') or '') or ''
    except Exception:
        return ''


def profile_values(profile):
    """Pure. Every value of the fact library (profile.json, saved answers included) worth hiding from a model: strings / numbers of 3+ characters,
    not plain yes / no words."""
    out = set()
    def walk(v):
        if isinstance(v, dict):
            for x in v.values(): walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
        elif isinstance(v, (str, int, float)) and not isinstance(v, bool):
            t = str(v).strip()
            if len(t) >= 3 and t.lower() not in ('yes', 'no', 'n/a', 'none', 'true', 'false', 'other'): out.add(t)
    walk(profile)
    return out


def redact(text, values):
    """Pure (tested). A note / error text for the model with every fact value hidden: what follows 'fact' / 'profile' in the audit's notes (the fact
    itself) is cut, profile values → [hidden], e-mail addresses → [email], web links → [link], digit runs of 4+ → #."""
    t = str(text or '')
    t = re.sub(r'\b(?:pay fact|start date fact|fact|profile|standard)\b[ :=]*[^;)]*?(?=\s*\((?:found|JSA)|[;)]|$)', '[hidden]', t, flags=re.I)
    for v in sorted(values or (), key=len, reverse=True):
        t = re.sub(re.escape(v), '[hidden]', t, flags=re.I)
    t = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[email]', t)
    t = re.sub(r'https?://\S+', '[link]', t)
    return re.sub(r'\d{4,}', '#', t)


def fact_library_hits(question, qa_questions, shadow_fact_key=None):
    """Pure (tested). KEY NAMES only (never contents) of the fact library entries that cover a question: saved answers (qa) whose question text
    matches, and the question-type reader's fact key. [] = none."""
    q = norm_q(question); hits = []
    for t in qa_questions or []:
        n = norm_q(t)
        if n and q and (n == q or (len(n) >= 12 and (n in q or q in n))): hits.append(f'qa:"{str(t)[:50]}"')
    if shadow_fact_key and shadow_fact_key not in ('unknown', 'none', ''): hits.append(f'fact:{shadow_fact_key}')
    return hits[:4]


def build_material(f, fields, results, wrong, shadow, qa_questions, hide=()):
    """What the model reads about one candidate (a finding): the question, options, what the rules did, the stops, the library keys — no fact content."""
    m = {}      # no counts: the material must not change as evidence grows (the cache is keyed by its hash)
    if f['type'] == 'fact':
        rows = [r for r in fields if norm_q(r.get('question')) == f['key'] and r.get('ok') is False and not r.get('planned')]
        r = rows[0] if rows else {}
        sh = next((x for x in shadow if norm_q(x.get('question')) == f['key']), None) or {}
        m.update(found_by='the rules left this question unanswered (nothing was filled)', question=r.get('question'), field_type=r.get('type'), required=r.get('required'), options=(r.get('options') or [])[:10],
                 rules_output='(nothing)', rules_source=redact(r.get('source') or '', hide), platforms=sorted({x.get('ats') or '' for x in rows}),
                 fact_library=fact_library_hits(r.get('question'), qa_questions, (sh.get('reading') or {}).get('fact_key')) or 'none',
                 type_reader=(sh.get('reading') or {}).get('fact_key'))
    elif f['type'] == 'rule':
        w = [x for x in wrong if 'wrong:' + norm_q(x.get('field')) == f['key']]
        m.update(found_by='the rules ANSWERED this question WRONGLY (found by the independent audit / replay)', question=(w[0].get('field') if w else f['key']),
                 what_went_wrong=[redact(str(x.get('note')), hide)[:300] for x in w[:2]] or f['key'])
    else:
        rows = [r for r in results if r.get('folder') in f['evidence'] and _sig(r) == f['key']]
        r = rows[0] if rows else {}
        m.update(found_by='the runner stopped', platform=r.get('ats') or '', stopped_at=r.get('stopped_at'), status=r.get('status'), problems=[redact(str(x), hide)[:200] for x in (r.get('problems') or [])[:2]])
    return m


def fact_index(profile):
    """Pure. NAMES of the fact library's entries (profile keys and one level below; saved-answer questions are `qa_questions`), never contents."""
    out = []
    for k, v in (profile or {}).items():
        if k.startswith('_') or k in ('qa', 'answers', 'resume_template', 'transcript'): continue
        out.append(k)
        if isinstance(v, dict): out += [f'{k}.{x}' for x in v if not str(x).startswith('_')]
    return out


def triage_found(found, fields, results, wrong, shadow, qa_questions, ask, cache, usage=None, index=None, hide=(), on_batch=None):
    """Model triage of the legacy findings → findings of the new categories, merged by the model's groups (ModelUnavailable propagates)."""
    cands = [{'id': pid(f['type'], f['key']), 'material': build_material(f, fields, results, wrong, shadow, qa_questions, hide)} for f in found]   # stable ids: the cache and its groupings outlive the day
    res, groups = TR.triage(cands, ask, cache, usage, index, on_batch)
    by = {c['id']: found[i] for i, c in enumerate(cands)}
    for g in groups: g[:] = [i for i in g if i in by]
    out = []
    for g in groups:
        members = [by[i] for i in g]
        cats = [res[i]['category'] for i in g]
        top = max(set(cats), key=cats.count); cat = top if cats.count(top) * 2 > len(cats) else 'unsure'
        rep = min(g, key=lambda i: by[i]['key'])
        win = [i for i in g if res[i]['category'] == cat] or [rep]
        shown = min(win, key=lambda i: by[i]['key'])             # the text shown is a member of the winning category
        out.append({'type': cat, 'key': by[rep]['key'], 'at': max((m['at'] for m in members), key=lambda a: _when(a) or datetime.min.astimezone()),
                    'evidence': sorted({e for m in members for e in m['evidence']}), 'members': sorted(m['key'] for m in members),
                    'evidence_text': res[shown]['evidence'], 'confidence': res[shown]['confidence'], 'reason': res[shown].get('reason', '')})
    return sorted(out, key=lambda e: e['key'])


def apply_triage_to_ledger(ledger, triaged):
    """Pure (tested). After update_ledger with triaged findings: the model's fields on the entries; ignore → status 'ignored'. An older entry
    (the rule-classified one, or a categorised one whose group / category changed) that covers any of the same problems is SUPERSEDED, and a
    new entry takes over its fixing / fixed / wontfix state (Joey's wontfix and the fix history are not lost)."""
    new_ids = {pid(t['type'], t['key']): t for t in triaged}
    by_id = {e['id']: e for e in ledger}
    for i, t in new_ids.items():
        e = by_id.get(i)
        if not e: continue
        e.update(category=t['type'], evidence_text=t['evidence_text'], confidence=t['confidence'], members=t['members'], reason=t.get('reason', ''))
        covered = set(t['members'])
        for old in ledger:
            if old['id'] == i or old['status'] == 'superseded' or old['id'] in new_ids: continue
            if old.get('key') in covered or covered & set(old.get('members') or []):
                if old['status'] in ('fixing', 'fixed', 'wontfix') and e['status'] in ('open', 'ignored') and not e.get('fixed_by'):
                    e['status'] = old['status']; e['fixed_by'] = old.get('fixed_by'); e['fixed_at'] = old.get('fixed_at')
                old['status'] = 'superseded'; old['superseded_by'] = i
        if t['type'] == 'ignore' and e['status'] == 'open': e['status'] = 'ignored'
    return ledger


def load_cache(p):
    c = {}
    for r in _jsonl(p):
        if 'k' in r and 'v' in r: c[r['k']] = r['v']
    return c


def save_cache(p, cache):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + '.tmp', 'w', encoding='utf-8') as o:
        for k, v in cache.items(): o.write(json.dumps({'k': k, 'v': v}, ensure_ascii=False) + '\n')
    os.replace(p + '.tmp', p)


def run(now=None, replay=True, data=None, log=print, model=True, ask=None, apps=None):
    now = now or datetime.now().astimezone(); data = data or jpaths.data()
    rd = os.path.join(data, 'runner'); ld = os.path.join(data, 'learn')
    fields = []
    for fn in sorted(os.listdir(os.path.join(rd, 'fields'))) if os.path.isdir(os.path.join(rd, 'fields')) else []:
        if fn.endswith('.jsonl'): fields += _jsonl(os.path.join(rd, 'fields', fn))
    results, wrong = _jsonl(os.path.join(rd, 'results.jsonl')), _jsonl(os.path.join(rd, 'wrong_answers.jsonl'))
    apps_dir = apps or jpaths.apps()
    existing = set(os.listdir(apps_dir)) if os.path.isdir(apps_dir) else None
    ok_f = lambda r: not TR.trial_folder(r.get('folder'), existing)         # dry runs / test folders / non-applications never count as evidence
    fields, results, wrong = [r for r in fields if ok_f(r)], [r for r in results if ok_f(r)], [r for r in wrong if ok_f(r)]
    for r in results: r['ats'] = infer_ats(r)
    rep = []
    if replay:
        try:
            t0 = now.timestamp() - 1
            subprocess.run([sys.executable, os.path.join(HERE, 'replay.py'), '--check'], capture_output=True, timeout=600)
            lp_ = os.path.join(rd, 'replay', 'last.md')
            if os.path.getmtime(lp_) < t0: log('replay did not write a fresh report — replay findings skipped'); rep = []
            else: rep = parse_replay_report(open(lp_, encoding='utf-8').read())
        except Exception as e:
            log(f'replay failed ({type(e).__name__}) — proposals without it')
    lp = os.path.join(ld, 'proposals.jsonl')
    rep = [r for r in rep if ok_f(r)]
    found = findings(results, fields, wrong, rep, now)
    used_model = False
    if model and found:
        cp_ = os.path.join(ld, 'triage_cache.jsonl'); cache = load_cache(cp_)
        try:
            prof = json.load(open(jpaths.config('profile.json'), encoding='utf-8'))
            qa = [q.get('q') for q in (prof.get('qa') or []) if isinstance(q, dict)]
        except Exception:
            prof, qa = {}, []
        try:
            triaged = triage_found(found, fields, results, wrong, _jsonl(os.path.join(rd, 'qtype_shadow.jsonl')), qa, ask or TR.ask_model, cache, index=fact_index(prof),
                                   hide=profile_values(prof), on_batch=lambda: save_cache(cp_, cache))
            save_cache(cp_, cache); used_model = True
        except TR.ModelUnavailable as e:
            log(f'model unavailable ({e}) — the old rules classify today')
    if used_model:
        ledger = apply_triage_to_ledger(update_ledger(load_ledger(lp), triaged, now), triaged)
    else:
        ledger = update_ledger(load_ledger(lp), found, now)
    save_ledger(lp, ledger)
    commits = []
    try:
        out = subprocess.run(['git', '-C', ROOT, 'log', '--since=7 days ago', '--format=%h\t%s', '--', 'skills/auto-apply/scripts/answer_rules.js'],
                             capture_output=True, text=True, timeout=30).stdout
        commits = [tuple(l.split('\t', 1)) for l in out.splitlines() if '\t' in l]
    except Exception:
        pass
    text = card(now.date().isoformat(), ledger, platform_metrics(results, now), phase_medians(results, now), hand_fixes(commits, {e.get('fixed_by') for e in ledger}), '' if used_model or not model else 'model not used today (unavailable) — classified by the old rules')
    cp = os.path.join(ld, f'card-{now.date().isoformat()}.md')
    open(cp + '.tmp', 'w', encoding='utf-8').write(text); os.replace(cp + '.tmp', cp)
    log(f"learn: {sum(1 for e in ledger if e['status'] == 'open')} open proposals · card {cp}")
    return ledger


def _commit_learn(subject):
    """JSA-412: proposals.jsonl, the card, triage_golden commit on the spot (triage_cache.jsonl is ignored); best effort."""
    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
        import data_git
        data_git.commit_tree('data/learn', subject)
    except Exception:  # noqa: BLE001
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-replay', action='store_true'); ap.add_argument('--no-model', action='store_true'); ap.add_argument('--list', action='store_true'); ap.add_argument('--status')
    ap.add_argument('--mark', nargs=2, metavar=('ID', 'STATUS')); ap.add_argument('--commit')
    a = ap.parse_args()
    lp = os.path.join(jpaths.data('learn'), 'proposals.jsonl')
    if a.mark:
        led = load_ledger(lp)
        if not mark(led, a.mark[0], a.mark[1], a.commit): print(f'no proposal {a.mark[0]}'); return 1
        save_ledger(lp, led); print(f'{a.mark[0]} → {a.mark[1]}'); _commit_learn(f'data: learn {a.mark[0]} → {a.mark[1]}'); return 0
    if a.list:
        for e in load_ledger(lp):
            if not a.status or e['status'] == a.status: print(e['id'], e['status'], e['key'][:90], f"({len(e['evidence'])} forms)")
        return 0
    run(replay=not a.no_replay, model=not a.no_model)
    _commit_learn('data: learn run')
    return 0


if __name__ == '__main__':
    sys.exit(main())
