#!/usr/bin/env python3
"""Form prefetch (JSA-237, spec docs/specs/form-prefetch.md; Joey 2026-11-06 「规则 + 大模型一起读」).

Reads, for every 可投 job on a platform with public form data (Greenhouse / Ashby / Lever / Workable), the application
form — no browser, no résumé / letter — answers it with today's rules exactly as batch_apply prepare would (plan_build /
run_workable.offline_plan), and records per job what still needs Joey; then one database-wide question sheet.

  ~/.job-agent-venv/bin/python form_prefetch.py [--limit N] [--recheck-days 5] [--only-new] [--ats greenhouse,lever]
                                                [--sleep 0.5] [--ds-max N] [--no-ds] [--max-questions 25] [--no-mark]
  ~/.job-agent-venv/bin/python form_prefetch.py --sheet-only      # rebuild the sheet from the saved job records

The JD verdict is JSA-231's (store elig == 可投); this reads forms only. Per question (route()):
  - rule answer, confident → used;
  - rule answer, uncertain (answer_rules `uncertain`) → DeepSeek second opinion (second_opinion.py, JSA-202, cached):
    agree → used; disagree / no answer / no key → Joey (listed per job: the qa table cannot override a rule);
  - no rule answer → the sheet; DeepSeek suggests an answer from his facts only, naming the fact, or ASK — never used
    on its own (Joey 2026-11-06), he confirms → collect_batch.py --apply → qa_add.py;
  - high-risk categories (visa, sponsorship, citizenship, export control, EEO, GPA, dates) → Joey, one by one, no suggestion.
Essays (prep_batch.open_qs) are drafted by ds_materials when the job is picked: counted apart, never Joey's.
A form that states a citizens-only / export-control / clearance restriction (form_restrictions, JSA-231) → kind
"restriction", the job 不可投 through form_restrictions.mark_store (--no-mark: recorded only).

Outputs (data home): data/forms/<id>.json · index.jsonl · questions.md · questions.json (answer slots for
collect_batch.py --apply) · runs.jsonl · ds_cache.jsonl (DeepSeek answers by sha256 of prompt version + model + system +
message; a facts change changes the system prompt, so only what it touches is asked again) · work/<id>/ (plan.json …,
never applications/). Submit still re-reads the live form, so a stale prefetch can never submit a wrong answer.
"""
import argparse, datetime, hashlib, json, os, re, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
for p in (os.path.join(ROOT, 'config'), HERE, os.path.join(HERE, '..', 'scripts'), os.path.join(ROOT, 'skills', 'job-hunt-pipeline', 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)
import paths as jpaths  # noqa: E402  (data home, ADR-0008)

PROMPT_VERSION = 'f1'
PLATFORMS = ('greenhouse', 'ashby', 'lever', 'workable')     # batch_apply.OFFLINE: public form data, no browser
MAX_QUESTIONS = 25                                           # Joey 11-06: 20–30 per morning
LONG_TAIL = 2                                                # asked by ≤ 2 jobs → asked when the job is picked
TOP_TIERS = ('A', 'B')


# ----------------------------------------------------------------------------- pure (tested: test/t_form_prefetch.py)
RISK = [
    ('export control', re.compile(r'\bexport[- ]?control|\bITAR\b|\bEAR\b|deemed export|protected individual|International Traffic in Arms', re.I)),
    ('sponsorship', re.compile(r'\bsponsor', re.I)),
    ('citizenship', re.compile(r'\bcitizen|permanent resident|green card|\bU\.?S\.? (person|national)\b|nationality|\bnational of\b|refugee|asylee', re.I)),
    ('visa', re.compile(r'\bvisa\b|immigration|\bF-?1\b|\bH-?1B\b|\bOPT\b|\bCPT\b|\bSTEM extension|\bwork authori[sz]ation|\bauthori[sz]ed to work|'
                        r'\b(legally )?(eligible|permitted|allowed|able) to work\b|\bwork permit|right to work', re.I)),
    ('EEO', re.compile(r'\bgender\b|\brace\b|ethnic|hispanic|latin[oax]|\bveteran|disabilit|sexual orientation|transgender|pronoun|'
                       r'\blgbt|\bsex\b|age range|date of birth|\bbirth ?date|\bage\b.{0,20}\b(18|older|over)\b|demographic|self[- ]identif', re.I)),
    ('GPA', re.compile(r'\bgpa\b|grade point|cumulative (grade|average)', re.I)),
    ('dates', re.compile(r'\bdates?\b|\bstart(ing)? (date|month)|\bwhen (can|could|would) you (start|begin)|\bavailab(le|ility) (to start|from|date|start)|'
                         r'\bgraduat\w* (date|month|year|term)|\b(expected|anticipated) graduation|\bmm\s*/\s*(dd|yy)|\bend date|\bnotice period|'
                         r'\bwhen (do|will) you graduate|\byear of graduation|\bclass of\b', re.I)),
]
CANON_RISK = {'work_auth_any_employer': 'visa', 'work_auth_today': 'visa', 'work_permit': 'visa', 'sponsorship_countries': 'sponsorship',
              'sponsorship_now': 'sponsorship', 'sponsorship_future': 'sponsorship', 'immigration_status': 'visa',
              'veteran_status': 'EEO', 'gender': 'EEO', 'ethnicity': 'EEO', 'disability': 'EEO'}


def high_risk(label, options=(), ftype=None, canon_key=None):
    """Pure. The high-risk category of a question (Joey always answers these himself), or None."""
    if canon_key in CANON_RISK:
        return CANON_RISK[canon_key]
    t = str(label or '')
    for cat, rx in RISK:
        if rx.search(t):
            return cat
    if ftype == 'date':
        return 'dates'
    opts = ' '.join(str(o) for o in options or [])
    if re.search(r'\bveteran|hispanic|latino|disabilit|non-?binary|\bmale\b|\bfemale\b|decline to self', opts, re.I):
        return 'EEO'
    return None


def route(rule, second_opinion=None, risk=None, suggestion=None, facts=()):
    """Pure. What happens to one question → {'route': 'used' | 'joey' | 'sheet', 'derived_block': bool}.
    rule: 'confident' | 'uncertain' | 'none' | 'per_job' (the rule knows the question, the answer is per job / per company);
    second_opinion: 'agree' | 'disagree' | 'error' | None; risk: high_risk() result; suggestion: {'answer', 'fact'} | None;
    facts: the fact names DeepSeek was shown (a suggestion naming another fact is not derived)."""
    if rule == 'confident':
        return {'route': 'used', 'derived_block': False}
    if rule == 'uncertain':                # high-risk: only a confident rule answer is used — never on DeepSeek's word (spec)
        return {'route': 'used' if second_opinion == 'agree' and not risk else 'joey', 'derived_block': False}
    if rule == 'per_job' or risk:
        return {'route': 'joey', 'derived_block': False}
    return {'route': 'sheet', 'derived_block': derived(suggestion, risk, facts)}


# facts whose meaning depends on the posting (answer_rules `jd: true`): "meets the JD's stated years" is not "has N years of
# professional experience" — never a one-click fact (full prefetch 11-06: "at least 1 year professional work experience?"
# → Yes from yoe_meets would have claimed something his facts do not say)
CONTEXTUAL = {'yoe_meets'}


def derived(suggestion, risk=None, facts=()):
    """Pure. A suggestion for the one-click block: an answer (not ASK) derived from a named fact DeepSeek was shown;
    never a high-risk question. With the facts' values (a dict) the answer must also BE that fact — the same text, the
    fact inside the chosen option, or the same Yes / No (smoke run 11-06: "remote internship OK?" → "No, …" was 'derived'
    from work_arrangement = Onsite: an inference, so it is listed one by one instead)."""
    s = suggestion or {}
    ans = str(s.get('answer') or '').strip()
    fact = s.get('fact')
    if risk or not ans or ans.upper() == 'ASK' or not fact or (facts and fact not in facts):
        return False
    if str(fact).split('.')[-1] in CONTEXTUAL:
        return False
    if isinstance(facts, dict):
        n = lambda x: re.sub(r'[^a-z0-9]+', ' ', str(x).lower()).strip()
        a, v = n(ans), n(facts[fact])
        if not v or not (a == v or (len(v) >= 3 and v in a) or (v in ('yes', 'no') and a.split()[:1] == [v])):
            return False
    return True


def due(last, today, recheck_days=5, only_new=False):
    """Pure. Read this job on this run? last = its previous record ({read_at, status}) or None."""
    if not last:
        return True
    if only_new:
        return False
    st = last.get('status')
    if st == 'closed':
        return False                       # a closed posting is not read again
    if st == 'error':
        return True                        # a failed read is retried on the next run
    try:
        age = (datetime.date.fromisoformat(str(today)[:10]) - datetime.date.fromisoformat(str(last.get('read_at'))[:10])).days
    except ValueError:
        return True
    return age >= recheck_days


def select(rows, index, today, recheck_days=5, only_new=False, ats=None, limit=None, platform=None):
    """Pure. Store rows → the jobs to read, in score order (higher first): never-read jobs first, then the due re-checks.
    Only elig == 可投 on a prefetch platform (platform(url) → name)."""
    platform = platform or _platform
    want = set(ats or PLATFORMS)
    new, again = [], []
    for r in rows:
        if r.get('elig') != '可投':
            continue
        p = platform(r.get('ats_url') or r.get('url'))
        if p not in PLATFORMS or p not in want:
            continue
        last = index.get(r.get('id'))
        if not due(last, today, recheck_days, only_new):
            continue
        (again if last else new).append(dict(r, _ats=p))
    key = lambda r: (-float(r.get('score') or 0), str(r.get('id')))
    out = sorted(new, key=key) + sorted(again, key=key)
    return out[:limit] if limit else out


def _platform(url):
    import batch_apply
    return batch_apply.platform(url)


def qkey(q):
    """Pure. The simple merge key (collect_batch.qnorm: case, numbering, punctuation, spacing)."""
    import collect_batch
    return collect_batch.qnorm(q)


def cache_key(system, msg, model):
    """Pure. Same recipe as gate_second_read.cache_key, with this module's prompt version."""
    return hashlib.sha256(f"{PROMPT_VERSION}\x00{model}\x00{system}\x00{msg}".encode('utf-8')).hexdigest()[:32]


def rank(jobs, max_questions=MAX_QUESTIONS, long_tail=LONG_TAIL, tiers=None):
    """Pure. Greedy sheet order. jobs: {job id: set of blockers}; a blocker is a sheet question id, or any id that is not a
    sheet candidate (a file, a per-job question, a long-tail question — never resolved by the sheet). tiers: {job id: tier}.
    Candidates = blockers asked by more than `long_tail` jobs. Each step takes the question that makes the most jobs fully
    ready (tier A/B jobs counted first), ties → more jobs ask it (A/B first), then the smaller id.
    → (sheet [ids], ready_after (int), left_out [ids, sorted])."""
    tiers = tiers or {}
    count = {}
    for j, need in jobs.items():
        for q in need:
            count[q] = count.get(q, 0) + 1
    cand = {q for q, n in count.items() if n > long_tail}
    left = {j: set(n) for j, n in jobs.items()}
    top = lambda j: tiers.get(j) in TOP_TIERS
    sheet = []
    while len(sheet) < max_questions:
        best, bk = None, None
        for q in sorted(cand - set(sheet)):
            asked = [j for j, n in left.items() if q in n]
            if not asked:
                continue
            done = [j for j in asked if n_left(left[j], cand) and left[j] == {q}]
            k = (sum(1 for j in done if top(j)), len(done), sum(1 for j in asked if top(j)), len(asked))
            if bk is None or k > bk:
                best, bk = q, k
        if best is None:
            break
        sheet.append(best)
        for j in left:
            left[j].discard(best)
    ready = sum(1 for j in left if not left[j])
    return sheet, ready, sorted(set(count) - set(sheet))


def n_left(need, cand):
    """Pure. True when every blocker left is a sheet candidate (the job can become ready through the sheet)."""
    return all(q in cand for q in need)


def match_re(wordings):
    """Pure. One qa_add --match regex for several merged wordings (each a qnorm key: words split by spaces)."""
    alts = sorted({r'\W+'.join(re.escape(w) for w in q.split()) for q in wordings if q.strip()})
    return '/^\\W*(?:' + '|'.join(alts) + ')\\W*(?:required)?\\W*$/i' if alts else None


def slot(answer, options=(), pattern=False):
    """Pure. A DeepSeek suggestion → a collect_batch answer slot: {'pick': …} | {'yes'/'no': True} | {'text': …}."""
    a = str(answer or '').strip()
    if not a or a.upper() == 'ASK':
        return None
    opts = [str(o) for o in options or []]
    if pattern:
        return {'text': a}
    if opts:
        o = next((x for x in opts if x.strip().lower() == a.lower()), None)
        if o is None:
            return None
        if {x.strip().lower() for x in opts} <= {'yes', 'no'}:
            return {'yes': True} if o.strip().lower() == 'yes' else {'no': True}
        return {'pick': o}
    return {'text': a}


# ----------------------------------------------------------------------------- DeepSeek (cached, capped, never fatal)
class DS:
    """DeepSeek with a JSONL cache (gate_second_read.Reader's pattern) and one call budget for the run. ask(system, msg,
    valid) → answer dict | None. None on no key, an error, an invalid answer or an exhausted budget — the caller then
    treats the question as unchecked (Joey), never fails."""

    def __init__(self, cache_path, budget=400, ask=None, model=None, enabled=True):
        self.path, self.budget, self.cache, self.enabled = cache_path, budget, {}, enabled
        self.usage = {'calls': 0, 'prompt': 0, 'out': 0, 'cached': 0, 'errors': 0, 'capped': 0}
        self._ask = ask
        self.model = model or 'test'
        if ask is None and enabled:
            try:
                import ladder
                if not ladder._key():
                    raise RuntimeError('no key')
                self.model = model or ladder.DS_MODEL
                self._ask = lambda system, msg: ladder.ask_deepseek(msg, self.usage, system=system)
            except Exception:
                self.enabled = False
        if cache_path and os.path.exists(cache_path):
            for line in open(cache_path, encoding='utf-8'):
                try:
                    x = json.loads(line); self.cache[x['k']] = x['a']
                except Exception:
                    pass

    def cached(self, system, msg):
        return cache_key(system, msg, self.model) in self.cache

    def get(self, system, msg):
        return self.cache.get(cache_key(system, msg, self.model))

    def put(self, system, msg, a):
        k = cache_key(system, msg, self.model)
        self.cache[k] = a
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'k': k, 'a': a, 'at': datetime.date.today().isoformat()}, ensure_ascii=False) + '\n')

    def ask(self, system, msg, valid=lambda a: isinstance(a, dict), call=None):
        """call: () → answer, instead of the default chat call (the second opinion uses second_opinion.ask_model)."""
        k = cache_key(system, msg, self.model)
        if k in self.cache:
            self.usage['cached'] += 1
            return self.cache[k]
        if not self.enabled or not (call or self._ask):
            return None
        if self.budget <= 0:
            self.usage['capped'] += 1
            return None
        self.budget -= 1
        try:
            a = call() if call else self._ask(system, msg)
        except Exception:
            self.usage['errors'] += 1
            return None
        if not valid(a):
            self.usage['errors'] += 1
            return None
        self.put(system, msg, a)
        return a


