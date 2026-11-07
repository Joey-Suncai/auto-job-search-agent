#!/usr/bin/env python3
"""Platform scorecard (JSA-045): per ATS, the certification numbers from files — never from a model's say-so.

Sources: data/runner/results.jsonl (every runner run) · data/store/emails.jsonl (company mail, the independent proof of
receipt) · folder → job id (sync_results.folder_job_ids) · applications/<folder>/ds_usage.md (materials cost) ·
data/runner/wrong_answers.jsonl (wrong answers found after a submit, one {"folder", "field", "note", "found"} per line).
Bar (Joey 2026-10-31, docs/specs/runner-platform-expansion.md): ≥ 50 submitted · no hands-on action by Joey ≥ 95 %
(「只要不需要我介入的情况能大于95%即可」; first dry-run clean is reported, not a bar) ·
proof of receipt ≥ 95 % — the company's e-mail within 48 h **or** the confirmation page (Joey 2026-11-04 「Yes, count the
page」: many Ashby / Workday companies send no e-mail; `page_proof`) · 0 wrong answers · median runner time ≤ 5 min · DeepSeek ≤ $0.01 per application.
Not in the files, so not scored: Joey's hands-on minutes (reported as a count of applications that needed him).
Claude tokens (info, no bar — Joey 2026-11-02 「平台认证进度还需要加入 token 消耗量的统计」): read from the Claude Code session
transcripts (~/.claude/projects/*job-search-agent*/**/*.jsonl, every assistant reply's usage, de-duplicated by message id —
forked sessions repeat their parent's lines) and attributed to applications by time with claude_tokens(); claude.ai and
DeepSeek-harness sessions are not in those files.

    python3 scripts/platform_scorecard.py                  # certification window (folders first run since CERT_SINCE)
    python3 scripts/platform_scorecard.py --all            # every run (baseline)
    python3 scripts/platform_scorecard.py --out <file.md> [--since 2026-10-28] [--json]
Spec + DeepSeek-written cases: scripts/test_cases/platform_scorecard_*; harness scripts/test_platform_scorecard.py.
"""
import argparse, glob, json, os, re, sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, HERE)
from field_class import field_class  # noqa: E402  (critical / non-critical questions, Joey 2026-11-05)
PRICE_IN, PRICE_OUT = 0.28, 0.42            # USD per 1M DeepSeek tokens (ds_materials.PRICE miss / out)
PROOF = {'Confirmation', 'Rejection', 'Assessment', 'Interview', 'Offer'}
BAR = dict(n=50, no_joey=0.95, clean=0.95, confirm=0.95, secs=300, cost=0.01)   # clean = info only (Joey 10-31)
NONCRIT = 0.95                                 # non-critical answers right ≥ 95 % (Joey 2026-11-05)
# Wrong answers (Joey 2026-11-05 「重要信息不能错，非重要信息能够达到95%以上正确率」, 「就按这个分」): a CRITICAL wrong answer
# (scripts/field_class.py: work authorization / visa, education, contact, EEO, experience / references) fails the platform;
# NON-CRITICAL answers (source, pay, start date, location …) must be ≥ 95 % right over the submitted forms' non-critical fields.
# Per-platform changes (Joey 2026-11-02 「Lever 就凑满30份吧。到时候单独说明一下 Lever 需要最后一步手动提交」): Lever needs 30,
# and its no-Joey rate is info only — the last step (Submit in Joey's Edge past hCaptcha) is his by rule 7.
PLATFORM_BAR = {'lever': dict(n=30, no_joey=None)}
PLATFORM_NOTE = {'lever': 'Lever: bar 30 submitted (Joey 2026-11-02); the last step is manual by design — hCaptcha stops the runner\'s Submit, '
                          'so Joey clicks Submit in his Edge (the fill extension has filled and read back the form). No-Joey rate = info only.'}


def bar_for(name):
    """Pure (tested): the certification bar for one platform — BAR with that platform's changes; None = info only."""
    return {**BAR, **PLATFORM_BAR.get(name, {})}
