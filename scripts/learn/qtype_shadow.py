#!/usr/bin/env python3
"""JSA-361 shadow run (Joey 2026-11-16): the question-type layer reads every question the runners filled, beside the
live rules, and logs one line per question — it changes no answer and is never in a run's way.

When: runner_common writes a run's fields.jsonl lines, then starts this script as a detached process (start_shadow);
it reads the corpus lines added since its watermark (data/runner/qtype_shadow_state.json). A first start only sets the
watermark (nothing old is read); --since YYYY-MM-DD reads back from a date. One process at a time (a lock file); any
error goes to data/runner/qtype_shadow.log. CX_QTYPE_SHADOW=0 turns it off.

The layer: list v3, DeepSeek read 3 times (majority), critical questions (field_class) re-read by Claude Haiku — both
agree when they lead to the same answer by the user's facts, else the layer asks. The layer's answer is compared with
the live planned answer:
  agree · differ · layer_asks (live answered, the layer would ask) · live_asks (the layer would answer) · both_ask ·
  cannot_compare (the layer's fact has no stored value — the rule computes it)
Output: data/runner/qtype_shadow.jsonl, one line per question.

  python3 scripts/learn/qtype_shadow.py            # process new corpus lines (what the runner starts)
  python3 scripts/learn/qtype_shadow.py --since 2026-11-16 [--limit 50]
  python3 scripts/learn/qtype_shadow.py --report [--days 7]   # critical disagreements per day
"""
import argparse, fcntl, glob, json, os, re, subprocess, sys, traceback
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'config'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import paths  # noqa: E402
import qtype_eval as Q  # noqa: E402

SKIP_TYPES = {'account', 'file', 'education'}
SKIP_SOURCE = re.compile(r'^(account|resume|page|wd_profile|wd_answered:(Education|Work Experience|Languages|Your Experience))')
YES_RX = re.compile(r"^\s*(yes|y|true|checked|i (am|do|will|have|agree|consent|accept|acknowledge|understand))\b", re.I)
NO_RX = re.compile(r"^\s*(no|n|false|unchecked|not\b|i (am not|do not|don't|will not|won't|have not|haven't|decline))\b", re.I)


def out_path():
    return paths.data('runner', 'qtype_shadow.jsonl')


def js_rx(p):
    """'/^no\\b/i' (a profile pick pattern) → a Python regex; a plain string → a literal, case-insensitive."""
    m = re.match(r'^/(.*)/([a-z]*)$', str(p))
    if not m:
        return re.compile(re.escape(str(p)), re.I)
    return re.compile(m.group(1), re.I if 'i' in m.group(2) else 0)


def yes_of(s):
    if NO_RX.search(s):
        return False
    if YES_RX.search(s):
        return True
    return None


def compare(ans, live):
    """Pure (tested). The layer's answer (Q.answer_of) vs the live planned answer → kind."""
    s = str(live if live is not None else '').strip()
    if ans is None:
        return 'layer_asks' if s else 'both_ask'
    if not s:
        return 'live_asks'
    kind = ans[0]
    if kind == 'yes':
        y = yes_of(s)
        return 'cannot_compare' if y is None else ('agree' if y == ans[1] else 'differ')
    if kind == 'text':
        return 'agree' if Q.norm(s).rstrip('.') == str(ans[1]).rstrip('.') else 'differ'
    if kind == 'pick':
        try:
            return 'agree' if any(js_rx(p).search(s) for p in ans[1]) else 'differ'
        except re.error:
            return 'cannot_compare'
    return 'cannot_compare'


def show(ans):
    if ans is None:
        return '(ask)'
    if ans[0] == 'yes':
        return 'Yes' if ans[1] else 'No'
    if ans[0] in ('text',):
        return ans[1]
    if ans[0] == 'pick':
        return 'pick ' + ' | '.join(ans[1][:2])
    return '(%s: computed by the rule)' % ans[1]


def critical(label):
    try:
        import field_class
        return field_class.field_class(label)[0] == 'critical'
    except Exception:
        return False


def wanted(r):
    if not str(r.get('question') or '').strip() or r.get('type') in SKIP_TYPES:
        return False
    return not SKIP_SOURCE.search(str(r.get('source') or ''))