def so_review(items, ds, fact_text, post=None):
    """JSA-202's second opinion with the prefetch cache: [{key, label, options, value, …}] → {key: {'so': 'agree' |
    'disagree' | 'error', 'model'}}. second_opinion.prompt / ask_model / same unchanged; the rules stay the decider: the
    model can only stop an answer. post: injectable HTTP call (tests); default = DeepSeek with usage counted."""
    import second_opinion as SO
    post = post or _so_post(ds)

    def call(it):
        m, why = SO.ask_model(it, fact_text, post)
        if m is None and (why.startswith('second opinion failed') or why.startswith('no DeepSeek key')):
            raise RuntimeError(why)
        return {'answer': m or 'UNSURE', 'reason': why}
    out = {}
    for it in items:
        a = ds.ask('second_opinion:' + SO.DS_MODEL, SO.prompt(it, fact_text), lambda x: isinstance(x, dict) and 'answer' in x,
                   call=lambda it=it: call(it))
        if a is None:
            out[it['key']] = {'so': 'error', 'model': None}
            continue
        m = str(a.get('answer') or '').strip()
        m = None if not m or m.upper() == 'UNSURE' else m
        out[it['key']] = {'so': 'agree' if SO.same(it.get('value'), m, it.get('options') or []) else 'disagree', 'model': m,
                          'why': str(a.get('reason') or '')[:200]}
    return out