CERT_SINCE = '2026-10-31T19:00'                # Joey 2026-10-31 「从这次重新算」: certification counts folders first run from here
FOLDER = re.compile(r'^\d{4}-\d{2}-\d{2}_')


def platform(line):
    u = (line.get('url') or '').lower()
    for key, name in (('greenhouse', 'greenhouse'), ('myworkday', 'workday'), ('lever.co', 'lever'), ('ashbyhq', 'ashby')):
        if key in u:
            return name
    return line.get('ats') or 'other'


def clean(line):
    return (line.get('status') in ('dry-run', 'submitted') and not line.get('problems')
            and not any(line.get(k) for k in ('bad', 'failed', 'needs')) and line.get('verify_pass') is not False)


def median(xs):
    if not xs:
        return None
    xs = sorted(xs); m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def rate(a, b):
    return round(a / b, 4) if b else None


def page_proof(line, shot):
    """Pure (tested). The submit line proves receipt by the page: the runner saw the thank-you / submitted page
    (`confirmed_by` starting with 'page'), or a runner submit with no `confirmed_by` whose folder holds
    submitted_confirmation.* (run_form / run_wd screenshot only after the confirmation page). An e-mail-confirmed submit
    (`confirmed_by` 'email') and Joey's own submits (`by` 'joey') never count by the page."""
    cb = str(line.get('confirmed_by') or '')
    if line.get('by') == 'joey' or cb == 'email':
        return False
    return cb.startswith('page') or (not cb and bool(shot))


