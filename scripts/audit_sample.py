#!/usr/bin/env python3
"""Independent audit of submitted applications (JSA-245, Joey 2026-11-08 「加独立抽查」).

The scorecard's wrong-answer count only holds errors somebody found (form replay, canon check, second opinion, e-mails):
a rule that was wrong from the start and that nothing re-checks never shows up. This samples submitted forms per
platform and checks EVERY answer on them against Joey's facts, so the accuracy is measured, not assumed.

    python3 scripts/audit_sample.py --run [--n 50] [--platform greenhouse,workday] [--seed 2026-11-08]   # sample + check
    python3 scripts/audit_sample.py --pending           # items waiting for a judgment (DeepSeek said wrong / unsure)
    python3 scripts/audit_sample.py --judge <key> right|wrong [--note "…"]   # Claude's (or Joey's) judgment
    python3 scripts/audit_sample.py --summary [--json]  # accuracy per platform over every audit so far

Who checks what (rule 13 spirit — the answering rules never grade themselves):
  * contact, link and location fields (name, e-mail, phone, LinkedIn / website, address, city, state, country …):
    compared with config/profile.json by code (contact_check), whatever group the question is in;
  * EEO fields: never sent to a model — compared by code with the profile's self-identification answers; what does not
    plainly match waits for a judgment;
  * everything else: DeepSeek (not the rule set that answered) with his confirmed facts (candidate-profile.md, contact
    stripped) and his saved form answers (config qa) → right / wrong / unsure + the fact it used.
  Every "wrong" or "unsure" waits for a judgment (--judge); a confirmed wrong answer is appended to
  data/runner/wrong_answers.jsonl (class from scripts/field_class.py), so the scorecard counts it. Judging it right later
  withdraws that line again (only the audit's own line, never one the replay or Joey recorded).
Sampling: per platform, submitted folders (results.jsonl) never audited before, random with a seed (default: today), n per
platform. Answers = what the runner read back from the page (fields corpus, latest run), else what it planned; files,
account / password fields and empty answers are not answers.
Data (data home): data/runner/audit/items.jsonl (one line per checked answer) · audit_<date>.md (the run's report) ·
ds_cache.jsonl. Weekly: run_daily.py gate runs `--run` on Sundays. Tests: scripts/test_audit_sample.py (DeepSeek cases).
"""
import argparse, glob, hashlib, json, math, os, random, re, sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home, ADR-0008)
sys.path.insert(0, HERE)
from field_class import field_class  # noqa: E402

SKIP_TYPES = {'file', 'account', 'hidden', 'password'}
ESSAY = 300          # longer answers are written prose: ds_materials fact-checks them before submit, not this audit
PROMPT_V = 'a1'
SYSTEM = """You audit answers that were submitted on job application forms for one candidate. You get the candidate's
confirmed FACTS and a list of ITEMS (question, the options offered if any, the answer that was submitted). For each item
decide, using ONLY the facts: "right" (the answer is what the facts call for, or an equally true choice among the options),
"wrong" (the facts call for a different answer — say which), or "unsure" (the facts do not settle it). Do not mark an
answer wrong for style, capitalisation, or because a longer free-text answer could be better; mark it wrong only when it
states something false or picks an option the facts contradict. Return JSON {"items": [{"k": <item number>, "verdict":
"right"|"wrong"|"unsure", "should": <answer the facts call for, or "">, "fact": <the fact you used, short>}]}."""


def audit_dir():
    return os.environ.get('JSA_AUDIT_DIR') or jpaths.data('runner', 'audit')


def jsonl(p):
    out = []
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    return out


# ----------------------------------------------------------------------------- pure parts (tested)
def submitted_by_platform(results, platform_of):
    """Pure (tested). results.jsonl lines → {platform: sorted folder names whose LATEST line has status 'submitted'}.
    Lines without a folder are ignored; platform_of(line) names the platform of a folder's latest line."""
    last = {}
    for r in results:
        f = r.get('folder')
        if f and (f not in last or str(r.get('at') or '') >= str(last[f].get('at') or '')):
            last[f] = r
    out = {}
    for f, r in last.items():
        if r.get('status') == 'submitted':
            out.setdefault(platform_of(r), []).append(f)
    return {p: sorted(v) for p, v in out.items()}


