#!/usr/bin/env python3
"""Whole-question read of rule-answered critical questions (JSA-288, Joey 2026-11-10: 「关键题整句复读」).

answer_rules.js answers by regex keywords, so it can miss what the whole sentence means: tense ("pursuing or have
completed"), negation, which degree or employer is meant, which sentence after a notice is the real question
(a Workday employer 11-10: "highest level of education you are pursuing or have completed?" → highest_ed = Bachelor).
Here DeepSeek reads every rule-answered critical question on its own — the whole question, its options and the
candidate's facts — WITHOUT seeing the rule's answer. Same answer → kept (`whole_read: agree`); a different answer, no
answer (UNSURE) or an API error → the question is stopped and goes to Joey. The model never supplies an answer.

Which questions (select): status ok, answered by a rule (or by a saved qa entry matched by its regex — a saved answer for
EXACTLY this question is Joey's own and is not re-read), and scripts/field_class.py says critical in the groups
work_auth, education, record, experience. Not re-read: contact and EEO (literal facts, judged by canon.py in code; their
facts are never sent to a model, JSA-202), links (LinkedIn / GitHub), leave-empty answers.

Cache: per prompt (question + options + facts + model) in the data home data/runner/whole_read_cache.jsonl — a question
seen once is not asked again until the facts change. An error is not cached.

Block boxes (JSA-294): an education / work block box ("Degree", "From", "Overall Result (GPA)", "Job Title") is judged
by code against the entry of its block (block_check.py) before any model call — ok / bad decided there, a box it cannot
judge goes to the model with its entry in the label. Items carry `pos` (page order) so the blocks can be found.

    echo '[{"key", "label", "options", "type", "value", "rule", "pos", "context": [labels just before]}]' | python3 whole_read.py
        → {key: {"agree": bool, "model": str | null, "why": str, "cached": bool}}   (only the selected keys)
    python3 whole_read.py --select < items.json → [keys it would read]   (the bridge's fallback when a read fails)
On in live runs (CX_SECOND_OPINION=1, which every runner sets, or CX_WHOLE_READ=1); CX_WHOLE_READ=0 switches it off;
never with JSA_NO_PUSH / CX_DATA (tests, replay); off → {} (nothing changes). Replay over the submitted corpus: scripts/whole_read_replay.py.
"""
import datetime, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts')); sys.path.insert(0, os.path.join(ROOT, 'config'))
import second_opinion as SO  # noqa: E402

GROUPS = {'work_auth', 'education', 'record', 'experience'}
SKIP_RULES = re.compile(r'^(linkedin|website|full_name|first_name|last_name|email|phone|address|city|state|zip|how_heard\w*|sms)$')
SENSITIVE = re.compile(r'\bEEO\b|gender|\brace\b|ethnic|hispanic|veteran|disab|orientation|transgender|pronoun|'
                       r'date of birth|\bage range\b', re.I)
PROMPT_V = 'w1'
CONFIRM_MODEL = os.environ.get('CX_WR_CONFIRM_MODEL', 'deepseek-v4-pro')   # the second, stronger read of a disagreement


def enabled(env=None):
    """Pure (tested). On in live runs: the runners' CX_SECOND_OPINION=1 (or CX_WHOLE_READ=1); CX_WHOLE_READ=0 = off;
    never with JSA_NO_PUSH / CX_DATA (tests, replay)."""
    env = os.environ if env is None else env
    if env.get('CX_WHOLE_READ') == '0' or env.get('JSA_NO_PUSH') or env.get('CX_DATA'):
        return False
    return env.get('CX_WHOLE_READ') == '1' or env.get('CX_SECOND_OPINION') == '1'


def qa_norm(s):
    """= answer_rules qaNorm."""
    s = str(s or '').lower().replace('‘', "'").replace('’', "'")
    s = re.sub(r'\(?\brequired\b\)?|\*', ' ', s)
    return re.sub(r"[^a-z0-9']+", ' ', s).strip()