def score(results, emails, fmap, ds_cost, wrong, today, shots=frozenset(), recert=None, field_counts=None):
    """Pure (tested). See the module doc and scripts/test_cases/platform_scorecard_spec.md.
    recert = {platform: {'since': 'YYYY-MM-DDTHH:MM:SS', 'need': n}} (data/runner/recertify.json, JSA-188): a platform that had
    wrong answers passes the wrong-answer bar again once `need` applications submitted at/after `since` have 0 wrong
    answers (the earlier wrong answers stay in the count shown; spec test_cases/platform_recert_spec.md).
    Wrong answers are CRITICAL or NON-CRITICAL (a line's `class`, else scripts/field_class.py on its `field`); field_counts =
    {folder: non-critical answers on its submitted form} (the fields corpus) is the denominator of the 95 % bar; re-cert
    counts critical wrong answers only (spec test_cases/scorecard_critical_spec.md)."""
    by = {}
    for r in sorted((r for r in results if FOLDER.match(r.get('folder') or '')), key=lambda r: r.get('at') or ''):
        by.setdefault(r['folder'], []).append(r)
    day = lambda s: date.fromisoformat(s[:10])
    td = day(today)
    out = {}
    for folder, lines in by.items():
        p = out.setdefault(platform(lines[0]), dict(folders=0, clean=0, submitted=0, needed_joey=0, confirmed=0, by_email=0, by_page=0, pending=0,
                                                    wrong_answers=0, critical_wrong=0, noncrit_wrong=0, noncrit_answers=0, recert_submitted=0, recert_wrong=0, _secs=[], _cost=[]))
        p['folders'] += 1
        p['clean'] += clean(lines[0])
        subs = [i for i, r in enumerate(lines) if r.get('status') == 'submitted']
        if not subs:
            continue
        i = subs[0]; sday = day(lines[i]['at'])
        p['submitted'] += 1
        p['needed_joey'] += lines[i].get('by') == 'joey' or any(r.get('status') == 'captcha' for r in lines[:i])   # Joey 10-31: only his hands count
        jid = fmap.get(folder)
        if jid and any(e.get('job_id') == jid and e.get('type') in PROOF and sday <= day(e['date']) <= sday + timedelta(days=2)
                       for e in emails if e.get('date')):
            p['confirmed'] += 1; p['by_email'] += 1
        elif page_proof(lines[i], folder in shots):
            p['confirmed'] += 1; p['by_page'] += 1
        elif td <= sday + timedelta(days=2):
            p['pending'] += 1
        mine = [w for w in wrong if w.get('folder') == folder]
        crit = sum(1 for w in mine if (w.get('class') or field_class(w.get('field'))[0]) == 'critical')
        p['wrong_answers'] += len(mine); p['critical_wrong'] += crit; p['noncrit_wrong'] += len(mine) - crit
        p['noncrit_answers'] += int((field_counts or {}).get(folder) or 0)
        nw = crit                                                  # re-certification counts critical wrong answers
        rc = (recert or {}).get(platform(lines[0]))
        if rc and str(lines[i].get('at') or '')[:19] >= str(rc.get('since') or '')[:19]:
            p['recert_submitted'] += 1; p['recert_wrong'] += nw
        if any(r.get('secs') is not None for r in lines):        # early Greenhouse runs logged no time: not logged ≠ 0 s
            p['_secs'].append(sum(r.get('secs') or 0 for r in lines))
        p['_cost'].append((ds_cost.get(folder) or 0) + sum(((r.get('deepseek') or {}).get('prompt', 0) * PRICE_IN
                                                           + (r.get('deepseek') or {}).get('out', 0) * PRICE_OUT) / 1e6 for r in lines))
    for name, p in out.items():
        secs, cost = p.pop('_secs'), p.pop('_cost')
        p['first_clean_rate'] = rate(p.pop('clean'), p['folders'])
        p['confirm_rate'] = rate(p['confirmed'], p['submitted'] - p['pending'])
        p['no_joey_rate'] = rate(p['submitted'] - p['needed_joey'], p['submitted'])
        p['median_secs'], p['timed'] = median(secs), len(secs)
        p['mean_ds_cost'] = round(sum(cost) / len(cost), 6) if cost else None
        ok = lambda v, f: v is not None and f(v)
        b = bar_for(name)
        p['bar'] = b
        p.update(n_ok=p['submitted'] >= b['n'], no_joey_ok=True if b['no_joey'] is None else ok(p['no_joey_rate'], lambda v: v >= b['no_joey']), clean_ok=ok(p['first_clean_rate'], lambda v: v >= BAR['clean']),
                 confirm_ok=ok(p['confirm_rate'], lambda v: v >= BAR['confirm']),
                 crit_ok=(p['critical_wrong'] == 0) if not (recert or {}).get(name) else
                         (p['recert_wrong'] == 0 and p['recert_submitted'] >= int((recert or {})[name].get('need') or 0)),
                 time_ok=ok(p['median_secs'], lambda v: v <= BAR['secs']), cost_ok=ok(p['mean_ds_cost'], lambda v: v <= BAR['cost']))
        p['recert_need'] = int((recert or {}).get(name, {}).get('need') or 0) or None
        p['noncrit_accuracy'] = (round(1 - p['noncrit_wrong'] / p['noncrit_answers'], 4)
                                 if p['noncrit_answers'] else None)
        p['noncrit_ok'] = (p['noncrit_wrong'] == 0) if p['noncrit_accuracy'] is None else p['noncrit_accuracy'] >= NONCRIT
        p['wrong_ok'] = p['crit_ok'] and p['noncrit_ok']
        p['certified'] = all(p[k] for k in ('n_ok', 'no_joey_ok', 'confirm_ok', 'wrong_ok', 'time_ok', 'cost_ok'))   # clean_ok = info only
    return out