def sample(folders, audited, n, seed, first=None):
    """Pure (tested). Up to n folders not in `audited`, chosen by random.Random(seed) from the sorted list; result sorted.
    first = the folders to take first (the certification window, JSA-258): the sample comes from those not yet audited;
    only when they are fewer than n does the rest of the pool fill up the sample (by the same seed)."""
    pool = sorted(set(folders) - set(audited or ()))
    if n <= 0 or not pool:
        return []
    rnd = random.Random(str(seed))
    if first is None:
        return sorted(rnd.sample(pool, min(n, len(pool))))
    win = [f for f in pool if f in set(first)]
    rest = [f for f in pool if f not in set(first)]
    got = rnd.sample(win, min(n, len(win)))
    got += rnd.sample(rest, min(n - len(got), len(rest)))
    return sorted(got)


def answers_of(lines, folder):
    """Pure (tested). Fields-corpus lines → the answers on the folder's LATEST run (by "at", then run_id):
    [{"question", "answer", "options", "type"}], answer = "page" when non-empty else "planned". Skipped: types file /
    account / hidden / password (any case), a question starting with "Account:", an empty answer, an answer longer than
    300 characters (prose — ds_materials checks it), and a repeat of the same question on that run (first kept).
    Each answer also carries "at" (the run's time)."""
    runs = {}
    for d in lines:
        if d.get('folder') != folder:
            continue
        k = (str(d.get('at') or ''), str(d.get('run_id') or ''))
        runs.setdefault(k, []).append(d)
    if not runs:
        return []
    out, seen = [], set()
    for d in runs[max(runs)]:
        t = str(d.get('type') or '').lower()
        q = str(d.get('question') or '').strip()
        a = d.get('page')
        a = a if a not in (None, '') else d.get('planned')
        a = '' if a is None else str(a).strip()
        if t in SKIP_TYPES or not q or q.lower().startswith('account:') or not a or q in seen or len(a) > ESSAY:
            continue
        seen.add(q)
        out.append({'question': q, 'answer': a, 'options': list(d.get('options') or [])[:40], 'type': t, 'at': str(d.get('at') or '')})
    return out


def norm_answer(a):
    """Pure (tested). The form's stored value as text: "True" / "False" (any case) → "Yes" / "No"; a list written as
    "['Asian']" or '["A", "B"]' → "Asian" / "A | B"; surrounding spaces trimmed."""
    s = str(a or '').strip()
    if s.lower() in ('true', 'false'):
        return 'Yes' if s.lower() == 'true' else 'No'
    m = re.match(r'^\[(.*)\]$', s, re.S)
    if m:
        parts = [x.strip().strip('\'"').strip() for x in m.group(1).split(',')]
        return ' | '.join(x for x in parts if x)
    return s


def bucket(question):
    """Pure (tested). 'contact' | 'eeo' | 'model' — who checks this answer (field_class group)."""
    cls, grp = field_class(question)
    return grp if grp in ('contact', 'eeo') else 'model'


def digits(s):
    return re.sub(r'\D', '', str(s or ''))