def _so_post(ds):
    def post(body):
        import ladder
        key = ladder._key()
        if not key:
            raise RuntimeError('no DeepSeek key')
        req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        r = json.load(urllib.request.urlopen(req, timeout=60))
        u = r.get('usage') or {}
        ds.usage['calls'] += 1; ds.usage['prompt'] += u.get('prompt_tokens', 0); ds.usage['out'] += u.get('completion_tokens', 0)
        return r
    return post


SUGGEST_SYSTEM = """You suggest an answer to ONE job-application form question for ONE candidate, using ONLY the facts below.
Facts (name: value):
{facts}

Rules: answer only when one listed fact decides it, and name that fact exactly as written before the colon. If no fact
decides it, or it asks for an opinion, essay, preference or anything not listed, answer "ASK". With options, the answer
must be one option exactly. Never guess, never invent.
Return JSON: {{"answer": "<option or short text or ASK>", "fact": "<fact name or null>", "why": "<one sentence>"}}"""

PATTERN_SYSTEM = """A kind of job-application question many companies ask with their own options (e.g. which office /
location do you prefer, how did you hear about us). Using ONLY the facts below, state ONE general principle that picks
an option at any company, e.g. "Chicago first, else No preference", plus the option keywords in priority order.
Facts (name: value):
{facts}
If no fact decides it, answer "ASK".
Return JSON: {{"answer": "<principle or ASK>", "keywords": ["<keyword>", ...], "fact": "<fact name or null>", "why": "<one sentence>"}}"""

GROUP_SYSTEM = """You group job-application form questions by meaning. For each numbered question give "intent": a short
snake_case name of exactly what it asks, the SAME name for questions that ask the same thing so that one answer fits all
of them (watch negation and time: "Have you worked here before?" and "Is this your first time applying?" differ;
"Are you available in June?" and "When can you start?" differ). "pattern": true only when the question picks among
company-specific options of a kind every company has (which office / location / team do you prefer, how did you hear
about us); false otherwise.
Common intents (reuse when they fit): preferred_first_name, preferred_last_name, pronunciation, how_heard,
office_location_preference, relocation, onsite_ok, worked_here_before, relatives_here, referral_name, linkedin_url,
portfolio_url, years_experience, salary_expectation, language_fluency, non_compete, background_check_ok.
Return JSON: {"items": [{"i": <number>, "intent": "<snake_case>", "pattern": true|false}]}"""