def claude_tokens(msgs, results):
    """Pure (tested). Claude token use per platform, attributed by time (spec: test_cases/claude_tokens_spec.md).
    msgs = [{'t': local 'YYYY-MM-DDTHH:MM:SS', 'total': n, 'new': n}] (total = every token billed incl. cache reads;
    new = input + cache writes + output). results = runner lines (folder, at = local end of the run, secs, url).
    A reply inside a run window [at - secs, at] belongs to the folder(s) running then (split evenly); else inside a folder's
    span (first run start .. last run end: answering its questions, fixing its page) → those folders; else it is overhead of
    that day (picking the batch, code fixes, docs), shared among the platforms by their number of folders run that day.
    → {platform: {'submitted', 'direct_median': [total, new] | None, 'direct_sum', 'overhead', 'all_in_per_app': [..] | None},
       '_unallocated': [total, new]}"""
    by, plat, subm = {}, {}, set()
    for r in results:
        f = r.get('folder')
        if not f or not r.get('at'):
            continue
        end = datetime.fromisoformat(r['at'][:19]); start = end - timedelta(seconds=float(r.get('secs') or 0))
        by.setdefault(f, []).append((start, end)); plat.setdefault(f, platform(r))
        if r.get('status') == 'submitted':
            subm.add(f)
    span = {f: (min(a for a, _ in w), max(b for _, b in w)) for f, w in by.items()}
    direct = {f: [0, 0] for f in by}; over = {}
    for m in msgs:
        t = datetime.fromisoformat(m['t'][:19]); v = (m.get('total') or 0, m.get('new') or 0)
        hit = [f for f, w in by.items() if any(a <= t <= b for a, b in w)] or [f for f, (a, b) in span.items() if a <= t <= b]
        if hit:
            for f in hit:
                direct[f][0] += v[0] / len(hit); direct[f][1] += v[1] / len(hit)
        else:
            o = over.setdefault(m['t'][:10], [0, 0]); o[0] += v[0]; o[1] += v[1]
    runs_day = {}
    for f, w in by.items():
        for d in {a.date().isoformat() for a, _ in w} | {b.date().isoformat() for _, b in w}:
            runs_day.setdefault(d, {}).setdefault(plat[f], set()).add(f)
    out = {p: dict(submitted=0, direct_sum=[0, 0], overhead=[0, 0], _d=[]) for p in set(plat.values())}
    for f, v in direct.items():
        q = out[plat[f]]; q['direct_sum'][0] += v[0]; q['direct_sum'][1] += v[1]
        if f in subm:
            q['submitted'] += 1; q['_d'].append(v)
    unalloc = [0, 0]
    for d, v in over.items():
        share = runs_day.get(d)
        if not share:
            unalloc[0] += v[0]; unalloc[1] += v[1]; continue
        n = sum(len(x) for x in share.values())
        for p, fs in share.items():
            out[p]['overhead'][0] += v[0] * len(fs) / n; out[p]['overhead'][1] += v[1] * len(fs) / n
    for p, q in out.items():
        ds = q.pop('_d')
        q['direct_median'] = [round(median([x[0] for x in ds])), round(median([x[1] for x in ds]))] if ds else None
        q['direct_sum'] = [round(x) for x in q['direct_sum']]; q['overhead'] = [round(x) for x in q['overhead']]
        q['all_in_per_app'] = ([round((q['direct_sum'][i] + q['overhead'][i]) / q['submitted']) for i in (0, 1)]
                               if q['submitted'] else None)
    out['_unallocated'] = [round(x) for x in unalloc]
    return out


# ---------- file loading (not part of the pure step) ----------
def jsonl(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()] if os.path.exists(p) else []


def ds_costs(apps):
    out = {}
    for p in glob.glob(os.path.join(apps, '*', 'ds_usage.md')):
        tot = sum(float(m) for m in re.findall(r'est\. cost=\$([\d.]+)', open(p, encoding='utf-8').read()))
        out[os.path.basename(os.path.dirname(p))] = tot
    return out