def contact_check(question, answer, prof):
    """Pure (tested). A contact / link / location answer against the profile → 'right' | 'wrong' | 'unsure', or None when
    the question is none of these (then another check decides). In this order:
    e-mail: equal (case-insensitive) to contact.email or contact.secondary_email, else 'wrong';
    phone ... code (country phone code): 'right' when the answer holds "+1" or "United States", else 'unsure';
    phone device / type: equal to answers.phone_device "text", else 'unsure'; phone: the same last 10 digits as
    contact.phone, else 'wrong'; LinkedIn: the same profile path as contact.linkedin (scheme, www, trailing slash
    ignored), else 'wrong'; website / portfolio / GitHub / URL / link: the same as contact.website or contact.linkedin,
    else 'unsure';
    "I have a preferred name" (or "do you have a preferred name"): 'right' when the answer is checked / yes / true and
    answers.has_preferred is yes; middle name / initial: 'right' when the profile has no middle name and the answer is
    blank-like (N/A, NA, None, -); first / last / full / preferred name: equal (case-insensitive) to the matching name.*
    value, a name question naming neither first nor last accepts any of first / last / full / preferred / signature,
    else 'wrong';
    permanent address, zip / postal, county, country, state / province, city / town, street address: the answer equals
    answers[key]."text" (case-insensitive), matches one of its "pick" patterns, or starts with its "text" followed by a
    comma ("<City>, <ST>, US"; "<street>, <City>, <ST> <ZIP>") → 'right', else 'unsure'."""
    q, a = question.lower(), answer.strip()
    c, n, ans = prof.get('contact') or {}, prof.get('name') or {}, prof.get('answers') or {}
    low = a.lower()
    url = lambda v: re.sub(r'^(https?://)?(www\.)?', '', str(v or '').strip().lower()).rstrip('/')
    if re.search(r'e-?mail', q):
        return 'right' if low in {str(c.get('email') or '').lower(), str(c.get('secondary_email') or '').lower()} - {''} else 'wrong'
    if re.search(r'phone', q) and re.search(r'\bcode\b', q):
        return 'right' if re.search(r'\+1\b|united states', low) else 'unsure'
    if re.search(r'phone', q) and re.search(r'device|type', q):
        t = str((ans.get('phone_device') or {}).get('text') or '').lower()
        return 'right' if t and low == t else 'unsure'
    if re.search(r'phone|mobile|cell', q):
        p = digits(c.get('phone'))
        return 'right' if p and digits(a)[-10:] == p[-10:] else 'wrong'
    if 'linkedin' in q:
        return 'right' if url(a) and url(a) == url(c.get('linkedin')) else 'wrong'
    if re.search(r'website|portfolio|github|\burl\b|\blink\b', q):
        return 'right' if url(a) and url(a) in {url(c.get('website')), url(c.get('linkedin'))} - {''} else 'unsure'
    if re.search(r'(have|has) a preferred name', q):
        hp = ans.get('has_preferred') or {}
        yes = hp.get('yes') is True or str(hp.get('text') or '').lower() in ('yes', 'true')
        return 'right' if yes and low in ('checked', 'yes', 'true', 'on') else 'unsure'
    if re.search(r'middle (name|initial)', q):
        return 'right' if not str(n.get('middle') or '').strip() and low in ('', 'n/a', 'na', 'none', '-') else 'unsure'
    if 'name' in q and not re.search(r'school|company|employer|university|college|reference|manager|recruiter|\breferr', q):
        names = {k: str(n.get(k) or '').strip().lower() for k in ('first', 'last', 'full', 'preferred', 'signature')}
        if re.search(r'\bfirst\b|\bgiven\b', q):
            ok = {names['first'], names['preferred']} if 'prefer' in q else {names['first']}
        elif re.search(r'\blast\b|\bfamily\b|\bsurname\b', q):
            ok = {names['last']}
        elif 'prefer' in q:
            ok = {names['preferred'], names['first']}
        else:
            ok = set(names.values())
        return 'right' if low in ok - {''} else 'wrong'
    for k, pat in (('permanent_address', r'permanent'), ('zip', r'\bzip\b|postal'), ('county', r'\bcounty\b'),
                   ('country', r'\bcountry\b'), ('state', r'\bstate\b|province'), ('city', r'\bcity\b|\btown\b'),
                   ('address', r'address|street')):
        if re.search(pat, q):
            spec = ans.get(k) or {}
            t = str(spec.get('text') or '').strip().lower()
            if t and (low == t or low.startswith(t + ',')):
                return 'right'
            if any(r and r.search(a) for r in (js_re(p) for p in spec.get('pick') or [])):
                return 'right'
            return 'unsure'
    return None


EEO_KEYS = [('hispanic', r'hispanic|latin[oax]'), ('transgender', r'transgender'), ('orientation', r'sexual orientation'),
            ('pronouns', r'pronoun'), ('veteran', r'veteran'), ('disability', r'disab'), ('gender', r'\bgender\b|\bsex\b'),
            ('race', r'\brace\b|ethnic')]