def select(items, qa=None, classify=None):
    """Pure (tested). The items to re-read. items = [{key, label, options, type, value, rule}]; qa = profile qa list
    (qa:N = entry N, 1-based); classify = field_class (injectable)."""
    if classify is None:
        from field_class import field_class as classify
    out = []
    for it in items or []:
        rule, v = str(it.get('rule') or ''), it.get('value')
        if not rule or SKIP_RULES.match(rule) or v is None or v == '' or v == [] or it.get('leave'):
            continue
        if str(it.get('type') or '').lower() in ('file', 'hidden', 'password'):
            continue
        sv = ' | '.join(map(str, v)) if isinstance(v, list) else str(v)
        if re.match(r'^\s*https?://', sv) or len(sv) > 300:
            continue                                         # a link, or an essay (JSA-288b: not a fact answer; letters have their own checks)
        m = re.match(r'^qa:(\d+)$', rule)
        if m and qa:
            n = int(m.group(1))
            e = qa[n - 1] if 0 < n <= len(qa) else None
            if e and e.get('q') and qa_norm(e['q']) == qa_norm(it.get('label')):
                continue                                     # Joey's own answer for exactly this question
        cl, g = classify(it.get('label') or '')
        if cl == 'critical' and g in GROUPS:
            out.append(dict(it, group=g))
    return out


def facts(prof, saved=None, today=None):
    """The candidate facts the model reads: confirmed form answers + education (candidate-profile.md via
    ladder.saved_facts, contact stripped), minus EEO / self-ID; the conviction fact; the dated education entries; today."""
    if saved is None:
        import ladder
        saved = ladder.saved_facts()
    lines = [l for l in saved if not SENSITIVE.search(l)]
    for e in prof.get('education') or []:
        lines.append('Education entry: %s, %s (%s), %s – %s%s' % (e.get('school'), e.get('degree'), e.get('level'), e.get('start', '?'),
                     e.get('end', '?'), ' — CURRENT, in progress, not yet completed' if e.get('current') else ' — completed'))
    c = ((prof.get('answers') or {}).get('conviction') or {})
    if c.get('yes') is not None:
        lines.append('Ever convicted of a crime, felony or misdemeanor, or pleaded guilty: ' + ('Yes' if c['yes'] else 'No'))
    emp = [e if isinstance(e, str) else e.get('name') for e in prof.get('employers') or []]
    if [e for e in emp if e]:
        lines.append('Past employers (internships, both ended; no current employer, a full-time student): ' + '; '.join(e for e in emp if e))
    for q in prof.get('qa') or []:                          # his own saved answers (= audit_sample.facts_text), not the match patterns
        if isinstance(q, dict) and q.get('q') and not q.get('retired') and not SENSITIVE.search(q['q']):
            a = 'Yes' if q.get('yes') is True else 'No' if q.get('yes') is False else q.get('text')
            if a and not re.match(r'^[/^]', str(a)):
                lines.append('Saved form answer — %s → %s' % (norm_ws(q['q'])[:200], str(a)[:160]))
    lines.append('Today is %s.' % (today or datetime.date.today().isoformat()))
    return '\n'.join(dict.fromkeys(lines))


def norm_ws(x):
    return ' '.join(str(x or '').split())


BLOCK_START = re.compile(r'^\s*(school( name)?|university|college|institution|company( name)?|employer( name)?|name of (school|employer))\s*[:*]*\s*$', re.I)


def block_context(label, context, has_options=False):
    """Pure (tested, JSA-292). The context the model sees: a field that STARTS a block (School, Company …) has none — the labels
    before it belong to the previous block (a Greenhouse employer: "School" after a High School question was read as the high school);
    otherwise the context is cut at the last block starter in it."""
    ctx = [c for c in context or [] if str(c).strip()]
    if BLOCK_START.match(str(label or '')):
        return ctx[-1:] if has_options else []
    for i in range(len(ctx) - 1, -1, -1):
        if BLOCK_START.match(str(ctx[i])):
            return ctx[i:]
    return ctx


def prompt(item, fact_text):
    opts = item.get('options') or []
    ctx = block_context(item.get('label'), item.get('context'), bool(opts))[-4:]
    return ('You answer ONE job-application form question for a candidate, using ONLY the candidate facts below.\n'
            'Read the WHOLE question before answering: which sentence actually asks (a notice before it only explains); '
            'tense (now / ever / completed / in progress / after graduation / during the internship); negation ("without", '
            '"not"); which degree, school or employer it means (undergraduate vs graduate, current vs past, any employer vs '
            'this one); what exactly is asked (a yes / no, a level, a name, a date).\n\n'
            'Candidate facts:\n' + fact_text + '\n\n' +
            ('Form context — the questions just before this one (they tell which block it belongs to, e.g. an education '
             'entry): ' + ' / '.join(str(c)[:80] for c in ctx) + '\n' if ctx else '') +
            'Question: ' + str(item.get('label') or '') + '\n' +
            ('Options (answer with one of them exactly; several only if the question says select all): '
             + ' | '.join(map(str, opts[:60])) + '\n' if opts else 'No options: answer with the short value you would type.\n') +
            'A fact that gives an ordered list ("first that the list offers: A → B → …") with no options shown: answer A.\n'
            'If the facts do not decide it, answer UNSURE.\n'
            'Reply as JSON: {"answer": "<option(s) separated by | , or short value, or UNSURE>", "reason": "<one sentence>"}')