def new_lines(state, since=None):
    """Corpus lines added since the watermark (or since a date) → (records, new state)."""
    recs, st = [], dict(state)
    first = not state.get('_init')
    for f in sorted(glob.glob(paths.data('runner', 'fields', '*.jsonl'))):
        name = os.path.basename(f)
        if since is None:
            if first:                                      # first start: from now on only
                st[name] = os.path.getsize(f)
                continue
            start = st.get(name, 0)                        # a new month file: from its start
        else:
            start = 0
        if start > os.path.getsize(f):
            start = 0                                      # the file was truncated / rewritten: read it again from its start
        with open(f, 'rb') as fh:                         # binary: byte offsets
            fh.seek(start)
            data = fh.read()
        end = data.rfind(b'\n') + 1                       # only complete lines: a line the runner is still writing waits for the next start
        for line in data[:end].splitlines():
            try:
                r = json.loads(line.decode('utf-8'))
            except Exception:
                continue
            if since is not None and str(r.get('at', ''))[:10] < since:
                continue
            recs.append(r)
        st[name] = start + end
    st['_init'] = True
    return recs, st


def process(recs, cache_path=None, haiku=True, log=print):
    """Records → shadow lines (also returns usage). DeepSeek majority for all; Haiku on critical questions."""
    items = [{'question': r['question'], 'options': r.get('options') or [], 'type': r.get('type') or ''} for r in recs]
    if not items:
        return [], {}
    cache_path = cache_path or paths.data('runner', 'qtype_cache.jsonl')
    cache = Q.load_cache(cache_path)
    reads, use = Q.read_all(items, Q.default_post(Q.MODEL), cache, cache_path, 8, Q.MODEL, None, 3, 2)
    crit = [i for i, r in enumerate(recs) if critical(r['question'])]
    hk_use = {}
    facts = Q.load_facts()
    if crit and haiku:
        key = Q.anthropic_key()
        try:
            import anthropic
        except ImportError:
            anthropic = None
        if key and anthropic:
            hk, hk_use = Q.haiku_all([items[i] for i in crit], Q.haiku_call(anthropic.Anthropic(api_key=key, max_retries=3)), cache, cache_path)
            for i, h in zip(crit, hk):
                reads[i] = Q.with_haiku(reads[i], h, facts)
        else:
            for i in crit:                                 # no Haiku → a critical question is not answered by the layer
                reads[i] = dict(reads[i], confidence='low', why='Haiku unavailable')
            log('qtype_shadow: Haiku unavailable (key or SDK) — critical questions count as layer_asks')
    out = []
    cs = set(crit)
    for i, (r, rd) in enumerate(zip(recs, reads)):
        ans = Q.answer_of(rd, facts, prefer_pick=True)
        out.append({'at': r.get('at'), 'shadow_at': datetime.now().isoformat(timespec='seconds'), 'run_id': r.get('run_id'),
                    'folder': r.get('folder'), 'ats': r.get('ats'), 'key': Q.cache_key(items[i], Q.MODEL), 'question': r['question'][:500],
                    'cls': 'critical' if i in cs else 'non-critical', 'live': r.get('planned'), 'live_source': r.get('source'),
                    'reading': {k: rd.get(k) for k in ('fact_key', 'shape', 'negated', 'subject', 'time', 'confidence', 'votes', 'haiku', 'why')},
                    'layer_answer': show(ans), 'kind': compare(ans, r.get('planned')), 'list': Q.SCHEMA['version']})
    out_use = dict(use, haiku=hk_use, usd=round(Q.cost_usd(use, Q.MODEL) + (Q.haiku_cost(hk_use) if hk_use else 0), 4))
    return out, out_use


def state_path():
    return paths.data('runner', 'qtype_shadow_state.json')


def load_state():
    """The watermark; a missing or torn file → {} (a fresh start: from now on)."""
    try:
        st = json.load(open(state_path()))
        return st if isinstance(st, dict) else {}
    except Exception:
        return {}


def save_state(st):
    tmp = state_path() + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(st, fh)
    os.replace(tmp, state_path())                         # atomic: a crash never leaves a torn file