def js_re(s):
    """'/pattern/i' → a compiled Python regex (case-insensitive when the flags hold i); a plain string → its escape."""
    m = re.match(r'^/(.*)/([a-z]*)$', str(s), re.S)
    try:
        return re.compile(m.group(1), re.I if 'i' in m.group(2) else 0) if m else re.compile(re.escape(str(s)), re.I)
    except re.error:
        return None


def eeo_key(q, a):
    """Pure (tested). Which self-identification answer a question asks: 'race' when it names race(s); else the first of
    EEO_KEYS that matches; an "ethnicity" question is 'hispanic' when the answer is a yes / no or names Hispanic / Latino,
    else 'race'. None = not recognised."""
    q = q.lower()
    if re.search(r'\braces?\b', q):
        return 'race'
    for k, pat in EEO_KEYS:
        if k != 'race' and re.search(pat, q):
            return k
    if re.search(r'ethnic', q):
        return 'hispanic' if re.search(r'^(no|yes)\b|hispanic|latin', a.strip(), re.I) else 'race'
    return None


def eeo_check(question, answer, prof):
    """Pure (tested). An EEO answer against the profile's own self-identification answers (profile.answers[key], key from
    the question by eeo_key()) → 'right' when the answer matches one of the key's "pick" patterns, or its "text" (case-insensitive), or —
    for a "yes": false key — starts with "No"; 'unsure' otherwise (no key, no profile answer, a decline, anything else).
    Never 'wrong': the judge decides; the code only clears the answers that plainly match."""
    q, a = question.lower(), answer.strip()
    key = eeo_key(q, a)
    spec = ((prof.get('answers') or {}).get(key) or {}) if key else {}
    if not spec or not a:
        return 'unsure'
    if any(r and r.search(a) for r in (js_re(p) for p in spec.get('pick') or [])):
        return 'right'
    if spec.get('text') and a.lower() == str(spec['text']).strip().lower():
        return 'right'
    if spec.get('yes') is False and re.match(r'^no\b', a, re.I):
        return 'right'
    return 'unsure'


SOURCE_Q = re.compile(r"(how|where) did you (\w+ )?(hear|find|learn|see)|(how|where) you (\w+ )?(heard|found out|learned|saw) (about|of)\b|"
                      r"how were you made aware of\b|^(applicant |candidate )?source( of (application|referral))?\b|"
                      r"\b(which|what|name of the) (job )?(board|site|website)\b.{0,60}\b(learn|hear|see|saw|find|found)|"
                      r"^career communi\w*\s*/\s*job boards?$|^which job board")
SOURCE_NOT = re.compile(r"\bif referred\b|\bname of (the|an?) (employee|person|referr)|who referred|root cause|investigat|problem")
SOURCE_PERSON = re.compile(r"\breferr|\bemployee\b|\brecruiter|\bfriend|\bcolleague|\bco-?worker|word of mouth|\bfamily\b|contacted me|reached out|\bagency\b|search firm|staffing", re.I)


def date_check(question, answer, at):
    """Pure (tested). "Date signed" / "today's date" / "signature date" questions: 'right' when the answer is that run's
    date (MM/DD/YYYY, YYYY-MM-DD or M/D/YYYY) or the day before / after; 'wrong' for another date; None when the question
    is not such a question or the run time is unknown."""
    if not re.search(r"date signed|signature date|today'?s date|\bdate of signature\b|^date$", question.strip().lower()) or not at:
        return None
    try:
        run = date.fromisoformat(at[:10])
    except ValueError:
        return None
    m = re.match(r'^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$', answer) or None
    try:
        d = date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else date.fromisoformat(answer.strip()[:10])
    except ValueError:
        return 'wrong'
    return 'right' if abs((d - run).days) <= 1 else 'wrong'