def meaning_prompt(item, a, b):
    return ('Two answers were written for the same job-application form question. Would both be correct, consistent '
            'answers to THIS question?\n'
            'SAME: they do not contradict each other and each answers what the question asks. Extra detail, a longer or '
            'shorter wording, or one saying "no minor / none" for a part the other leaves out does NOT make them different.\n'
            'DIFFERENT: they contradict (yes vs no, different degree, school, employer, date, number, option), or one does '
            'not answer what is asked (a bare Yes to a "what / which / please describe" question, a name to a yes / no '
            'question), or one leaves out the very thing the question asks for.\n\n'
            'Question: ' + str(item.get('label') or '') + '\nAnswer A: ' + str(a) + '\nAnswer B: ' + str(b) + '\n'
            'Reply as JSON: {"answer": "SAME" or "DIFFERENT", "reason": "<one sentence>"}')


# ----------------------------------------------------------------------------- comparing answers
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def ym(s):
    """Pure (tested). A date-like answer → (year, month | None); None when it is not a date."""
    s = str(s or '').strip().lower()
    m = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', s)
    if m:
        return int(m.group(3)), int(m.group(1))
    m = re.fullmatch(r'(\d{4})-(\d{1,2})(-\d{1,2})?', s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r'(\d{1,2})[/.-](\d{4})', s)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.fullmatch(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2},?\s+)?(\d{4})', s)
    if m:
        return int(m.group(3)), MONTHS[m.group(1)]
    m = re.fullmatch(r'(\d{4})', s)
    if m:
        return int(m.group(1)), None
    return None


