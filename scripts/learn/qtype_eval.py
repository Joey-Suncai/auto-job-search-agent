#!/usr/bin/env python3
"""JSA-361 step 1 — measure, do not switch: can a model read a form question's type from a fixed list?

DeepSeek reads each question of the gold set (scripts/test_cases/qtype_gold.jsonl, built by qtype_gold.py) into a
reading from scripts/learn/qtype_schema.json — shape, subject, time, degree, topic, fact_key, negated, confidence. It
sees only the question, its options and the control type; never a fact about the user. The code then scores the
readings against the switch gate (Joey 2026-11-13, jsa-dev docs/dev-decisions.md):
  1. type-misread wrong answers: >= 80 % read right, the rest fall to "ask" (never another wrong reading);
  2. questions the audit judged right, critical: 0 new wrong;
  3. the same, non-critical: <= 1 % new wrong.
Nothing here answers a form: not imported by answer_rules.js or any runner. Spec: jsa-dev docs/specs/runner-qtype-reading.md.

v2 (2026-11-16): each question is read 3 times and the majority (>= --agree readings alike) is used, else it asks;
with --haiku a critical question is answered only when Claude Haiku's own reading matches (run it with the venv python,
which has the anthropic SDK; key: Keychain jobagent-anthropic).
Cache (per list version + prompt hash + model + effort + control type + label + options; the 3 raw readings and their
majority): the data home's data/runner/qtype_cache.jsonl (untracked — JSA-358 decides).
Cost: the API's token counts priced at DeepSeek's peak list price (an upper bound), plus the account balance before / after.

  python3 scripts/learn/qtype_eval.py [--limit N] [--reads 3] [--agree 2] [--haiku] [--report out.md] [--results out.jsonl]
"""
import argparse, concurrent.futures as cf, hashlib, json, os, sys, threading, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths  # noqa: E402

SCHEMA = json.load(open(os.path.join(HERE, 'qtype_schema.json')))
GOLD = os.path.join(ROOT, 'scripts', 'test_cases', 'qtype_gold.jsonl')
HOLDOUT = os.path.join(ROOT, 'scripts', 'test_cases', 'qtype_holdout.jsonl')   # held-out set: never tune the list on it
VERDICTS = os.path.join(ROOT, 'scripts', 'test_cases', 'qtype_gold_verdicts.json')   # Claude's verdict on each new wrong (rule 13)
NOT_WRONG = ('gold_stale', 'model_right', 'same_answer')
DS_URL = 'https://api.deepseek.com/chat/completions'
BAL_URL = 'https://api.deepseek.com/user/balance'
KEY_PATHS = [os.environ.get('DEEPSEEK_KEY_FILE', ''), os.path.expanduser('~/deepseek/api_key')]
MODEL = os.environ.get('CX_QTYPE_MODEL', 'deepseek-flash')
# USD per 1M tokens, peak hours (off-peak is half) — api-docs.deepseek.com/quick_start/pricing, read 2026-11-16
PRICE = {'deepseek-flash': {'hit': 0.006, 'miss': 0.30, 'out': 1.20},
         'deepseek-v4-pro': {'hit': 0.044, 'miss': 1.32, 'out': 3.96}}
FIELDS = ('shape', 'subject', 'time', 'degree', 'topic', 'fact_key', 'negated', 'confidence')
YES_WORDS, NO_WORDS = {'yes', 'y', 'true'}, {'no', 'n', 'false'}


def fact_keys():
    return [k for t in SCHEMA['topics'].values() for k in t]


KEYS = fact_keys()
TOPIC_OF = {k: t for t, ks in SCHEMA['topics'].items() for k in ks}
ABOUT_OTHERS = set(SCHEMA['about_others'])


# ---------- scoring (pure; spec: scripts/test_cases/qtype_eval_spec.md) ----------
def asks(r):
    """Does this reading mean "ask the user"?"""
    k = r.get('fact_key')
    if k in ('none', 'unknown', None, ''):
        return True
    if r.get('confidence') == 'low' or r.get('shape') in ('unclear', 'trap') or r.get('subject') == 'unclear':
        return True
    if k in ('spons_now', 'spons_future') and r.get('time') == 'none':
        return True                                        # no time word: Joey answers each one (Joey 2026-11-16, JSA-361)
    return r.get('subject') == 'other_person' and k not in ABOUT_OTHERS