def source_check(question, answer):
    """Pure (tested). A job-source question ("How did you hear about us?", "name of the job board where you learned about
    this position", "Source") with a filled answer → 'right': any filled source counts, whether or not he really saw the job
    there (Joey 2026-11-09, JSA-261). None when the question is no source question, the answer is empty, or the answer
    claims a person or a third party (referral / employee / recruiter / friend / "contacted me" / agency / staffing
    firm — those still get the model check)."""
    q = str(question or '').strip().lower()
    if not SOURCE_Q.search(q) or SOURCE_NOT.search(q):
        return None
    a = str(answer or '').strip()
    if not a or SOURCE_PERSON.search(a):
        return None
    return 'right'


def key_of(folder, question):
    return hashlib.sha1(f'{folder}\x00{question}'.encode()).hexdigest()[:12]


def summary(items):
    """Pure (tested). Items → {platform: {"answers", "wrong", "pending", "accuracy", "low95"}} plus "all".
    An item counts as wrong when judged 'wrong', right when judged 'right' or when its check said 'right' with no
    judgment; anything else is pending (not in the accuracy). A wrong item with `covered` (the current rules answer that
    question right now — Joey 2026-11-09 「新规则已经覆盖了，就不要算错」, JSA-260) is counted under "covered" (key present
    only when > 0), not as wrong, and stays out of the accuracy. accuracy = right / (right + wrong), None when 0 judged;
    low95 = the Wilson 95 % lower bound of that rate (z = 1.96), None when 0 judged. Values rounded to 4 places."""
    agg = {}
    for it in items:
        st = it.get('judged') or ('right' if it.get('check') == 'right' else None)
        for p in (it.get('platform') or 'other', 'all'):
            a = agg.setdefault(p, {'answers': 0, 'wrong': 0, 'pending': 0, 'covered': 0})
            a['answers'] += 1
            if st == 'wrong' and it.get('covered'):
                a['covered'] += 1
            elif st == 'wrong':
                a['wrong'] += 1
            elif st != 'right':
                a['pending'] += 1
    z = 1.96
    for a in agg.values():
        n = a['answers'] - a['pending'] - a['covered']
        if not a['covered']:
            del a['covered']                        # the key appears only when some wrong answer is covered
        if n:
            ph = (n - a['wrong']) / n
            lo = (ph + z * z / (2 * n) - z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))) / (1 + z * z / n)
            a['accuracy'], a['low95'] = round(ph, 4), round(max(lo, 0.0), 4)
        else:
            a['accuracy'] = a['low95'] = None
    return agg


# ----------------------------------------------------------------------------- live parts
def facts_text(prof):
    sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
    import ladder
    import second_opinion
    lines = list(ladder.saved_facts())
    try:
        lines += second_opinion.facts(open(second_opinion.PROFILE_MD, encoding='utf-8').read()).splitlines()
    except OSError:
        pass
    for q in prof.get('qa') or []:
        if not isinstance(q, dict) or not q.get('q'):
            continue
        a = 'Yes' if q.get('yes') is True else 'No' if q.get('yes') is False else q.get('text') or ' / '.join(q.get('pick') or [])
        if a:
            lines.append(f"Saved form answer — {q['q'][:160]} → {str(a)[:120]}")
    for l in prof.get('languages') or []:
        lines.append(f"Language: {l.get('name')} — {l.get('level')}")
    return '\n'.join(lines)


def ds_check(items, facts, cache_path, usage):
    """DeepSeek on one folder's model items (cached by prompt version + facts + items) → {index: verdict dict}."""
    sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
    import ladder
    msg = 'FACTS:\n' + facts + '\n\nITEMS:\n' + '\n'.join(
        f"{i}. Q: {it['question'][:2000]}" + (f" | options: {' / '.join(it['options'][:25])[:600]}" if it['options'] else '')
        + f" | submitted: {it['answer'][:300]}" for i, it in enumerate(items))
    h = hashlib.sha256((PROMPT_V + SYSTEM + msg).encode()).hexdigest()
    for c in jsonl(cache_path):
        if c.get('h') == h:
            return {int(k): v for k, v in c['out'].items()}
    out = {}
    try:
        r = ladder.ask_deepseek(msg, usage, system=SYSTEM)
        for x in r.get('items') or []:
            try:
                out[int(x.get('k'))] = {'verdict': x.get('verdict'), 'should': x.get('should') or '', 'fact': x.get('fact') or ''}
            except (TypeError, ValueError):
                pass
    except Exception as e:
        print(f'audit: DeepSeek failed ({type(e).__name__}: {str(e)[:120]}) — items left unsure')
        return {}
    with open(cache_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'h': h, 'out': out}, ensure_ascii=False) + '\n')
    return out