def month(s):
    """Pure (tested). A bare month answer ('September', 'Sep', '09', '9') → 1..12; else None."""
    s = str(s or '').strip().lower().rstrip('.')
    if re.fullmatch(r'0?[1-9]|1[0-2]', s):
        return int(s)
    m = re.fullmatch(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*', s)
    return MONTHS[m.group(1)] if m else None


GPA_Q = re.compile(r'\bgpa\b|grade point|cumulative (average|result)|overall result', re.I)
GPA_NONE = re.compile(r'^(n/?a|none|not applicable|other|no gpa( yet)?|not yet available|-)$', re.I)


def gpa_either(label, a, b):
    """Pure (tested). Joey 2026-11-10 (「累计 GPA 选填 3.60 或者填没有，其实都可以」): on a GPA question that names no
    major / undergraduate-only scale, the UIUC cumulative 3.60 and none / N/A / Other are both right — so one side 3.60
    and the other none-like is no reason to stop. Anything else (3.85, 3.81, a band) is compared as usual."""
    if not GPA_Q.search(str(label or '')) or re.search(r'\bmajor\b', str(label or ''), re.I):
        return False
    def band(v):                                         # "3.5 - 3.9" / "3.70-3.89": a band that holds 3.60 is the 3.60 answer
        m = re.fullmatch(r'\s*(\d\.\d+)\s*(-|–|to)\s*(\d\.\d+)\s*', str(v or ''))
        return bool(m) and float(m.group(1)) <= 3.60 <= float(m.group(3))
    ok = lambda v: bool(re.fullmatch(r'\s*3\.790*\s*(/\s*4(\.0+)?)?\s*', str(v or ''))) or bool(GPA_NONE.match(str(v or '').strip())) or band(v)
    return ok(a) and ok(b)


MAJOR_Q = re.compile(r'\b(major|field of study|area of study|discipline|concentration|minor)\b', re.I)
NEGATOR = re.compile(r"\b(not|no|non|never|without|none|cannot)\b|n't|\d", re.I)


def major_lenient(label, a, b):
    """Pure (tested, JSA-292). Only on a major / minor / field-of-study question (free text): the rule's "Data Science" and the model's
    "Applied Data Science | None" are the same field of study — one name a whole-word run of the other (shorter 2+ words, the extra
    words no negation or number) and a none-like minor part ignored. Never for any other question (work authorization, employers,
    degrees: a prefix there is a different answer)."""
    if not MAJOR_Q.search(str(label or '')):
        return False
    pa, pb = parts(a), parts(b)
    none = lambda p: bool(re.fullmatch(r'(none|n/?a|no minor)', p.strip().lower().replace('.', '')))
    pa, pb = [x for x in pa if not none(x)], [y for y in pb if not none(y)]
    if len(pa) != 1 or len(pb) != 1:
        return False
    tok = lambda t: re.findall(r'[a-z0-9]+', re.sub(r'(?<![a-z])([a-z])\.', r'\1', t.lower()))      # B.A. = BA
    wx, wy = tok(pa[0]), tok(pb[0])
    sh, lo = (wx, wy) if len(wx) <= len(wy) else (wy, wx)
    if len(sh) < 2 or not any(lo[i:i + len(sh)] == sh for i in range(len(lo) - len(sh) + 1)):
        return False
    extra = [w for w in lo if w not in sh] if sh != lo else []
    return not NEGATOR.search(' '.join(extra))


def parts(v):
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [p.strip() for p in re.split(r'\s*\|\s*', str(v or '')) if p.strip()]


def same(rule_value, model_value, options=()):
    """Pure (tested). Do the rule and the model give the same answer? Several picks compare as sets; dates by year and
    month; numbers by value; else second_opinion.same (case / punctuation / the same option)."""
    if model_value is None:
        return False
    a, b = parts(rule_value), parts(model_value)
    if not a or not b:
        return False
    if len(a) > 1 or len(b) > 1:
        return len(a) == len(b) and all(any(same(x, y, options) for y in b) for x in a)
    x, y = a[0], b[0]
    if SO.same(x, y, options):
        return True
    mx, my = month(x), month(y)
    if mx and my:
        return mx == my
    dx, dy = ym(x), ym(y)
    if dx and dy:
        return dx[0] == dy[0] and (dx[1] is None or dy[1] is None or dx[1] == dy[1])
    nx, ny = re.fullmatch(r'\s*(\d+(\.\d+)?)\s*(/\s*4(\.0+)?)?\s*', x), re.fullmatch(r'\s*(\d+(\.\d+)?)\s*(/\s*4(\.0+)?)?\s*', y)
    if nx and ny:
        return float(nx.group(1)) == float(ny.group(1))
    return False


# ----------------------------------------------------------------------------- cache + review
def cache_path():
    try:
        import paths as jpaths
        return jpaths.data('runner', 'whole_read_cache.jsonl')
    except Exception:
        return None


def load_cache(path):
    out = {}
    try:
        for line in open(path, encoding='utf-8'):
            try:
                d = json.loads(line)
                out[d['k']] = d
            except (ValueError, KeyError):
                pass
    except OSError:
        pass
    return out


def key_of(p, model=None):
    return hashlib.sha256((PROMPT_V + (model or SO.DS_MODEL) + p).encode('utf-8')).hexdigest()[:24]


def failed(why):
    return str(why or '').startswith(('second opinion failed', 'no DeepSeek key'))


def cached_ask(prompts, post=None, cache=None, path=None, workers=8, model=None):
    """{k: prompt} → {k: (answer | None, why, cached)}: one DeepSeek call per uncached prompt, in parallel; answers
    (UNSURE included) are cached, an API error is not."""
    cache = {} if cache is None else cache
    out = {k: (cache[k].get('answer'), cache[k].get('why', ''), True) for k in prompts if k in cache}
    todo = [k for k in prompts if k not in cache]
    if not todo:
        return out
    from concurrent.futures import ThreadPoolExecutor

    def one(k):
        return k, SO.ask_model({}, '', post, prompt_text=prompts[k], model=model)
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(todo)))) as ex:
        got = dict(ex.map(one, todo))
    new = []
    for k, (m, why) in got.items():
        out[k] = (m, why, False)
        if m is None and failed(why):
            continue
        cache[k] = {'k': k, 'answer': m, 'why': why, 'at': datetime.date.today().isoformat()}
        new.append(cache[k])
    if path and new:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            for d in new:
                f.write(json.dumps(d, ensure_ascii=False) + '\n')
    return out