SENSITIVE_FACT = re.compile(r'gender|hispanic|race|veteran|disab|pronoun|transgender|orientation|age_range|phone|email|address|zip|'
                            r'visa|spons|auth|immigration|citizen|any_employer|work_permit|on_opt|eligibility|reside_us|gpa|birth|signature', re.I)


def facts_of(profile):
    """Pure. The candidate's facts DeepSeek may see for a suggestion: {name: value} — names, school, employers and the
    plain form answers; never contact details, EEO, visa / sponsorship / authorization or GPA (those are Joey's)."""
    out = {}
    nm = profile.get('name') or {}
    for k in ('first', 'last', 'preferred', 'full'):
        if nm.get(k):
            out[f'name.{k}'] = str(nm[k])
    for i, e in enumerate(profile.get('education') or []):
        for k in ('school', 'degree', 'major', 'city', 'state', 'start', 'end'):
            if isinstance(e, dict) and e.get(k):
                out[f'education[{i}].{k}'] = str(e[k])
    for i, e in enumerate(profile.get('employers') or []):
        if isinstance(e, dict):
            for k in ('name', 'company', 'title'):
                if e.get(k):
                    out[f'employers[{i}].{k}'] = str(e[k])
        elif isinstance(e, str):
            out[f'employers[{i}]'] = e
    for k, v in (profile.get('answers') or {}).items():
        if SENSITIVE_FACT.search(k) or not isinstance(v, dict):
            continue
        if isinstance(v.get('text'), str) and v['text'].strip():
            out[f'answers.{k}'] = v['text'].strip()[:200]
        elif isinstance(v.get('yes'), bool):
            out[f'answers.{k}'] = 'Yes' if v['yes'] else 'No'
    return out


def facts_text(facts):
    return '\n'.join(f'{k}: {v}' for k, v in sorted(facts.items()))


def suggest(ds, facts, question, options=(), pattern=False):
    """DeepSeek's suggestion for a sheet question (cached per question + options + facts version) → {'answer', 'fact',
    'why'[, 'keywords']} | None. A fact name it was not shown, or a non-option answer, → ASK."""
    system = (PATTERN_SYSTEM if pattern else SUGGEST_SYSTEM).format(facts=facts_text(facts))
    msg = f"Question: {question}\n" + (f"Options: {' | '.join(map(str, options))[:2500]}\n" if options else 'Free-text answer.\n')
    a = ds.ask(system, msg, lambda x: isinstance(x, dict) and 'answer' in x)
    if a is None:
        return None
    out = {'answer': str(a.get('answer') or 'ASK').strip() or 'ASK', 'fact': a.get('fact') or None, 'why': str(a.get('why') or '')[:200]}
    if out['fact'] not in facts:
        out.update(answer='ASK', fact=None)
    if pattern:
        out['keywords'] = [str(k) for k in (a.get('keywords') or []) if str(k).strip()][:6]
    elif options and out['answer'].upper() != 'ASK' and not slot(out['answer'], options):
        out.update(answer='ASK', fact=None)
    return out


def group(ds, wordings, chunk=40):
    """DeepSeek grouping (cached per wording): {wording key: {'intent', 'pattern'}}. Uncached wordings go in chunks; a
    wording with no answer keeps its own key as its group."""
    out, todo = {}, []
    line = lambda w: f"{w['q'][:300]}" + (f" [options: {' / '.join(map(str, w['options'][:8]))}]" if w.get('options') else '')
    for w in wordings:
        g = ds.get(GROUP_SYSTEM, 'Q: ' + line(w))
        if g:
            ds.usage['cached'] += 1; out[w['k']] = g
        else:
            todo.append(w)
    for s in range(0, len(todo), chunk):
        part = todo[s:s + chunk]
        msg = '\n'.join(f"{n + 1}. {line(w)}" for n, w in enumerate(part))
        a = ds.ask(GROUP_SYSTEM, msg, lambda x: isinstance(x, dict) and isinstance(x.get('items'), list))
        for it in (a or {}).get('items') or []:
            try:
                w = part[int(it.get('i')) - 1]
            except (TypeError, ValueError, IndexError):
                continue
            intent = re.sub(r'[^a-z0-9_]+', '_', str(it.get('intent') or '').lower()).strip('_')[:60]
            if intent:
                g = {'intent': intent, 'pattern': bool(it.get('pattern'))}
                ds.put(GROUP_SYSTEM, 'Q: ' + line(w), g); out[w['k']] = g
    return out


# ----------------------------------------------------------------------------- one job
class Gone(Exception):
    """The posting is closed (404 / not found)."""