def run(n, platforms, seed):
    import audit_score as PS                     # ADR-0011 step 5: the shared counting lives in the product
    sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
    import jsa_profile
    prof = jsa_profile.load()
    d = audit_dir()
    os.makedirs(d, exist_ok=True)
    ipath = os.path.join(d, 'items.jsonl')
    old = jsonl(ipath)
    audited = {it['folder'] for it in old}
    by = submitted_by_platform(jsonl(jpaths.data('runner', 'results.jsonl')), PS.platform)
    try:                                         # JSA-258: the certification window's forms first (the audit is a bar there)
        recert = json.load(open(jpaths.data('runner', 'recertify.json'), encoding='utf-8'))
    except (OSError, ValueError):
        recert = {}
    win = PS.window_folders(PS.load(since=PS.CERT_SINCE)[0], recert)
    import subprocess                            # the corpus first: Greenhouse / Lever / Ashby / Workday answers reach it only
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'learn', 'convert_fields.py')],   # through convert_fields (11-09)
                   capture_output=True, text=True, timeout=600)
    lines = [x for p in glob.glob(jpaths.data('runner', 'fields', '*.jsonl')) for x in jsonl(p)]
    facts = facts_text(prof)
    usage = {'calls': 0, 'prompt': 0, 'out': 0}
    today = date.today().isoformat()
    new = []
    for plat in sorted(by):
        if platforms and plat not in platforms:
            continue
        for folder in sample(by[plat], audited, n, f'{seed}:{plat}', first=win.get(plat, [])):
            ans = answers_of(lines, folder)
            if not ans:
                continue
            for a in ans:
                a['answer'] = norm_answer(a['answer'])
            model = [a for a in ans if bucket(a['question']) == 'model' and date_check(a['question'], a['answer'], a.get('at')) is None
                     and contact_check(a['question'], a['answer'], prof) is None
                     and source_check(a['question'], a['answer']) is None]
            ds = ds_check(model, facts, os.path.join(d, 'ds_cache.jsonl'), usage) if model else {}
            for a in ans:
                a['answer'] = norm_answer(a['answer'])
                b = bucket(a['question'])
                it = dict(a, key=key_of(folder, a['question']), platform=plat, folder=folder, by=b, audited=today,
                          cls=field_class(a['question'])[0], judged=None)
                cc = contact_check(a['question'], a['answer'], prof) if b != 'eeo' else None
                if cc is not None:
                    it['check'] = cc
                elif b == 'contact':
                    it['check'] = 'unsure'
                elif b == 'eeo':
                    it['check'] = eeo_check(a['question'], a['answer'], prof)
                elif source_check(a['question'], a['answer']) is not None:
                    it['check'] = 'right'
                    it['fact'] = 'any filled job source is right (Joey 2026-11-09, JSA-261)'
                elif date_check(a['question'], a['answer'], a.get('at')) is not None:
                    it['check'] = date_check(a['question'], a['answer'], a.get('at'))
                else:
                    v = ds.get(model.index(a), {})
                    it['check'] = v.get('verdict') if v.get('verdict') in ('right', 'wrong', 'unsure') else 'unsure'
                    it['should'], it['fact'] = v.get('should', ''), v.get('fact', '')
                new.append(it)
    with open(ipath, 'a', encoding='utf-8') as f:
        for it in new:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    rep = report(new, summary(old + new), usage, today)
    open(os.path.join(d, f'audit_{today}.md'), 'w', encoding='utf-8').write(rep)
    folders = len({it['folder'] for it in new})
    pend = sum(1 for it in new if it['check'] != 'right')
    print(f'audit: {folders} folder(s) · {len(new)} answers · {pend} to judge · DeepSeek {usage} → {os.path.join(d, f"audit_{today}.md")}')
    return new