def noncrit_counts(fields_dir):
    """{folder: non-critical answered fields on its LATEST run} from the fields corpus (data/runner/fields/*.jsonl,
    JSA-187/188) — the denominator of the 95 % non-critical bar. File uploads are not answers."""
    runs = {}
    for p in glob.glob(os.path.join(fields_dir, '*.jsonl')):
        for d in jsonl(p):
            f = d.get('folder')
            if not f or str(d.get('type') or '').lower() == 'file':
                continue
            at = str(d.get('at') or '')
            cur = runs.get(f)
            if cur is None or at > cur[0]:
                runs[f] = (at, d.get('run_id'), [])
                cur = runs[f]
            if d.get('run_id') == cur[1]:
                cur[2].append(d.get('question') or '')
    return {f: sum(1 for q in qs if field_class(q)[0] == 'non-critical') for f, (_, _, qs) in runs.items()}


def load(root=ROOT, since=None):
    sys.path.insert(0, os.path.join(root, 'scripts', 'store'))
    import sync_results
    D = jpaths.data if root == ROOT else (lambda *p: os.path.join(root, 'data', *p))           # a test passes its own root  paths-ok
    A = jpaths.apps if root == ROOT else (lambda *p: os.path.join(root, 'applications', *p))   # paths-ok
    results = jsonl(D('runner', 'results.jsonl'))
    if since:                                    # a folder counts only when its FIRST run is on/after `since`
        first = {}
        for r in results:
            first[r['folder']] = min(first.get(r['folder'], '9'), r.get('at') or '')
        results = [r for r in results if first[r['folder']] >= since]
    return (results, jsonl(D('store', 'emails.jsonl')), sync_results.folder_job_ids(),
            ds_costs(A()), jsonl(D('runner', 'wrong_answers.jsonl')),
            frozenset(os.path.basename(os.path.dirname(p)) for p in glob.glob(A('*', 'submitted_confirmation.*'))))


CLAUDE_DIRS = os.environ.get('CLAUDE_PROJECTS_GLOB', os.path.expanduser('~/.claude/projects/*job-search-agent*'))