def run(since=None, limit=0, log=print):
    if os.environ.get('CX_QTYPE_SHADOW') == '0':
        return 0
    lock = open(paths.data('runner', 'qtype_shadow.lock'), 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0                                           # another shadow process is reading: these lines wait for the next start
    state = load_state()
    recs, st = new_lines(state, since)
    recs = [r for r in recs if wanted(r)]
    if limit:
        recs = recs[-limit:]
    lines, use = process(recs, log=log)
    with open(out_path(), 'a', encoding='utf-8') as fh:
        for x in lines:
            fh.write(json.dumps(x, ensure_ascii=False) + '\n')
    if since is None and not limit:                        # --since / --limit are manual reads: the watermark stays
        save_state(st)
    log('qtype_shadow: %d question(s) · DeepSeek %d calls · ≈ $%.4f' % (len(lines), use.get('calls', 0), use.get('usd', 0)) if lines else 'qtype_shadow: nothing new')
    return len(lines)


def report(days=7, path=None):
    """Critical disagreements per day (plain text)."""
    path = path or out_path()
    rows = [json.loads(x) for x in open(path, encoding='utf-8')] if os.path.exists(path) else []
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    rows = [r for r in rows if str(r.get('at', ''))[:10] >= since]
    L = ['# qtype shadow — last %d days (%d questions)' % (days, len(rows)), '',
         '| day | questions | critical | agree | differ (critical) | layer asks (critical) | live asks | cannot compare |', '|---|---|---|---|---|---|---|---|']
    byday = {}
    for r in rows:
        byday.setdefault(str(r.get('at', ''))[:10], []).append(r)
    for d in sorted(byday):
        xs = byday[d]
        c = lambda k, crit=None: sum(1 for x in xs if x['kind'] == k and (crit is None or x['cls'] == 'critical'))
        L.append('| %s | %d | %d | %d | %d (%d) | %d (%d) | %d | %d |' % (d, len(xs), sum(1 for x in xs if x['cls'] == 'critical'), c('agree'),
                 c('differ'), c('differ', True), c('layer_asks'), c('layer_asks', True), c('live_asks'), c('cannot_compare')))
    L += ['', '## Critical disagreements (layer answer ≠ live answer)', '']
    for r in rows:
        if r['cls'] == 'critical' and r['kind'] == 'differ':
            L.append('- %s · %s · %s — live %r (%s) · layer %r (%s/%s%s)' % (str(r.get('at', ''))[:10], r.get('folder'), r['question'][:100],
                     r.get('live'), r.get('live_source'), r.get('layer_answer'), r['reading'].get('fact_key'), r['reading'].get('shape'),
                     ' negated' if r['reading'].get('negated') else ''))
    return '\n'.join(L) + '\n'


def start_shadow(data_dir):
    """For runner_common: start this script detached after a run wrote its fields lines. Never raises; does nothing in
    tests (JSA_NO_PUSH / JSA_TEST_HOME), outside the data home, or with CX_QTYPE_SHADOW=0."""
    try:
        if os.environ.get('CX_QTYPE_SHADOW') == '0' or os.environ.get('JSA_NO_PUSH') or os.environ.get('JSA_TEST_HOME'):
            return False
        if os.path.realpath(data_dir) != os.path.realpath(paths.data('runner')):
            return False
        venv = os.path.expanduser('~/.job-agent-venv/bin/python')     # it has the anthropic SDK (Haiku)
        py = venv if os.path.exists(venv) else sys.executable
        logf = open(paths.data('runner', 'qtype_shadow.log'), 'a')
        subprocess.Popen([py, os.path.abspath(__file__)], stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
                         start_new_session=True, cwd=ROOT)
        return True
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--since', default=None, help='YYYY-MM-DD: read the corpus back from this date (the watermark is kept)')
    ap.add_argument('--limit', type=int, default=0, help='only the last N questions')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--days', type=int, default=7)
    a = ap.parse_args(argv)
    if a.report:
        print(report(a.days))
        return 0
    try:
        run(a.since, a.limit, log=lambda m: print(datetime.now().isoformat(timespec='seconds'), m, flush=True))
    except Exception:
        print(datetime.now().isoformat(timespec='seconds'), 'qtype_shadow failed:', traceback.format_exc(limit=3), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