def report(new, sm, usage, today):
    L = [f'# Independent audit — {today} (JSA-245)', '',
         f'{len({i["folder"] for i in new})} submitted forms · {len(new)} answers checked · DeepSeek {usage}', '',
         '| Platform | Answers audited (all runs) | Wrong (confirmed) | Waiting for a judgment | Accuracy | 95 % lower bound |', '|---|---|---|---|---|---|']
    for p in sorted(k for k in sm if k != 'all') + ['all']:
        a = sm[p]
        pct = lambda v: '—' if v is None else f'{100 * v:.1f} %'
        L.append(f"| {p} | {a['answers']} | {a['wrong']} | {a['pending']} | {pct(a['accuracy'])} | {pct(a['low95'])} |")
    L += ['', '## To judge (`python3 scripts/audit_sample.py --judge <key> right|wrong --note "…"`)', '']
    for it in new:
        if it['check'] != 'right':
            L.append(f"- `{it['key']}` {it['platform']} · {it['folder']} · [{it['by']}/{it['cls']}] **{it['question'][:120]}** → "
                     f"`{it['answer'][:100]}` — check: {it['check']}" + (f" · should: `{it.get('should', '')[:80]}` ({it.get('fact', '')[:100]})" if it.get('should') or it.get('fact') else ''))
    return '\n'.join(L) + '\n'