def read_items(items, fact_text, post=None, cache=None, path=None, workers=8):
    """[{key, label, options, value, …}] (already selected) → {key: {agree, model, why, cached, how}}.
    Step 1: the fast model (deepseek-flash) answers each question on its own — it never sees the rule's answer.
    Step 2, only where step 1 did not give the rule's answer: the stronger model (CONFIRM_MODEL) answers the same prompt
    on its own; its answer decides (one model's slip no longer stops a right answer — replay 11-10: the fast model
    answered the same question differently when the facts list changed slightly).
    Step 3, free-text questions only (no options) whose answers still differ in words: the fast model judges whether
    the two say the same thing (SAME → agree).
    how: 'same' | 'confirm' (step 2 agreed) | 'meaning' | 'disagree' | 'unsure' | 'error'."""
    cache = {} if cache is None else cache

    def ask(prompts, model=None):
        keys = {key: key_of(p, model) for key, p in prompts.items()}
        got = cached_ask({keys[key]: p for key, p in prompts.items()}, post, cache, path, workers, model)
        return {key: got[keys[key]] for key in prompts}
    p1 = {it['key']: prompt(it, fact_text) for it in items}
    a1 = ask(p1)
    out, again = {}, {}
    for it in items:
        m, why, hit = a1[it['key']]
        if same(it.get('value'), m, it.get('options') or []) or gpa_either(it.get('label'), it.get('value'), m) or (not it.get('options') and major_lenient(it.get('label'), it.get('value'), m)):
            out[it['key']] = {'agree': True, 'model': m, 'why': why, 'cached': hit, 'how': 'same'}
        else:
            again[it['key']] = p1[it['key']]
    byk = {it['key']: it for it in items}
    p3 = {}
    if again:
        a2 = ask(again, CONFIRM_MODEL)
        for key in again:
            it = byk[key]
            m, why, hit = a2[key]
            if same(it.get('value'), m, it.get('options') or []) or gpa_either(it.get('label'), it.get('value'), m) or (not it.get('options') and major_lenient(it.get('label'), it.get('value'), m)):
                out[key] = {'agree': True, 'model': m, 'why': why, 'cached': hit, 'how': 'confirm', 'first': a1[key][0]}
                continue
            how = 'error' if m is None and failed(why) else 'unsure' if m is None else 'disagree'
            out[key] = {'agree': False, 'model': m, 'why': why, 'cached': hit, 'how': how, 'first': a1[key][0]}
            if how == 'disagree' and not it.get('options'):
                p3[key] = meaning_prompt(it, it.get('value'), m)
    if p3:
        a3 = ask(p3)                                         # the fast model judges wording (the strong one was stricter on extra detail)
        for key in p3:
            m3, why3, _ = a3[key]
            if str(m3 or '').strip().upper() == 'SAME':
                out[key].update(agree=True, how='meaning', why=out[key]['why'] + ' | same meaning: ' + why3)
    return out


def blocks_first(items, sel, ents=None):
    """JSA-294: the education / work block boxes among `sel` are judged by CODE against the entry their block belongs to
    (block_check.py — all `items` in page order (`pos`) give the blocks); the model never reads a bare "Degree" / "From".
    → (decided {key: verdict}, rest): ok → agree (how 'block'); bad → not agree, the entry and the reason in `why`;
    a box the code cannot judge → kept for the model, its label carrying the entry ("Minor — education entry: …")."""
    import block_check as BC
    rows = sorted(items or [], key=lambda it: it.get('pos', 0) if isinstance(it.get('pos'), int) else 0)
    j = BC.judge(rows, ents)
    by = {rows[n]['key']: d for n, d in j.items()}
    decided, rest = {}, []
    for it in sel:
        d = by.get(it['key'])
        if not d:
            rest.append(it)
        elif d['verdict'] == 'ok':
            decided[it['key']] = {'agree': True, 'model': None, 'why': 'block check (%s): %s' % (d['context'][:120], d['why'] or 'matches'),
                                  'cached': False, 'how': 'block'}
        elif d['verdict'] == 'bad':
            decided[it['key']] = {'agree': False, 'model': None, 'why': 'block check — %s: %s' % (d['context'][:120], d['why']),
                                  'cached': False, 'how': 'block'}
        elif d.get('entry'):
            rest.append(dict(it, label='%s — %s' % (it.get('label') or '', d['context']), context=[d['context']]))
        else:
            rest.append(it)
    return decided, rest


def review(items, prof=None, post=None, env=None, path=None, ents=None):
    """Selected items → {key: verdict}; {} when off. Block boxes first by code (blocks_first), the rest by the model."""
    if not enabled(env):
        return {}
    if prof is None:
        import jsa_profile
        prof = jsa_profile.load()
    sel = select(items, prof.get('qa') or [])
    if not sel:
        return {}
    out, sel = blocks_first(items, sel, ents)
    if not sel:
        return out
    path = path or cache_path()
    out.update(read_items(sel, facts(prof), post, load_cache(path) if path else {}, path))
    return out


if __name__ == '__main__':
    data = json.load(sys.stdin)
    if '--select' in sys.argv:
        import jsa_profile
        print(json.dumps([it['key'] for it in select(data, jsa_profile.load().get('qa') or [])] if enabled() else []))
    else:
        print(json.dumps(review(data)))