def score_wrong(r, g):
    """A question the old rules answered wrong → 'right' / 'ask' / 'wrong'."""
    if asks(r):
        return 'right' if 'none' in g['keys'] else 'ask'
    ok = (r.get('fact_key') in g['keys'] and r.get('shape') in g['shape'] and r.get('subject') in g['subject']
          and (g.get('negated') is None or bool(r.get('negated')) == bool(g['negated']))
          and (g.get('degree') is None or r.get('degree') in g['degree']))
    return 'right' if ok else 'wrong'


def yes_word(a):
    a = str(a or '').strip().lower()
    return True if a in YES_WORDS else False if a in NO_WORDS else None


def norm(x):
    return str(x).strip().lower() if x is not None else None


def score_right(r, g, facts):
    """A question the audit judged right (gold key + right answer) → 'same' / 'ask' / 'new_wrong'."""
    if asks(r):
        return 'ask'
    k = r.get('fact_key')
    f = facts.get(k)
    if r.get('shape') == 'paragraph' and f is not None and 'yes' in f and 'text' not in f:
        return 'ask'
    if r.get('shape') == 'yes_no' and g.get('box') and f is not None and 'yes' not in f:
        return 'new_wrong'                                 # a yes / no in a value box (JSA-322)
    yw = yes_word(g.get('answer'))
    if yw is not None:
        if f is None or 'yes' not in f:
            return 'new_wrong'
        return 'same' if (bool(f['yes']) != bool(r.get('negated'))) == yw else 'new_wrong'
    if k == g['key']:
        return 'same'
    gf = facts.get(g['key'])
    if f is None or gf is None:
        return 'new_wrong'
    if 'text' not in f and 'yes' not in f:
        return 'new_wrong'
    return 'same' if norm(f.get('text')) == norm(gf.get('text')) and f.get('yes') == gf.get('yes') else 'new_wrong'


def why_wrong(r, g):
    """Which field of a wrong reading differs from the gold (for the report)."""
    if r.get('fact_key') not in g['keys']:
        return 'fact_key'
    if r.get('shape') not in g['shape']:
        return 'shape'
    if r.get('subject') not in g['subject']:
        return 'subject'
    if g.get('negated') is not None and bool(r.get('negated')) != bool(g['negated']):
        return 'negated'
    return 'degree'


# ---------- the reader ----------
def system_prompt():
    f = SCHEMA['fields']
    lines = ['You read ONE question from a job application form and classify it with a fixed list. You do not answer it.',
             'Read the whole label: the asking sentence decides; a preamble, examples or legal text around it do not.',
             'The person filling in the form is "the user". Use only values from the lists below.', '']
    for name in ('shape', 'subject', 'time', 'degree', 'confidence'):
        lines.append(name + ':')
        lines += ['  %s — %s' % (k, v) for k, v in f[name].items()]
    lines += ['negated: ' + f['negated'], '', 'topic and fact_key (fact_key must be one of the keys under its topic):']
    for t, ks in SCHEMA['topics'].items():
        lines.append('  topic ' + t + ':')
        lines += ['    %s — %s' % (k, v) for k, v in ks.items()]
    lines += ['  special fact_key values (topic: the closest topic, or "other"):']
    lines += ['    %s — %s' % (k, v) for k, v in SCHEMA['special_keys'].items()]
    lines += ['', 'Reply with JSON only: {"shape": "", "subject": "", "time": "", "degree": "", "topic": "", "fact_key": "", '
              '"negated": false, "confidence": "", "why": "<one short sentence>"}']
    return '\n'.join(lines)


SYSTEM = system_prompt()