def judge(key, verdict, note):
    d = audit_dir()
    ipath = os.path.join(d, 'items.jsonl')
    items = jsonl(ipath)
    hit = [it for it in items if it.get('key') == key]
    if not hit:
        print(f'audit: no item {key}'); return 1
    was = hit[0].get('judged')
    for it in hit:
        it['judged'], it['note'] = verdict, note
    tmp = ipath + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    os.replace(tmp, ipath)
    it = hit[0]
    if was == 'wrong' and verdict == 'right':   # a reversed judgment withdraws the audit's wrong-answer line (Joey 11-08: field of study)
        wp = jpaths.data('runner', 'wrong_answers.jsonl')
        keep = [w for w in jsonl(wp) if not (w.get('folder') == it['folder'] and w.get('field') == it['question']
                                              and 'independent audit, JSA-245' in str(w.get('note') or ''))]
        with open(wp + '.tmp', 'w', encoding='utf-8') as f:
            for w in keep:
                f.write(json.dumps(w, ensure_ascii=False) + '\n')
        os.replace(wp + '.tmp', wp)
        print(f'audit: {key} → right (its wrong_answers.jsonl line withdrawn)')
        return 0
    if verdict == 'wrong' and was != 'wrong':
        w = {'folder': it['folder'], 'field': it['question'], 'note': f"answered {it['answer'][:120]!r} — {note} (found by the independent audit, JSA-245)",
             'found': date.today().isoformat(), 'class': it.get('cls')}
        with open(jpaths.data('runner', 'wrong_answers.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(w, ensure_ascii=False) + '\n')
    print(f"audit: {key} → {verdict}" + (' (added to wrong_answers.jsonl)' if verdict == 'wrong' else ''))
    return 0


def cover(key, note, by=''):
    """JSA-260: mark a judged-wrong item as covered by the current rules (they answer that question right now) — on the
    item and on its wrong_answers.jsonl line(s), which platform_scorecard then skips outside a re-certification window."""
    ipath = os.path.join(audit_dir(), 'items.jsonl')
    items = jsonl(ipath)
    hit = [it for it in items if it.get('key') == key]
    if not hit or hit[0].get('judged') != 'wrong':
        print(f'audit: {key} is not a judged-wrong item'); return 1
    tag = {'by': by, 'note': note, 'on': date.today().isoformat()}
    for it in hit:
        it['covered'] = tag
    with open(ipath + '.tmp', 'w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    os.replace(ipath + '.tmp', ipath)
    wp = jpaths.data('runner', 'wrong_answers.jsonl')
    ws = jsonl(wp)
    for w in ws:
        if w.get('folder') == hit[0]['folder'] and w.get('field') == hit[0]['question']:
            w['covered'] = tag
    with open(wp + '.tmp', 'w', encoding='utf-8') as f:
        for w in ws:
            f.write(json.dumps(w, ensure_ascii=False) + '\n')
    os.replace(wp + '.tmp', wp)
    print(f'audit: {key} → covered by the current rules')
    return 0


def rules_now(items):
    """The current rules' answer for each item's question ({key: answer}), through runner/rules_bridge.js."""
    import subprocess
    fields = [{'key': it['key'], 'label': it['question'], 'type': it.get('type') or ('combo' if it.get('options') else 'text'),
               'options': it.get('options') or []} for it in items]
    r = subprocess.run(['node', os.path.join(ROOT, 'skills', 'auto-apply', 'runner', 'rules_bridge.js')], input=json.dumps(fields),
                       capture_output=True, text=True, timeout=300, env=dict(os.environ, CX_SECOND_OPINION='0'))
    return json.loads(r.stdout or '{}')


def recheck():
    """JSA-260: every judged-wrong, not-yet-covered item with what the current rules answer now — for the judge to mark the
    ones the rules fix (`--cover KEY`). Prints only; nothing is marked here."""
    items = [it for it in jsonl(os.path.join(audit_dir(), 'items.jsonl')) if it.get('judged') == 'wrong' and not it.get('covered')]
    now = rules_now(items) if items else {}
    print(f'audit: {len(items)} wrong answer(s) not covered')
    for it in items:
        a = now.get(it['key']) or {}
        v = a.get('value') if a.get('status') == 'ok' else ('asked' if a.get('ask') or a.get('status') == 'unknown' else a.get('status'))
        print(f"- {it['key']} {it['platform']} · {it['folder'][:40]} · {it['question'][:80]} | sent {str(it['answer'])[:50]!r} "
              f"| rules now {str(v)[:60]!r} ({a.get('rule')}) | note {str(it.get('note') or '')[:60]}")
    return 0


def pending_items():
    return [it for it in jsonl(os.path.join(audit_dir(), 'items.jsonl')) if not it.get('judged') and it.get('check') != 'right']


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--run', action='store_true'); ap.add_argument('--n', type=int, default=50, help='forms per platform (Joey 2026-11-09: 50, JSA-259)')
    ap.add_argument('--platform'); ap.add_argument('--seed', default=date.today().isoformat())
    ap.add_argument('--pending', action='store_true'); ap.add_argument('--summary', action='store_true')
    ap.add_argument('--json', action='store_true'); ap.add_argument('--judge', nargs=2, metavar=('KEY', 'VERDICT'))
    ap.add_argument('--note', default='')
    ap.add_argument('--recheck', action='store_true', help='wrong answers + what the current rules answer now (JSA-260)')
    ap.add_argument('--cover', metavar='KEY', help='mark a wrong answer as covered by the current rules (JSA-260)')
    ap.add_argument('--by', default='', help='with --cover: the release / commit whose rules answer it right')
    a = ap.parse_args(argv)
    if a.cover:
        return cover(a.cover, a.note, a.by)
    if a.recheck:
        return recheck()
    if a.judge:
        if a.judge[1] not in ('right', 'wrong'):
            ap.error('verdict is right or wrong')
        return judge(a.judge[0], a.judge[1], a.note)
    if a.run:
        run(a.n, set(a.platform.split(',')) if a.platform else None, a.seed)
        return 0
    if a.pending:
        p = pending_items()
        print(f'audit: {len(p)} answer(s) waiting for a judgment')
        for it in p:
            print(f"- {it['key']} {it['platform']} · {it['folder']} · [{it['by']}] {it['question'][:100]} → {it['answer'][:80]} "
                  f"(check {it['check']}{', should ' + it['should'][:60] if it.get('should') else ''})")
        return 0
    sm = summary(jsonl(os.path.join(audit_dir(), 'items.jsonl')))
    print(json.dumps(sm, indent=1) if a.json else '\n'.join(f"{p}: {v}" for p, v in sorted(sm.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