def http(fn, tries=3, backoff=2.0):
    """Call fn() with retries on transient errors (timeouts, 429, 5xx); a 404 / 'not found' → Gone."""
    for n in range(tries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise Gone(f'HTTP {e.code}')
            if e.code not in (429, 500, 502, 503, 504) or n == tries - 1:
                raise
        except SystemExit as e:                       # plan_build's parsers: "posting not found"
            if re.search(r'not found|no jobPosting', str(e), re.I):
                raise Gone(str(e)[:160])
            raise RuntimeError(str(e)[:200])
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if n == tries - 1:
                raise
        time.sleep(backoff * (n + 1))


def _get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
        return json.load(r)


class Rules:
    """Wraps plan_build.run_rules / run_workable.answer: rules without the bridge's own second opinion, then the cached
    one here (so_review) on the `uncertain` answers — a disagreement becomes 'unknown' exactly like rules_bridge.js."""

    def __init__(self, ds, fact_text, use_so=True):
        self.ds, self.fact_text, self.use_so = ds, fact_text, use_so
        self.last = {}

    def wrap(self, fn):
        def inner(fields, *a, **k):
            out = fn(fields, *a, **k)
            return self.review(out, fields)
        return inner

    def review(self, out, fields):
        byk = {f['key']: f for f in fields}
        items = [{'key': k, 'label': a.get('label') or (byk.get(k) or {}).get('label', ''), 'options': (byk.get(k) or {}).get('options') or [],
                  'type': (byk.get(k) or {}).get('type'), 'value': a.get('value'), 'rule': a.get('rule'), 'uncertain': a.get('uncertain')}
                 for k, a in out.items() if isinstance(a, dict) and a.get('status') == 'ok' and a.get('uncertain')]
        rev = so_review(items, self.ds, self.fact_text) if (items and self.use_so) else {it['key']: {'so': 'error', 'model': None} for it in items}
        self.last = {}
        for k, a in out.items():
            if isinstance(a, dict):
                self.last[k] = {'status': a.get('status'), 'rule': a.get('rule'), 'ask': bool(a.get('ask')), 'uncertain': a.get('uncertain')}
        for it in items:
            v = rev.get(it['key']) or {'so': 'error'}
            self.last[it['key']]['so'] = v['so']
            if v['so'] == 'agree':
                out[it['key']] = dict(out[it['key']], second_opinion='agree')
            else:
                out[it['key']] = {'status': 'unknown', 'label': it['label'], 'rule': it['rule'], 'rejected': it['value'],
                                  'why': f"second opinion: rules said {it['value']!r} ({it['uncertain']}), the model "
                                         + (f"said {v.get('model')!r}" if v.get('model') else 'gave no answer')}
        return out


def read_form(job, work, ats):
    """HTTP → (fields, url, jd text, extra) for Greenhouse / Ashby / Lever; raises Gone for a closed posting."""
    import plan_build as PB, prep_batch
    url = re.sub(r'%20|\s+', '', job.get('ats_url') or job.get('url') or '')     # store URLs with a stray space (Lever 'Xpansiv%20')
    if ats == 'greenhouse':
        ids = prep_batch.gh_ids(url, job.get('company') or '')
        if not ids:
            raise RuntimeError('no Greenhouse board / job id in the URL')
        last = None
        for b, jid in ids:
            try:
                data = http(lambda: _get_json(f'https://boards-api.greenhouse.io/v1/boards/{b}/jobs/{jid}?questions=true'))
            except Gone as e:
                last = e; continue
            json.dump(data, open(os.path.join(work, 'gh_api.json'), 'w'), ensure_ascii=False)
            return PB.gh_fields(data), f'https://job-boards.greenhouse.io/embed/job_app?for={b}&token={jid}', prep_batch.text_of(data.get('content')), {'title': data.get('title')}
        raise last or Gone('not found')
    if ats == 'lever':
        site, jid = PB.lever_parse_url(url)
        page = http(lambda: PB.lever_fetch(site, jid))
        try:
            post = json.loads(http(lambda: PB._get(f'https://api.lever.co/v0/postings/{site}/{jid}')))
            jd = (post.get('descriptionPlain') or '') + '\n\n' + '\n\n'.join(f"{l.get('text')}\n" + prep_batch.text_of(l.get('content')) for l in post.get('lists') or []) + '\n\n' + (post.get('additionalPlain') or '')
        except Gone:
            raise
        except Exception:
            jd = ''
        return PB.lever_fields(page), f'https://jobs.lever.co/{site}/{jid}/apply', jd, {}
    if ats == 'ashby':
        org, jid = PB.ashby_parse_url(url)
        post = http(lambda: PB.ashby_fetch(org, jid))
        json.dump(post, open(os.path.join(work, 'ashby_job.json'), 'w'), ensure_ascii=False)
        jd = prep_batch.text_of(post.get('descriptionHtml') or '') if post.get('descriptionHtml') else ''
        return PB.ashby_fields(post), f'https://jobs.ashbyhq.com/{org}/{jid}/application', jd, {'title': post.get('title')}
    raise RuntimeError('platform ' + ats)


def items_of_plan(plan, last, essays):
    """Pure-ish. plan.json needs_user → per-question records with their route inputs (rule kind, second opinion)."""
    import canon
    out = []
    for n in plan.get('needs_user') or []:
        if n['key'] in essays or n.get('survey'):
            continue
        r = last.get(n['key']) or {}
        why = str(n.get('why') or '')
        if r.get('so') in ('disagree', 'error'):
            rule = 'uncertain'
        elif why.startswith('ask:') or why == 'consent' or 'not an exact option' in why or r.get('ask'):
            rule = 'per_job'
        else:
            rule = 'none'
        ftype = next((f.get('type') for f in plan.get('fields') or [] if f.get('key') == n['key']), None)
        risk = high_risk(n['label'], n.get('options'), ftype, canon.classify(n['label']) if ftype not in ('text', 'textarea', 'date') else None)
        out.append({'key': n['key'], 'label': n['label'], 'options': list(n.get('options') or [])[:60], 'type': ftype,
                    'required': bool(n.get('required')), 'why': why[:200], 'rule': rule, 'so': r.get('so'), 'risk': risk})
    return out


def read_job(job, rules, today=None, mark=None, cand=None, log=print):
    """One job → its record (never raises). mark(job_id, hits) = form_restrictions.mark_store, or None (recorded only)."""
    import plan_build as PB, prep_batch, form_restrictions as FR
    today = today or datetime.date.today().isoformat()
    ats = job.get('_ats') or _platform(job.get('ats_url') or job.get('url'))
    rec = {'id': job['id'], 'company': job.get('company'), 'title': job.get('title'), 'ats': ats, 'url': job.get('ats_url') or job.get('url'),
           'score': job.get('score'), 'tier': job.get('tier'), 'track': job.get('track'), 'read_at': today, 'prompt': PROMPT_VERSION}
    work = jpaths.data('forms', 'work', job['id'])
    rules.last = {}
    try:
        os.makedirs(work, exist_ok=True)
        json.dump({'id': job['id'], 'company': job.get('company'), 'title': job.get('title'), 'url': rec['url'], 'ats': ats, 'track': job.get('track')},
                  open(os.path.join(work, 'job.json'), 'w'), ensure_ascii=False, indent=1)
        if ats == 'workable':
            import run_workable as RW
            RW.COMPANY = job.get('company') or ''
            orig = RW.answer
            RW.answer = rules.wrap(orig)
            try:
                for n in range(3):
                    form, fields, _, ans, missing, probs = RW.offline_plan(rec['url'], work)
                    if form is not None or re.search(r'\b40[34]\b|\b410\b', ' '.join(probs)):
                        break
                    time.sleep(2 * (n + 1))
            finally:
                RW.answer = orig
            if form is None:
                if re.search(r'\b404\b|\b410\b', ' '.join(probs)):
                    raise Gone(probs[0] if probs else 'not found')
                raise RuntimeError(probs[0] if probs else 'form schema not readable')
            essays = {q['id'] for q in missing or []}
            plan = {'fields': [dict(f, answer=(ans.get(f['key']) or {}).get('value')) for f in fields], 'ats': 'workable', 'url': rec['url'],
                    'needs_user': [{'key': f['key'], 'label': f['label'], 'options': f.get('options') or [], 'required': True,
                                    'why': ('ask: ' + str((ans.get(f['key']) or {}).get('why') or '')) if (ans.get(f['key']) or {}).get('ask') else 'no rule'}
                                   for f in fields if f.get('required') and f.get('type') != 'file'
                                   and (ans.get(f['key']) or {}).get('status') != 'ok' and f['key'] not in essays]}
            json.dump(plan, open(os.path.join(work, 'plan.json'), 'w'), ensure_ascii=False, indent=1)
            essay_labels = [q['label'] for q in missing or []]
            used = [f for f in fields if f.get('type') != 'file' and (ans.get(f['key']) or {}).get('status') == 'ok']
            files = [{'key': f['key'], 'label': f['label']} for f in fields if f.get('type') == 'file' and f.get('required') and _joey_file(f['label'])]
        else:
            fields, url, jd, extra = read_form(job, work, ats)
            open(os.path.join(work, 'jd.md'), 'w', encoding='utf-8').write(f"# {extra.get('title') or job.get('title')} — {job.get('company')}\nURL: {url}\n\n{jd}\n")
            orig = PB.run_rules
            PB.run_rules = rules.wrap(orig)
            try:
                plan = PB.build(work, fields, url, ats)
            finally:
                PB.run_rules = orig
            json.dump(plan, open(os.path.join(work, 'plan.json'), 'w'), ensure_ascii=False, indent=1)
            qs = prep_batch.open_qs(plan)
            essays = {q['id'] for q in qs}
            essay_labels = [q['label'] for q in qs]
            used = [f for f in plan['fields'] if f.get('status') == 'ok' and f.get('type') not in ('file', 'hidden')]
            files = []
            if ats == 'greenhouse':
                row = {}
                _quiet(lambda: prep_batch.file_requirements(work, row))
                if row.get('status') == 'skipped_grad_transcript':
                    files.append({'key': 'grad_transcript', 'label': 'graduate transcript (JSA-216: such jobs are skipped)'})
                files += row.get('joey_files') or []
            else:
                files = [{'key': f['key'], 'label': f['label']} for f in plan['fields'] if f.get('type') == 'file' and f.get('required') and _joey_file(f['label'])]
        last = rules.last
        rec['fields'] = len([f for f in plan['fields'] if f.get('type') not in ('file', 'hidden')])
        rec['used_rule'] = sum(1 for f in used if (last.get(f['key']) or {}).get('so') != 'agree')
        rec['used_agreed'] = sum(1 for f in used if (last.get(f['key']) or {}).get('so') == 'agree')
        rec['essays'] = essay_labels
        rec['files'] = files
        rec['joey_tasks'] = prep_batch.joey_tasks(plan)
        qitems = items_of_plan(plan, last, essays)
        for q in qitems:
            q.update(route(q['rule'], q['so'], q['risk']))
        rec['questions'] = qitems
        hits = FR.find(plan)
        cand = FR.candidate() if cand is None else cand
        if FR.applies(hits, cand):
            hard = [dict(h, kind_detail=h['kind'], kind='restriction') for h in hits if h['kind'] in FR.HARD]
            rec['restriction'] = hard
            rec['status'] = 'restricted'
            if mark:
                try:
                    rec['store_marked'] = mark(job['id'], [h for h in hits if h['kind'] in FR.HARD])
                except Exception as e:
                    rec['store_marked'] = f'store not updated ({type(e).__name__}: {str(e)[:80]})'
        else:
            if hits:
                rec['restriction_note'] = hits
            rec['status'] = 'ok'
    except Gone as e:
        rec.update(status='closed', error=str(e)[:200])
    except BaseException as e:                      # one failing job never stops the run
        if isinstance(e, KeyboardInterrupt):
            raise
        rec.update(status='error', error=f'{type(e).__name__}: {str(e)[:200]}')
    rec['needs'] = needs_count(rec)
    rec['ready'] = rec['status'] == 'ok' and rec['needs'] == 0
    return rec


def _joey_file(label):
    import materials_probe
    k = materials_probe.classify(label, 'input_file')
    return k in ('other_file', 'portfolio', 'grad_transcript') or (k == 'transcript' and not _transcript())


def _transcript():
    import materials_gate
    return bool(materials_gate.TRANSCRIPT and os.path.exists(materials_gate.TRANSCRIPT))


def _quiet(fn):
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        return fn()


def needs_count(rec):
    """Pure. What still needs Joey on this job: required questions not routed to 'used' + his files + his tasks."""
    if rec.get('status') != 'ok':
        return None
    q = sum(1 for x in rec.get('questions') or [] if x.get('required') and x.get('route') != 'used')
    return q + len(rec.get('files') or []) + len(rec.get('joey_tasks') or [])


def blockers(rec):
    """Pure. A record's blockers for rank(): 'q:<key>' for each sheet question (by its merge key), 'x:…' for the rest."""
    out = set()
    for x in rec.get('questions') or []:
        if not x.get('required') or x.get('route') == 'used':
            continue
        out.add(('q:' if x.get('route') == 'sheet' or (x.get('risk') and x.get('rule') == 'none') else 'x:') + qkey(x['label']))
    out |= {f"x:file:{f.get('key')}" for f in rec.get('files') or []}
    out |= {f"x:task:{t[:40]}" for t in rec.get('joey_tasks') or []}
    return out


# ----------------------------------------------------------------------------- the sheet
def build_sheet(recs, ds, facts, max_questions=MAX_QUESTIONS, use_ds=True, today=None):
    """Every saved job record → (sheet dict for questions.json, markdown). Same-meaning wordings merged (qnorm, then
    DeepSeek grouping of the non-high-risk ones), greedy order (rank), fact-derived block on top, pattern questions as one
    principle, the long tail left out."""
    today = today or datetime.date.today().isoformat()
    live = {r['id']: r for r in recs if r.get('status') == 'ok'}
    words = {}                                         # qnorm key → {q, options, risk, jobs}
    for r in live.values():
        for x in r.get('questions') or []:
            if not x.get('required') or x.get('route') == 'used' or not (x.get('route') == 'sheet' or (x.get('risk') and x.get('rule') == 'none')):
                continue
            k = qkey(x['label'])
            w = words.setdefault(k, {'k': k, 'q': x['label'], 'options': [], 'risk': x.get('risk'), 'jobs': set(), 'type': x.get('type'), 'optsets': set()})
            w['jobs'].add(r['id'])
            w['optsets'].add(tuple(x.get('options') or []))
            for o in x.get('options') or []:
                if o not in w['options']:
                    w['options'].append(o)
    groups = group(ds, [w for w in words.values() if not w['risk']]) if use_ds else {}
    gid = {}                                           # wording key → group id
    for k, w in words.items():
        g = groups.get(k)
        gid[k] = ('g:' + g['intent']) if g else ('w:' + k)
    jobs = {}
    for j, r in live.items():
        b = set()
        for x in blockers(r):
            b.add(('q:' + gid[x[2:]]) if x.startswith('q:') and x[2:] in gid else x)
        jobs[j] = b
    tiers = {j: r.get('tier') for j, r in live.items()}
    sheet_ids, ready_after, _ = rank(jobs, max_questions, LONG_TAIL, tiers)
    ready_now = sum(1 for b in jobs.values() if not b)
    members = {}
    for k, g in gid.items():
        members.setdefault('q:' + g, []).append(words[k])
    entries, n_ds = [], 0
    answered = {j: set(b) for j, b in jobs.items()}
    for n, sid in enumerate(sheet_ids, 1):
        ms = sorted(members.get(sid, []), key=lambda w: (-len(w['jobs']), w['q']))
        if not ms:
            continue
        rep = ms[0]
        opts = []
        for w in ms:
            opts += [o for o in w['options'] if o not in opts]
        pattern = bool((groups.get(rep['k']) or {}).get('pattern')) and len(set().union(*[w['optsets'] for w in ms])) > 1   # options differ per company
        risk = next((w['risk'] for w in ms if w['risk']), None)
        sug = None
        if use_ds and not risk:
            sug = suggest(ds, facts, rep['q'], [] if pattern else opts[:60], pattern)
        before = sum(1 for b in answered.values() if not b)
        for b in answered.values():
            b.discard(sid)
        gain = sum(1 for b in answered.values() if not b) - before
        jl = sorted(set().union(*[w['jobs'] for w in ms]))
        e = {'id': f'P{n}', 'question': rep['q'], 'options': [] if pattern else opts[:60], 'type': rep.get('type') or '',
             'kind': 'high_risk' if risk else 'pattern' if pattern else 'fact', 'risk': risk, 'jobs': jl, 'folders': jl,
             'n_jobs': len(jl), 'ready_gain': gain, 'wordings': [w['q'] for w in ms][:12], 'answer': None}
        if len(ms) > 1:
            e['match'] = match_re([w['k'] for w in ms])
        if pattern:
            e['example_options'] = {w['q'][:80]: w['options'][:12] for w in ms[:4]}
        if sug:
            e['suggestion'] = sug
            if pattern and sug.get('answer', 'ASK').upper() != 'ASK' and sug.get('keywords'):
                e['suggested'] = {'pick': ['/' + re.escape(k) + '/i' for k in sug['keywords']], 'principle': sug['answer']}
            elif not pattern:
                s = slot(sug.get('answer'), opts)
                if s:
                    e['suggested'] = s
            e['block'] = 'derived' if (not pattern and derived(sug, risk, facts) and e.get('suggested')) else None   # a principle is confirmed on its own
        entries.append(e)
    entries.sort(key=lambda e: (e.get('block') != 'derived', int(e['id'][1:])))
    total = len(live)
    pct = round(100.0 * ready_after / total, 1) if total else 0.0
    other = {}
    for r in live.values():
        for x in r.get('questions') or []:
            if x.get('required') and x.get('route') == 'joey' and x.get('rule') in ('uncertain', 'per_job'):
                k = qkey(x['label'])
                o = other.setdefault(k, {'question': x['label'], 'why': x.get('why'), 'rule': x['rule'], 'jobs': []})
                o['jobs'].append(r['id'])
    long_tail = sum(1 for sid in {g for b in jobs.values() for g in b if g.startswith('q:')} if sid not in sheet_ids
                    and sum(1 for b in jobs.values() if sid in b) <= LONG_TAIL)
    sheet = {'name': 'prefetch-' + today, 'generated': today, 'prompt': PROMPT_VERSION,
             'summary': {'jobs': total, 'ready_now': ready_now, 'ready_after': ready_after, 'pct_after': pct, 'questions': len(entries),
                         'long_tail_left_out': long_tail, 'closed': sum(1 for r in recs if r.get('status') == 'closed'),
                         'restricted': sum(1 for r in recs if r.get('status') == 'restricted'), 'errors': sum(1 for r in recs if r.get('status') == 'error')},
             'accept_derived': False, 'questions': entries,
             'per_job': sorted(other.values(), key=lambda o: -len(o['jobs']))[:40]}
    return sheet, sheet_md(sheet)


def sheet_md(s):
    sm = s['summary']
    L = [f"# Form prefetch questions — {s['generated']}", '',
         f"**Answer these {sm['questions']} and {sm['pct_after']} % of the prefetched jobs become ready to submit** "
         f"({sm['ready_after']} of {sm['jobs']}; {sm['ready_now']} ready already).", '',
         f"Not asked ahead: {sm['long_tail_left_out']} long-tail question(s) (≤ {LONG_TAIL} jobs) — asked when such a job is picked. "
         f"Closed {sm['closed']} · form restriction (不可投) {sm['restricted']} · read errors {sm['errors']}.", '',
         'Fill the `answer` slots in questions.json (or set `"accept_derived": true` for the whole first block), then:',
         '`python3 skills/auto-apply/runner/collect_batch.py --apply <data home>/data/forms/questions.json --source "Joey <date> (prefetch)"`', '']
    der = [e for e in s['questions'] if e.get('block') == 'derived']
    rest = [e for e in s['questions'] if e.get('block') != 'derived']
    if der:
        L += ['## Derived from your facts — accept the whole block with one click', '']
        for e in der:
            sug = e['suggestion']
            L.append(f"- **{e['id']}** ({e['n_jobs']} jobs, +{e['ready_gain']} ready) {e['question'][:160]} → **{sug['answer']}** _(from {sug['fact']})_")
        L.append('')
    if rest:
        L += ['## One by one', '']
        for e in rest:
            tag = {'high_risk': f"⚠ {e.get('risk')} — your answer, no suggestion", 'pattern': 'one principle for every company'}.get(e['kind'], '')
            L.append(f"**{e['id']}** ({e['n_jobs']} jobs, +{e['ready_gain']} ready){' · ' + tag if tag else ''} — {e['question'][:200]}")
            if e.get('options'):
                L.append('  options: ' + ' / '.join(map(str, e['options'][:12])) + (' …' if len(e['options']) > 12 else ''))
            if e.get('example_options'):
                for q, o in list(e['example_options'].items())[:3]:
                    L.append(f"  e.g. {q[:60]}: {' / '.join(o[:6])}")
            if len(e.get('wordings') or []) > 1:
                L.append(f"  also asked as: {' | '.join(w[:60] for w in e['wordings'][1:4])}")
            sug = e.get('suggestion')
            if sug and sug.get('answer', 'ASK').upper() != 'ASK':
                L.append(f"  suggestion: {sug['answer']}" + (f" (from {sug['fact']})" if sug.get('fact') else ''))
            L.append('')
    if s.get('per_job'):
        L += ['## Not on the sheet: a rule answers these but needs a check (second opinion disagreed / per-company answer)', '']
        L += [f"- {o['question'][:140]} · {len(o['jobs'])} job(s) · {o['why'][:100]}" for o in s['per_job'][:15]] + ['']
    return '\n'.join(L)


# ----------------------------------------------------------------------------- I/O + CLI
def load_index(path):
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            try:
                x = json.loads(line); out[x['id']] = x
            except Exception:
                pass
    return out


def index_row(rec):
    return {k: rec.get(k) for k in ('id', 'company', 'title', 'ats', 'status', 'read_at', 'needs', 'ready', 'score', 'tier', 'error')}


def write_index(path, index):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for k in sorted(index):
            f.write(json.dumps(index[k], ensure_ascii=False) + '\n')
    os.replace(tmp, path)


def load_recs(d, index):
    out = []
    for i in index:
        p = os.path.join(d, f'{i}.json')
        if os.path.exists(p):
            try:
                out.append(json.load(open(p, encoding='utf-8')))
            except ValueError:
                pass
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--limit', type=int); ap.add_argument('--recheck-days', type=int, default=5)
    ap.add_argument('--only-new', action='store_true'); ap.add_argument('--ats', help='comma-separated: ' + ','.join(PLATFORMS))
    ap.add_argument('--sleep', type=float, default=0.5); ap.add_argument('--ds-max', type=int, default=400)
    ap.add_argument('--no-ds', action='store_true'); ap.add_argument('--max-questions', type=int, default=MAX_QUESTIONS)
    ap.add_argument('--no-mark', action='store_true', help='record form restrictions without marking the store 不可投')
    ap.add_argument('--sheet-only', action='store_true'); ap.add_argument('--ids', help='comma-separated job ids (debugging)')
    a = ap.parse_args(argv)
    t0 = time.time()
    os.environ['CX_SECOND_OPINION'] = '0'          # the bridge's own (uncached) second opinion is off: Rules does it, cached
    d = jpaths.data('forms')
    os.makedirs(d, exist_ok=True)
    ipath = os.path.join(d, 'index.jsonl')
    index = load_index(ipath)
    import jsa_profile, second_opinion as SO
    profile = jsa_profile.load()
    facts = facts_of(profile)
    ds = DS(os.path.join(d, 'ds_cache.jsonl'), budget=a.ds_max, enabled=not a.no_ds)
    fact_text = SO.facts(open(SO.PROFILE_MD, encoding='utf-8').read()) if os.path.exists(SO.PROFILE_MD) else ''
    rules = Rules(ds, fact_text, use_so=ds.enabled)
    today = datetime.date.today().isoformat()
    stats = {'read': 0, 'ok': 0, 'ready': 0, 'closed': 0, 'error': 0, 'restricted': 0, 'by_ats': {}}
    if not a.sheet_only:
        sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
        import store
        rows = store.load('jobs')
        if a.ids:
            want = set(a.ids.split(','))
            rows = [r for r in rows if r.get('id') in want]
        todo = select(rows, index, today, a.recheck_days, a.only_new, a.ats.split(',') if a.ats else None, a.limit)
        import form_restrictions as FR
        cand = FR.candidate()
        mark = None if a.no_mark else FR.mark_store
        print(f'form_prefetch: {len(todo)} job(s) to read (index {len(index)}, recheck {a.recheck_days} d, DeepSeek {"on" if ds.enabled else "off"})')
        for n, job in enumerate(todo, 1):
            rec = read_job(job, rules, today, mark, cand)
            json.dump(rec, open(os.path.join(d, f"{job['id']}.json"), 'w'), ensure_ascii=False, indent=1)
            index[job['id']] = index_row(rec)
            stats['read'] += 1
            stats[rec['status']] = stats.get(rec['status'], 0) + 1
            stats['ready'] += 1 if rec.get('ready') else 0
            b = stats['by_ats'].setdefault(rec['ats'], {'read': 0, 'ready': 0})
            b['read'] += 1; b['ready'] += 1 if rec.get('ready') else 0
            print(f"{n:4}. {rec['status']:10} {rec['ats']:10} needs={rec.get('needs')!s:4} {rec['id']} {str(rec.get('company'))[:24]} | {str(rec.get('title'))[:50]}"
                  + (f" | {rec.get('error', '')[:80]}" if rec.get('error') else ''))
            if n % 20 == 0:
                write_index(ipath, index)
            time.sleep(a.sleep)
        write_index(ipath, index)
    recs = load_recs(d, index)
    sheet, md = build_sheet(recs, ds, facts, a.max_questions, use_ds=ds.enabled, today=today)
    json.dump(sheet, open(os.path.join(d, 'questions.json'), 'w'), ensure_ascii=False, indent=1)
    open(os.path.join(d, 'questions.md'), 'w', encoding='utf-8').write(md)
    stats.update(secs=round(time.time() - t0, 1), ds=ds.usage, sheet=sheet['summary'], at=datetime.datetime.now().isoformat(timespec='seconds'))
    with open(os.path.join(d, 'runs.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(stats, ensure_ascii=False) + '\n')
    sm = sheet['summary']
    print(f"form_prefetch: read {stats['read']} · ready {stats['ready']} · closed {stats.get('closed', 0)} · restricted {stats.get('restricted', 0)} · errors {stats.get('error', 0)} · "
          f"DeepSeek {ds.usage} · {stats['secs']} s")
    print(f"sheet: answer these {sm['questions']} and {sm['pct_after']} % of the {sm['jobs']} prefetched jobs become ready ({sm['ready_now']} ready now) → {os.path.join(d, 'questions.md')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