def claude_msgs(since=None, dirs=CLAUDE_DIRS):
    """Every assistant reply in the agent's Claude Code transcripts, once per message id, time in Chicago local."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('America/Chicago')
    except Exception:
        tz = timezone(timedelta(hours=-6))
    seen = {}
    for p in glob.glob(os.path.join(dirs, '**', '*.jsonl'), recursive=True):
        for l in open(p, encoding='utf-8', errors='replace'):
            if '"assistant"' not in l:
                continue
            try:
                r = json.loads(l)
            except ValueError:
                continue
            msg = r.get('message') or {}
            u = msg.get('usage') or {}
            if r.get('type') != 'assistant' or not u or not r.get('timestamp'):
                continue
            key = msg.get('id') or r.get('requestId') or r.get('uuid')
            t = datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')).astimezone(tz).strftime('%Y-%m-%dT%H:%M:%S')
            new = (u.get('input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0) + (u.get('output_tokens') or 0)
            seen[key] = dict(t=t, total=new + (u.get('cache_read_input_tokens') or 0), new=new)
    return [m for m in seen.values() if not since or m['t'] >= since]


def report(sc, today, since=None, tok=None):
    pct = lambda v: '—' if v is None else f'{v * 100:.0f} %'
    mark = lambda b: '✅' if b else '❌'
    rows = ['| Platform | Submitted (≥ 50; Lever ≥ 30) | No Joey needed (≥ 95 %; Lever info) | Proof: e-mail ≤ 48 h or confirmation page (≥ 95 %) | Wrong answers (critical 0 · non-critical ≥ 95 % right) | '
            'Median runner time (≤ 300 s) | DeepSeek / app (≤ $0.01) | First dry-run clean (info) | Claude tokens / app, median direct (info) | Claude tokens / app, all-in (info) | Certified |', '|' + '---|' * 11]
    tok = tok or {}
    k = lambda v: '—' if v is None else (f'{v / 1e6:.1f} M' if v >= 1e6 else f'{v / 1e3:.0f} k')
    tk = lambda v: '—' if not v else f'{k(v[0])} (new {k(v[1])})'
    for name in sorted(sc, key=lambda k: -sc[k]['folders']):
        p = sc[name]
        cost = '—' if p['mean_ds_cost'] is None else f"${p['mean_ds_cost']:.4f}"
        nj = 'info' if (p.get('bar') or BAR)['no_joey'] is None else mark(p['no_joey_ok'])
        rows.append(f"| {name} | {p['submitted']} {mark(p['n_ok'])} | {pct(p['no_joey_rate'])} ({p['submitted'] - p['needed_joey']}/{p['submitted']}) {nj} | "
                    f"{pct(p['confirm_rate'])} ({p['confirmed']}/{p['submitted'] - p['pending']}: e-mail {p['by_email']}, page {p['by_page']}; {p['pending']} pending) {mark(p['confirm_ok'])} | "
                    f"critical {p['critical_wrong']} · non-critical {p['noncrit_wrong']}/{p['noncrit_answers']}"
                    f"{(' (%.1f %% right)' % (100 * p['noncrit_accuracy'])) if p.get('noncrit_accuracy') is not None else ''}"
                    f"{(' (re-cert %d/%d, critical wrong %d)' % (p['recert_submitted'], p['recert_need'], p['recert_wrong'])) if p.get('recert_need') else ''} {mark(p['wrong_ok'])} | {'not logged' if p['median_secs'] is None else f"{round(p['median_secs'])} s of {p['timed']}"} {mark(p['time_ok'])} | "
                    f"{cost} {mark(p['cost_ok'])} | "
                    f"{pct(p['first_clean_rate'])} of {p['folders']} | {tk((tok.get(name) or {}).get('direct_median'))} | "
                    f"{tk((tok.get(name) or {}).get('all_in_per_app'))} | {'**yes**' if p['certified'] else 'no'} |")
    return '\n'.join([f'# Platform scorecard — {today}' + (f' (folders run since {since})' if since else ''), '',
                      'Computed by `scripts/platform_scorecard.py` from results.jsonl, emails.jsonl, ds_usage.md and wrong_answers.jsonl.',
                      'Not scored (not in the files): Joey\'s hands-on minutes.',
                      'Claude tokens (info, no bar): from the Claude Code transcripts, attributed by time (`claude_tokens()`). "new" = input + cache writes + output; '
                      'the larger number also counts cache reads (the conversation re-read on every reply). Direct = replies while that application ran or waited for an answer; '
                      'all-in = direct + the day\'s overhead (batch picking, code fixes, docs) shared by number of applications run, divided by submitted.', ''] + rows
                     + [''] + [f'- {PLATFORM_NOTE[n]}' for n in sorted(sc) if n in PLATFORM_NOTE]
                     + ([''] + [f"Claude tokens per platform (window): " + ' · '.join(f"{n}: direct {tk(tok[n]['direct_sum'])}, overhead {tk(tok[n]['overhead'])}" for n in sorted(sc) if n in tok)
                               + f" · not allocated (days with no runs): {tk(tok.get('_unallocated'))}"] if tok else [])) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out'); ap.add_argument('--since', help=f'default {CERT_SINCE} (certification window); --all = every run')
    ap.add_argument('--all', action='store_true'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    today = date.today().isoformat()
    since = None if a.all else (a.since or CERT_SINCE)
    data = load(since=since)
    try:                                         # re-certification after wrong answers (Joey 2026-11-05: Greenhouse, 10 with 0 wrong)
        recert = json.load(open(jpaths.data('runner', 'recertify.json'), encoding='utf-8'))
    except (OSError, ValueError):
        recert = {}
    sc = score(*data[:5], today, data[5], recert=recert, field_counts=noncrit_counts(jpaths.data('runner', 'fields')))
    tok = claude_tokens(claude_msgs(since), data[0])
    if a.json:
        for n, q in tok.items():
            if n in sc: sc[n]['claude_tokens'] = q
    text = json.dumps(sc, indent=1) if a.json else report(sc, today, since, tok)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(text)
    print(text)


if __name__ == '__main__':
    main()