def messages(item):
    opts = [str(o) for o in (item.get('options') or [])][:40]
    u = 'Question: %s\nControl type: %s\n' % (str(item['question']).strip()[:2000], item.get('type') or 'unknown')
    u += ('Options: ' + ' | '.join(opts) + (' | …' if len(item.get('options') or []) > 40 else '')) if opts else 'Options: (none — a box to fill)'
    return [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': u}]


def parse_reading(text):
    """Model reply → a reading with every field inside the list (anything else → unclear / unknown, i.e. ask)."""
    try:
        d = json.loads(text)
        if not isinstance(d, dict):
            raise ValueError
    except Exception:
        return {'shape': 'unclear', 'subject': 'unclear', 'time': 'none', 'degree': 'none', 'topic': 'other',
                'fact_key': 'unknown', 'negated': False, 'confidence': 'low', 'why': 'bad reply'}
    f = SCHEMA['fields']
    r = {}
    for name, bad in (('shape', 'unclear'), ('subject', 'unclear'), ('time', 'none'), ('degree', 'none'), ('confidence', 'low')):
        v = d.get(name)
        r[name] = v if v in f[name] else bad
    k = d.get('fact_key')
    r['fact_key'] = k if k in KEYS or k in SCHEMA['special_keys'] else 'unknown'
    t = d.get('topic')
    r['topic'] = t if t in SCHEMA['topics'] or t == 'other' else 'other'
    r['negated'] = d.get('negated') is True
    r['why'] = str(d.get('why') or '')[:200]
    return r


PROMPT_HASH = hashlib.sha256(SYSTEM.encode('utf-8')).hexdigest()[:12]   # an edited prompt is a new reading


def cache_key(item, model, effort=None, sample=0):
    """sample > 0 = an independent repeat run (new readings of the same questions, to measure run-to-run spread)."""
    raw = json.dumps([SCHEMA['version'], PROMPT_HASH, model, effort or '', item.get('type') or '', str(item['question']).strip(),
                      [str(o) for o in (item.get('options') or [])]] + ([sample] if sample else []), ensure_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]


def api_key():
    return next((open(p).read().strip() for p in KEY_PATHS if p and os.path.exists(p)), None)


def default_post(model, effort=None):
    key = api_key()
    if not key:
        raise SystemExit('no DeepSeek key (~/deepseek/api_key)')

    def post(body):
        if effort:
            body = dict(body, reasoning_effort=effort)
        req = urllib.request.Request(DS_URL, data=json.dumps(body).encode(), headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        return json.load(urllib.request.urlopen(req, timeout=180))
    return post


def load_cache(path):
    c = {}
    if path and os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            try:
                e = json.loads(line)
                c[e['k']] = e
            except Exception:
                continue
    return c


VOTE = ('fact_key', 'shape', 'negated', 'subject')      # the fields that decide the answer


def vote_of(r):
    return tuple(bool(r.get(f)) if f == 'negated' else r.get(f) for f in VOTE)


def majority(reads, agree=2):
    """N independent readings of one question → one reading: the reading that at least `agree` of them share (on
    fact_key, shape, negated, subject); none → a reading that asks (the readings disagree). JSA-361 v2: one run's
    reading changed on 10-12 % of questions, so a single reading is not trusted."""
    if not reads:
        return None
    groups = {}
    for r in reads:
        groups.setdefault(vote_of(r), []).append(r)
    best = max(groups.values(), key=len)
    if len(best) >= agree:
        return dict(best[0], votes='%d/%d' % (len(best), len(reads)))
    return dict(reads[0], confidence='low', votes='%d/%d' % (len(best), len(reads)),
                why='readings disagree: ' + ' | '.join('%s/%s' % (r.get('fact_key'), r.get('shape')) for r in reads))


FAIL = {'shape': 'unclear', 'subject': 'unclear', 'fact_key': 'unknown', 'confidence': 'low', 'why': 'API error', 'error': True}


def read_all(items, post, cache, cache_path, workers=8, model=MODEL, effort=None, reads=3, agree=2, sample=0):
    """Items → (readings aligned with items, usage of the calls made now). Each question is read `reads` times
    (independent calls); the cache line of a key holds all raw readings ('reads', 'raw') and their majority ('reading'),
    written once every read succeeded — a key with a failed read is not cached (the next run tries again)."""
    keys = [cache_key(it, model, effort, sample) for it in items]
    todo = {}
    for k, it in zip(keys, items):
        if len((cache.get(k) or {}).get('reads') or []) < reads and k not in todo:
            todo[k] = it
    use = {'calls': 0, 'errors': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 0}
    lock = threading.Lock()

    def one(k):
        body = {'model': model, 'temperature': 0, 'response_format': {'type': 'json_object'}, 'messages': messages(todo[k])}
        got = []
        for _ in range(reads):
            resp = None
            for _ in range(3):
                try:
                    resp = post(body)
                    text = resp['choices'][0]['message']['content']
                    break
                except Exception:
                    resp = None
            with lock:
                if resp is None:
                    use['errors'] += 1
                    return
                use['calls'] += 1
                for n in ('prompt_tokens', 'completion_tokens', 'prompt_cache_hit_tokens', 'prompt_cache_miss_tokens'):
                    use[n] += int((resp.get('usage') or {}).get(n) or 0)
            got.append((parse_reading(text), text[:600]))
        e = {'k': k, 'model': model, 'v': SCHEMA['version'], 'reads': [g[0] for g in got], 'raw': [g[1] for g in got],
             'reading': majority([g[0] for g in got], 2), 'at': datetime.now().isoformat(timespec='seconds')}
        with lock:
            cache[k] = e
            if cache_path:
                with open(cache_path, 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps(e, ensure_ascii=False) + '\n')

    with cf.ThreadPoolExecutor(max(1, workers)) as ex:
        list(ex.map(one, list(todo)))
    out = []
    for k in keys:
        e = cache.get(k)
        rs = (e or {}).get('reads') or ([e['reading']] if e and 'reading' in e else [])
        out.append(dict(majority(rs[:reads], agree)) if len(rs) >= reads else dict(FAIL))
    return out, use


# ---------- the Haiku re-read of critical questions (JSA-361 v2, Joey 2026-11-13: "关键题由 Claude Haiku 独立再读一遍") ----------
HAIKU = os.environ.get('CX_QTYPE_HAIKU', 'claude-haiku-5-5')
HAIKU_PRICE = {'in': 0.10, 'cache_read': 0.01, 'cache_write': 0.125, 'out': 0.50}   # USD per 1M tokens (prompts <= 100K)
SAME = ('fact_key', 'shape', 'negated')


def reading_schema():
    f = SCHEMA['fields']
    en = lambda name: {'type': 'string', 'enum': list(f[name])}
    props = {'shape': en('shape'), 'subject': en('subject'), 'time': en('time'), 'degree': en('degree'),
             'topic': {'type': 'string', 'enum': list(SCHEMA['topics']) + ['other']},
             'fact_key': {'type': 'string', 'enum': KEYS + list(SCHEMA['special_keys'])},
             'negated': {'type': 'boolean'}, 'confidence': en('confidence'), 'why': {'type': 'string'}}
    return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}


def anthropic_key():
    for svc, acct in (('jobagent-anthropic', 'jobagent'), ('jsa-anthropic', 'jobagent'), ('jobagent-anthropic', None), ('jsa-anthropic', None)):
        cmd = ['security', 'find-generic-password', '-s', svc] + (['-a', acct] if acct else []) + ['-w']
        r = __import__('subprocess').run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return None


def haiku_call(client):
    """item → (reading text, usage dict) through the Anthropic SDK; raises on API failure."""
    def call(item):
        m = messages(item)
        r = client.messages.create(model=HAIKU, max_tokens=1024,
                                   system=[{'type': 'text', 'text': m[0]['content'], 'cache_control': {'type': 'ephemeral'}}],
                                   output_config={'effort': 'medium', 'format': {'type': 'json_schema', 'schema': reading_schema()}},
                                   messages=[{'role': 'user', 'content': m[1]['content']}])
        if r.stop_reason == 'refusal':
            raise RuntimeError('refusal')
        u = r.usage
        text = next(b.text for b in r.content if b.type == 'text')
        return text, {'input': u.input_tokens or 0, 'cache_read': getattr(u, 'cache_read_input_tokens', 0) or 0,
                      'cache_write': getattr(u, 'cache_creation_input_tokens', 0) or 0, 'output': u.output_tokens or 0}
    return call


def haiku_all(items, call, cache, cache_path, workers=4, sample=0):
    """Critical items → (Haiku readings aligned with items, usage). One read per question, cached like DeepSeek's."""
    keys = [cache_key(it, HAIKU, None, sample) for it in items]
    todo = {k: it for k, it in zip(keys, items) if k not in cache}
    use = {'calls': 0, 'errors': 0, 'input': 0, 'cache_read': 0, 'cache_write': 0, 'output': 0}
    lock = threading.Lock()

    def one(k):
        try:
            text, u = call(todo[k])
        except Exception:
            with lock:
                use['errors'] += 1
            return
        e = {'k': k, 'model': HAIKU, 'v': SCHEMA['version'], 'reading': parse_reading(text), 'raw': text[:600],
             'at': datetime.now().isoformat(timespec='seconds')}
        with lock:
            use['calls'] += 1
            for n in ('input', 'cache_read', 'cache_write', 'output'):
                use[n] += u[n]
            cache[k] = e
            if cache_path:
                with open(cache_path, 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps(e, ensure_ascii=False) + '\n')

    with cf.ThreadPoolExecutor(max(1, workers)) as ex:
        list(ex.map(one, list(todo)))
    return [dict(cache[k]['reading']) if k in cache else dict(FAIL) for k in keys], use


YES_SHAPES = ('yes_no', 'choice', 'multi_choice', 'subscription', 'data_consent', 'attestation')


def answer_of(r, facts, prefer_pick=False):
    """The answer a reading leads to, by the user's facts (local only): yes / no, a text, a pick list, or — for a key
    with no stored value — the key itself. None when the reading asks. (spec: qtype_vote_answer_spec.md)"""
    if asks(r):
        return None
    k = r.get('fact_key')
    f = facts.get(k)
    key = ('key', k, r.get('shape'), bool(r.get('negated')))
    if f is None:
        return key
    if r.get('shape') in YES_SHAPES and 'yes' in f:
        return ('yes', bool(f['yes']) != bool(r.get('negated')))
    if prefer_pick and r.get('shape') in ('choice', 'multi_choice') and f.get('pick'):
        return ('pick', tuple(map(str, f['pick'])))      # shadow: a live option is matched by the fact's patterns, not its text
    if f.get('text') is not None:
        return ('text', norm(f['text']))
    if f.get('pick'):
        return ('pick', tuple(map(str, f['pick'])))
    return key


def with_haiku(ds, hk, facts=None):
    """A critical question is answered only when DeepSeek's majority and Haiku agree; else, or when either asks, it
    asks. facts None → agree = same fact_key, shape and negated; facts given → agree = the same answer (v2b)."""
    if asks(ds):
        return ds
    if hk.get('error'):
        return dict(ds, confidence='low', why='Haiku re-read failed', error=True)
    if facts is None:
        same = not asks(hk) and all((bool(ds.get(f)) if f == 'negated' else ds.get(f)) == (bool(hk.get(f)) if f == 'negated' else hk.get(f)) for f in SAME)
    else:
        a = answer_of(hk, facts)
        same = a is not None and a == answer_of(ds, facts)
    if not same:
        return dict(ds, confidence='low', why='Haiku reads it as %s/%s' % (hk.get('fact_key'), hk.get('shape')), haiku=hk.get('fact_key'))
    return dict(ds, haiku='same')


def haiku_cost(use):
    p = HAIKU_PRICE
    return (use.get('input', 0) * p['in'] + use.get('cache_read', 0) * p['cache_read'] + use.get('cache_write', 0) * p['cache_write']
            + use.get('output', 0) * p['out']) / 1e6


def cost_usd(use, model):
    p = PRICE.get(model, PRICE['deepseek-flash'])
    return (use.get('prompt_cache_hit_tokens', 0) * p['hit'] + use.get('prompt_cache_miss_tokens', 0) * p['miss']
            + use.get('completion_tokens', 0) * p['out']) / 1e6


def balance():
    key = api_key()
    try:
        req = urllib.request.Request(BAL_URL, headers={'Authorization': 'Bearer ' + key})
        b = json.load(urllib.request.urlopen(req, timeout=20))['balance_infos'][0]
        return float(b['total_balance']), b['currency']
    except Exception:
        return None, None


# ---------- facts (local only: to tell whether two fact keys give the same answer; never sent) ----------
def load_facts():
    try:
        a = json.load(open(paths.config('profile.json'), encoding='utf-8')).get('answers') or {}
    except OSError:
        return {}
    out = {}
    for k, v in a.items():
        if isinstance(v, dict):
            f = {}
            if isinstance(v.get('yes'), bool):
                f['yes'] = v['yes']
            if v.get('text') is not None:
                f['text'] = v['text']
            if v.get('pick'):
                f['pick'] = [str(x) for x in v['pick']]
            out[k] = f
        elif isinstance(v, (str, int, float)):
            out[k] = {'text': str(v)}
    return out


def right_id(folder, question):
    return 'r' + hashlib.sha1((folder + '|' + question).encode('utf-8')).hexdigest()[:12]


def load_answers():
    """{right-item id: 'Yes' / 'No'} — the audit's right answer when it is a bare yes / no (a fact: read locally, never
    committed with the gold set nor sent to the model)."""
    out = {}
    try:
        for line in open(paths.data('runner', 'audit', 'items.jsonl'), encoding='utf-8'):
            a = json.loads(line)
            yw = yes_word(a.get('answer'))
            if a.get('check') == 'right' and yw is not None:
                out[right_id(a['folder'], a['question'])] = 'Yes' if yw else 'No'
    except OSError:
        pass
    return out


def verdict_applies(v, r):
    """A verdict judged one reading: it counts only while the reading is the same (another model / prompt / list → judge again)."""
    seen = v.get('read') or {}
    return bool(seen) and r.get('fact_key') == seen.get('fact_key') and r.get('shape') == seen.get('shape') \
        and bool(r.get('negated')) == bool(seen.get('negated'))


# ---------- the run ----------
def pct(a, b):
    return '%.1f %%' % (100.0 * a / b) if b else '—'


def run(gold, readings, facts, verdicts=None, answers=None):
    """Score every item; a new wrong judged not wrong (verdicts, same reading) becomes 'judged_ok' (raw outcome kept in
    'raw'). answers = load_answers() (the right yes / no per right item)."""
    verdicts, answers = verdicts or {}, answers or {}
    rows = []
    for g, r in zip(gold, readings):
        if g['set'] == 'wrong':
            o = score_wrong(r, g['gold'])
        else:
            fx = dict(facts)
            g = dict(g, gold=dict(g['gold'], **({'answer': answers[g['id']]} if g['id'] in answers else {})))
            yw = yes_word(g['gold'].get('answer'))
            if g['gold']['key'] not in fx or (yw is not None and 'yes' not in fx[g['gold']['key']]):
                fx[g['gold']['key']] = {'yes': yw} if yw is not None else {'text': g['gold'].get('answer')}   # a rule with its own value: the right answer is its value
            box = not (g.get('options') or []) and (g.get('type') or 'text') in ('text', 'textarea')
            o = score_right(r, dict(g['gold'], box=box), fx)
        rows.append({'id': g['id'], 'set': g['set'], 'outcome': o, 'question': g['question'][:300], 'options': (g.get('options') or [])[:8],
                     'gold': g['gold'] if g['set'] == 'wrong' else {'key': g['gold']['key']}, 'reading': r,
                     'why': why_wrong(r, g['gold']) if o == 'wrong' else '', 'raw': o, 'error': bool(r.get('error'))})
        v = next((v for v in verdicts.get(g['id']) or [] if verdict_applies(v, r)), None)   # the verdict on THIS reading
        if o == 'new_wrong' and v and v['verdict'] in NOT_WRONG:
            rows[-1].update(outcome='judged_ok', verdict=v['verdict'], reason=v['reason'])
    return rows


def summary(rows):
    s = {}
    for x in rows:
        s.setdefault(x['set'], {}).setdefault(x['outcome'], 0)
        s[x['set']][x['outcome']] += 1
    return s


def report(rows, use, model, bal0, bal1, cur, hk_use=None, setup=''):
    s = summary(rows)
    w, rc, rn = s.get('wrong', {}), s.get('right_critical', {}), s.get('right_noncritical', {})
    nw, nc, nn = sum(w.values()), sum(rc.values()), sum(rn.values())
    g1 = nw and w.get('right', 0) / nw >= 0.8 and not w.get('wrong', 0)
    g2 = rc.get('new_wrong', 0) == 0
    g3 = nn and rn.get('new_wrong', 0) / nn <= 0.01
    errs = use.get('errors', 0) + (hk_use or {}).get('errors', 0) + sum(1 for x in rows if x.get('error'))
    if errs:                                           # a reading that failed is not a reading: the gates are not met
        g1 = g2 = g3 = False
    rawc, rawn = rc.get('new_wrong', 0) + rc.get('judged_ok', 0), rn.get('new_wrong', 0) + rn.get('judged_ok', 0)
    L = ['# JSA-361 question-type reading — measurement (%s, %s, list v%s%s)' % (datetime.now().strftime('%Y-%m-%d %H:%M'), model, SCHEMA['version'], (', ' + setup) if setup else ''), '',
         '| Gate | Need | Got | Pass |', '|---|---|---|---|',
         '| 1 type-misread wrong answers read right | ≥ 80 %%, rest → ask | %d / %d right (%s) · ask %d · wrong %d | %s |' % (w.get('right', 0), nw, pct(w.get('right', 0), nw), w.get('ask', 0), w.get('wrong', 0), 'yes' if g1 else 'no'),
         '| 2 right critical: new wrong | 0 | %d / %d judged (raw %d) · ask %d = %s | %s |' % (rc.get('new_wrong', 0), nc, rawc, rc.get('ask', 0), pct(rc.get('ask', 0), nc), 'yes' if g2 else 'no'),
         '| 3 right non-critical: new wrong | ≤ 1 %% | %d / %d = %s judged (raw %d = %s) · ask %d = %s | %s |' % (rn.get('new_wrong', 0), nn, pct(rn.get('new_wrong', 0), nn), rawn, pct(rawn, nn), rn.get('ask', 0), pct(rn.get('ask', 0), nn), 'yes' if g3 else 'no'),
         '', 'Gate overall: **%s**' % ('pass' if g1 and g2 and g3 else 'INCOMPLETE — %d items without a reading (API errors); run again' % errs if errs else 'not met'),
         'Judged = after Claude\'s verdict on each raw new wrong (scripts/test_cases/qtype_gold_verdicts.json); an unjudged new wrong counts as wrong.', '']
    usd = cost_usd(use, model)
    L += ['## Cost', '', 'Calls %d (errors %d) · prompt %d tokens (cache hit %d, miss %d) · output %d → ≈ $%.4f at peak list price (off-peak half).'
          % (use['calls'], use['errors'], use['prompt_tokens'], use['prompt_cache_hit_tokens'], use['prompt_cache_miss_tokens'], use['completion_tokens'], usd)]
    if hk_use is not None:
        L.append('Haiku (%s): calls %d (errors %d) · input %d, cache read %d, cache write %d · output %d → ≈ $%.4f.'
                 % (HAIKU, hk_use['calls'], hk_use['errors'], hk_use['input'], hk_use['cache_read'], hk_use['cache_write'], hk_use['output'], haiku_cost(hk_use)))
    if bal0 is not None and bal1 is not None:
        L.append('Account balance %.2f → %.2f %s (Δ %.2f %s; other sessions using the key at the same time count too).' % (bal0, bal1, cur, bal0 - bal1, cur))
    L += ['', '## Wrong readings by field (set 1)', '']
    byf = {}
    for x in rows:
        if x['outcome'] == 'wrong':
            byf.setdefault(x['why'], []).append(x)
    for f, xs in sorted(byf.items(), key=lambda kv: -len(kv[1])):
        L.append('- **%s** (%d)' % (f, len(xs)))
        L += ['  - %s → read %s / %s / %s%s (gold %s)' % (x['question'][:110], x['reading'].get('fact_key'), x['reading'].get('shape'), x['reading'].get('subject'),
                                                       ' negated' if x['reading'].get('negated') else '', '/'.join(x['gold']['keys'])) for x in xs]
    jv = {}
    for x in rows:
        if x['outcome'] == 'judged_ok':
            jv[x['verdict']] = jv.get(x['verdict'], 0) + 1
    L += ['', 'Raw new wrongs judged not wrong: ' + (', '.join('%s %d' % kv for kv in sorted(jv.items())) or 'none'), '']
    L += ['', '## Set 1 → ask', '']
    L += ['- %s → %s / %s / %s (gold %s)' % (x['question'][:110], x['reading'].get('fact_key'), x['reading'].get('shape'), x['reading'].get('confidence'), '/'.join(x['gold']['keys']))
          for x in rows if x['set'] == 'wrong' and x['outcome'] == 'ask']
    for st in ('right_critical', 'right_noncritical'):
        L += ['', '## New wrong (judged real or not judged) — %s' % st, '']
        pairs = {}
        for x in rows:
            if x['set'] == st and x['outcome'] == 'new_wrong':
                pairs.setdefault((x['gold']['key'], x['reading'].get('fact_key')), []).append(x)
        for (gk, rk), xs in sorted(pairs.items(), key=lambda kv: -len(kv[1])):
            L.append('- gold %s → read %s (%d): %s' % (gk, rk, len(xs), ' ‖ '.join('%s%s' % (x['question'][:90], ' [negated]' if x['reading'].get('negated') else '') for x in xs[:3])))
    return '\n'.join(L) + '\n', g1 and g2 and g3


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--gold', default=GOLD)
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--effort', default=None, help='reasoning_effort (low / high / max); default = the API default')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--cache', default=paths.data('runner', 'qtype_cache.jsonl'))
    ap.add_argument('--verdicts', default=VERDICTS, help='Claude\'s verdicts on new wrongs; "" = raw only')
    ap.add_argument('--reads', type=int, default=3, help='independent DeepSeek readings per question (majority vote)')
    ap.add_argument('--agree', type=int, default=2, help='how many readings must agree (2 = majority of 3, 3 = all)')
    ap.add_argument('--haiku-by', choices=('key', 'answer'), default='key',
                    help='Haiku agrees with DeepSeek when the key / shape / negated match (key) or when both lead to the same answer (answer)')
    ap.add_argument('--sample', type=int, default=0, help='0 = the cached readings; 1, 2 … = an independent repeat run')
    ap.add_argument('--haiku', action='store_true', help='critical questions: answer only when Haiku reads them the same')
    ap.add_argument('--report', default='')
    ap.add_argument('--results', default='')
    a = ap.parse_args(argv)
    gold = [json.loads(x) for x in open(a.gold, encoding='utf-8')]
    if a.limit:
        gold = gold[:a.limit]
    bal0, cur = balance()
    cache = load_cache(a.cache)
    readings, use = read_all(gold, default_post(a.model, a.effort), cache, a.cache, a.workers, a.model, a.effort, a.reads, a.agree, a.sample)
    hk_use = None
    if a.haiku:
        crit = [i for i, g in enumerate(gold) if g.get('cls') == 'critical']
        key = anthropic_key()
        if not key:
            raise SystemExit('no Anthropic key in the Keychain (jobagent-anthropic / jsa-anthropic)')
        import anthropic
        hk, hk_use = haiku_all([gold[i] for i in crit], haiku_call(anthropic.Anthropic(api_key=key, max_retries=3)), cache, a.cache, sample=a.sample)
        hf = load_facts() if a.haiku_by == 'answer' else None
        for i, h in zip(crit, hk):
            readings[i] = with_haiku(readings[i], h, hf)
    bal1, _ = balance()
    verdicts = json.load(open(a.verdicts, encoding='utf-8'))['verdicts'] if a.verdicts and os.path.exists(a.verdicts) else {}
    rows = run(gold, readings, load_facts(), verdicts, load_answers())
    setup = '%d reads, %d must agree%s' % (a.reads, a.agree, (', + Haiku on critical (agree by %s)' % a.haiku_by) if a.haiku else '')
    text, ok = report(rows, use, a.model, bal0, bal1, cur, hk_use, setup)
    if a.report:
        open(a.report, 'w', encoding='utf-8').write(text)
    if a.results:
        with open(a.results, 'w', encoding='utf-8') as fh:
            for x in rows:
                fh.write(json.dumps(x, ensure_ascii=False) + '\n')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
