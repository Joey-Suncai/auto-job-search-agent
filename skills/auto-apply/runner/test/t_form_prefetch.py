#!/usr/bin/env python3
"""JSA-237 form prefetch (rule 13): DeepSeek-written cases from docs/specs/form-prefetch.md
(scripts/test_cases/form_prefetch_cases_*.json, verdicts in form_prefetch_verdicts.json) + fixed checks: buckets,
high-risk routing, a suggestion is never used, greedy ranking, long-tail cut, merging, staleness, cache key / reuse,
call cap, restriction kind, one job offline end to end (Greenhouse fixture, no network), the sheet and the
collect_batch --apply slots. Offline: DeepSeek is a stub; the data home is a temp dir.   python3 t_form_prefetch.py"""
import glob, json, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(RUNNER, '..', '..', '..'))
TMP = tempfile.mkdtemp(prefix='jsa_prefetch_')
os.environ['JSA_HOME'] = TMP                      # never the live data home (ADR-0008)
os.environ['CX_SECOND_OPINION'] = '0'
sys.path.insert(0, RUNNER)
import form_prefetch as FP  # noqa: E402
import collect_batch as CB  # noqa: E402

bad = 0


def check(name, ok, *info):
    global bad
    if not ok:
        bad += 1; print('FAIL', name, *info)


# ----------------------------------------------------------------------------- DeepSeek-written cases
CASES = os.path.join(ROOT, 'scripts', 'test_cases')
vp = os.path.join(CASES, 'form_prefetch_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = []
for p in sorted(glob.glob(os.path.join(CASES, 'form_prefetch_cases*.json'))):
    for c in json.load(open(p)):
        c['_file'] = os.path.basename(p); cases.append(c)
FACTS = {'answers.last_name': 'Sun', 'name.last': 'Sun', 'answers.city': 'Chicago'}


def rule_of(i):
    return {'confident': 'confident', 'uncertain': 'uncertain', 'none': 'none'}.get(i.get('rule'), i.get('rule'))


def run_case(c, long_tail=FP.LONG_TAIL):
    k, i = c['kind'], c['input']
    if k == 'route':
        risk = FP.high_risk(i.get('question'), i.get('options') or [])
        sug = i.get('suggestion') if isinstance(i.get('suggestion'), dict) else None
        facts = set(FACTS) | ({sug['fact']} if sug and sug.get('fact') else set())   # the case's fact counts as one DeepSeek was shown
        r = FP.route(rule_of(i), i.get('second_opinion'), risk, sug, facts)
        return {'route': r['route'], 'high_risk': bool(risk), 'derived_block': r['derived_block']}
    if k == 'rank':
        jobs = {j: set(v.get('needs') or []) for j, v in i['jobs'].items()}
        tiers = {j: v.get('tier') for j, v in i['jobs'].items()}
        sheet, ready, left = FP.rank(jobs, i.get('max_questions', 25), long_tail, tiers)
        return {'sheet': sheet, 'ready_after': ready, 'left_out': left}
    if k == 'stale':
        return {'read': FP.due(i.get('last'), i['today'], i.get('recheck_days', 5), i.get('only_new', False))}
    if k == 'cache':
        def key(x):
            return FP.cache_key(FP.SUGGEST_SYSTEM.format(facts='v=' + str(x.get('facts_version'))),
                                f"Question: {x.get('question')}\n" + (f"Options: {' | '.join(x.get('options') or [])}\n" if x.get('options') else 'Free-text answer.\n'), 'm')
        return {'same_answer_reused': key(i['a']) == key(i['b'])}
    if k == 'merge':
        return {'same': FP.qkey(i['a']) == FP.qkey(i['b'])}
    if k == 'restriction':
        import form_restrictions as FR
        hits = FR.find({'fields': [{'key': 'q', 'label': i['question'], 'options': []}]})
        return {'job_ineligible': FR.applies(hits, {'citizen_or_pr': i.get('citizen_or_pr')})}
    return None


n_dis = 0
for c in cases:
    try:
        got = run_case(c)
    except Exception as e:
        got = f'error {type(e).__name__}: {e}'
    exp = c.get('expect')
    if isinstance(got, dict) and isinstance(exp, dict):
        same = all(got.get(k) == v for k, v in exp.items() if k in got)
    else:
        same = got == exp
    v = verdicts.get(c['name']) or {}
    if not same and v.get('check') == 'long_tail_off':      # the case forgot the long-tail cut: its greedy order must still hold without it
        g2 = run_case(c, long_tail=0)
        if not all(g2.get(k2) == v2 for k2, v2 in exp.items()):
            bad += 1; print('DISAGREE (long tail off)', c['name'], '| got', g2, '| expect', exp)
        continue
    if not same and c['name'] not in verdicts:
        n_dis += 1; bad += 1
        print('DISAGREE', c['_file'], c['name'], json.dumps(c['input'])[:300], '| got', got, '| expect', exp)
print(f'{len(cases)} DeepSeek cases, {len(verdicts)} verdicts, {n_dis} open disagreements')

# ----------------------------------------------------------------------------- high-risk + route (fixed)
for lab, cat in [('Will you now or in the future require sponsorship for employment visa status?', 'sponsorship'),
                 ('Are you a U.S. citizen?', 'citizenship'), ('What is your current visa status?', 'visa'),
                 ('Are you legally authorized to work in the United States?', 'visa'),
                 ('This position requires access to export-controlled information (ITAR). Are you a U.S. person?', 'export control'),
                 ('What is your gender?', 'EEO'), ('Are you a protected veteran?', 'EEO'), ('Cumulative GPA', 'GPA'),
                 ('What is your expected graduation date?', 'dates'), ('When can you start?', 'dates'),
                 ('Preferred Last Name', None), ('How did you hear about us?', None), ('Which office do you prefer?', None)]:
    check('risk ' + lab, FP.high_risk(lab) == cat, FP.high_risk(lab))
check('risk: a date field', FP.high_risk('Availability', ftype='date') == 'dates')
check('risk: EEO by its options', FP.high_risk('Please select', ['Male', 'Female', 'Decline to self-identify']) == 'EEO')
check('risk: canon key', FP.high_risk('Something', canon_key='sponsorship_now') == 'sponsorship')
check('confident rule used', FP.route('confident')['route'] == 'used')
check('uncertain + agree used', FP.route('uncertain', 'agree')['route'] == 'used')
for so in ('disagree', 'error', None):
    check(f'uncertain + {so} → Joey', FP.route('uncertain', so)['route'] == 'joey')
check('per-job ask → Joey', FP.route('per_job')['route'] == 'joey')
s_ok = {'answer': 'Sun', 'fact': 'answers.last_name'}
check('no rule → sheet, never used', FP.route('none', None, None, s_ok, FACTS) == {'route': 'sheet', 'derived_block': True})
check('no rule + high risk → Joey, no block', FP.route('none', None, 'GPA', s_ok, FACTS) == {'route': 'joey', 'derived_block': False})
check('ASK → not derived', FP.route('none', None, None, {'answer': 'ASK', 'fact': None}, FACTS)['derived_block'] is False)
check('derived: the answer must be the fact (an inference is one by one)', FP.derived({'answer': 'No, remote does not suit me', 'fact': 'answers.city'}, None, FACTS) is False
      and FP.derived({'answer': 'No', 'fact': 'answers.relocate'}, None, {'answers.relocate': 'No'}) is True
      and FP.derived({'answer': 'Chicago, IL', 'fact': 'answers.city'}, None, FACTS) is True)
check('unknown fact name → not derived', FP.derived({'answer': 'x', 'fact': 'answers.made_up'}, None, FACTS) is False)
check('no suggestion → sheet, not derived', FP.route('none', None, None, None, FACTS) == {'route': 'sheet', 'derived_block': False})

# ----------------------------------------------------------------------------- staleness + selection
check('never read → read', FP.due(None, '2026-11-06'))
check('fresh → skip', not FP.due({'read_at': '2026-11-04', 'status': 'ok'}, '2026-11-06', 5))
check('5 days → re-read', FP.due({'read_at': '2026-11-01', 'status': 'ok'}, '2026-11-06', 5))
check('closed → never again', not FP.due({'read_at': '2026-10-01', 'status': 'closed'}, '2026-11-06', 5))
check('error → retried', FP.due({'read_at': '2026-11-06', 'status': 'error'}, '2026-11-06', 5))
check('only-new skips an old one', not FP.due({'read_at': '2026-10-01', 'status': 'ok'}, '2026-11-06', 5, only_new=True))
rows = [{'id': 'A', 'elig': '可投', 'score': 50, 'url': 'https://job-boards.greenhouse.io/x/jobs/1'},
        {'id': 'B', 'elig': '可投', 'score': 90, 'url': 'https://jobs.lever.co/x/0'},
        {'id': 'C', 'elig': '待核实', 'score': 99, 'url': 'https://jobs.ashbyhq.com/x/1'},
        {'id': 'D', 'elig': '可投', 'score': 95, 'url': 'https://x.wd1.myworkdayjobs.com/a'},
        {'id': 'E', 'elig': '可投', 'score': 99, 'url': 'https://apply.workable.com/x/j/ABCDEF/'},
        {'id': 'F', 'elig': '可投', 'score': 98, 'url': 'https://jobs.ashbyhq.com/x/2'}]
idx = {'F': {'read_at': '2026-10-01', 'status': 'ok'}}
sel = [r['id'] for r in FP.select(rows, idx, '2026-11-06')]
check('select: 可投 on the 4 platforms, new by score, then re-checks', sel == ['E', 'B', 'A', 'F'], sel)
check('select: --ats', [r['id'] for r in FP.select(rows, {}, '2026-11-06', ats=['lever'])] == ['B'])
check('select: --limit', len(FP.select(rows, {}, '2026-11-06', limit=2)) == 2)

# ----------------------------------------------------------------------------- greedy ranking + long tail
jobs = {'j1': {'q1'}, 'j2': {'q1'}, 'j3': {'q1', 'q2'}, 'j4': {'q2', 'q3'}, 'j5': {'q2', 'q3'}, 'j6': {'q2', 'q3'},
        'j7': {'q4'}, 'j8': {'q4', 'x:file'}, 'j9': set()}
sheet, ready, left = FP.rank(jobs, 10)
check('greedy: q1 (3 asked, 2 ready) before q2 (4 asked, 0 ready)', sheet[0] == 'q1', sheet)
check('greedy: long tail q4 (2 jobs) left out', 'q4' not in sheet and 'q4' in left)
check('greedy: ready after = j1 j2 j3 j4 j5 j6 j9', ready == 7, ready)
check('greedy: max questions', len(FP.rank(jobs, 1)[0]) == 1)
tie = {'a1': {'qa'}, 'a2': {'qa'}, 'a3': {'qa'}, 'b1': {'qb'}, 'b2': {'qb'}, 'b3': {'qb'}}
check('tie: tier A/B jobs first', FP.rank(tie, 1, tiers={'b1': 'A'})[0] == ['qb'])
check('tie: smaller id', FP.rank(tie, 1)[0] == ['qa'])

# ----------------------------------------------------------------------------- merging + match regex + slots
check('qnorm merge', FP.qkey('1.2 Preferred Last Name *') == FP.qkey('preferred last name'))
rx = FP.match_re([FP.qkey('Preferred Last Name'), FP.qkey('Preferred surname?')])
r = re.compile(rx[1:rx.rindex('/')], re.I)
check('match regex: both wordings', bool(r.search('Preferred Last Name*')) and bool(r.search('Preferred surname?')), rx)
check('match regex: not another question', not r.search('Preferred first name'))
check('qa_add accepts it', bool(re.fullmatch(r'/.+/[a-z]*', rx)))
check('slot yes/no', FP.slot('Yes', ['Yes', 'No']) == {'yes': True} and FP.slot('no', ['Yes', 'No']) == {'no': True})
check('slot pick', FP.slot('chicago', ['Chicago', 'NYC']) == {'pick': 'Chicago'})
check('slot: not an option → none', FP.slot('Boston', ['Chicago', 'NYC']) is None)
check('slot: ASK → none', FP.slot('ASK') is None and FP.slot('Sun') == {'text': 'Sun'})

# ----------------------------------------------------------------------------- DeepSeek cache, cap, errors
calls = []


def stub(system, msg):
    calls.append(msg)
    if 'BROKEN' in msg:
        raise RuntimeError('net down')
    if msg.startswith('1. ') or '\n1. ' in msg:          # grouping chunk
        items = []
        for n, line in enumerate(msg.splitlines(), 1):
            low = line.lower()
            intent = 'preferred_last_name' if ('last name' in low or 'surname' in low) else 'office_location_preference' if 'office' in low else re.sub(r'\W+', '_', low)[:30]
            items.append({'i': n, 'intent': intent, 'pattern': 'office' in low})
        return {'items': items}
    if 'principle' in system:
        return {'answer': 'Chicago first, else No preference', 'keywords': ['Chicago', 'No preference'], 'fact': 'answers.city', 'why': 'lives in Chicago'}
    if 'last name' in msg.lower() or 'surname' in msg.lower():
        return {'answer': 'Sun', 'fact': 'answers.last_name', 'why': 'last name'}
    if 'invented' in msg:
        return {'answer': 'Blue', 'fact': 'answers.favorite_color', 'why': 'made up'}
    return {'answer': 'ASK', 'fact': None, 'why': 'no fact'}


with tempfile.TemporaryDirectory() as d:
    cp = os.path.join(d, 'c.jsonl')
    ds = FP.DS(cp, budget=10, ask=stub)
    a1 = FP.suggest(ds, FACTS, 'Preferred Last Name')
    a2 = FP.suggest(FP.DS(cp, budget=10, ask=stub), FACTS, 'Preferred Last Name')
    check('cache: same answer, one call', a1 == a2 and len(calls) == 1, calls)
    FP.suggest(FP.DS(cp, budget=10, ask=stub), dict(FACTS, **{'answers.last_name': 'Sun2'}), 'Preferred Last Name')
    check('cache: a facts change asks again', len(calls) == 2)
    FP.suggest(FP.DS(cp, budget=10, ask=stub), FACTS, 'Preferred Last Name', ['Sun', 'Other'])
    check('cache: other options ask again', len(calls) == 3)
    check('suggestion naming an unknown fact → ASK', FP.suggest(ds, FACTS, 'invented question')['answer'] == 'ASK')
    check('suggestion not an option → ASK', FP.suggest(FP.DS(None, 5, ask=stub), FACTS, 'Preferred Last Name', ['Smith', 'Jones'])['answer'] == 'ASK')
    capped = FP.DS(None, budget=1, ask=stub)
    FP.suggest(capped, FACTS, 'Q one surname'); FP.suggest(capped, FACTS, 'Q two surname')
    check('cap: one call, the second capped', capped.usage['capped'] == 1)
    err = FP.DS(None, budget=5, ask=stub)
    check('error → None, never raises', FP.suggest(err, FACTS, 'BROKEN surname') is None and err.usage['errors'] == 1)
    check('no key → disabled, rules only', FP.DS(None, 5, ask=None, enabled=False).ask('s', 'm') is None)

# ----------------------------------------------------------------------------- second opinion inside the rules wrapper
class FakeDS(FP.DS):
    def __init__(self):
        super().__init__(None, 10, ask=lambda s, m: None)


def so_post(answer):
    return lambda body: {'choices': [{'message': {'content': json.dumps({'answer': answer, 'reason': 'stub'})}}]}


import second_opinion as SO  # noqa: E402
items = [{'key': 'k', 'label': 'Are you able to work without sponsorship?', 'options': ['Yes', 'No'], 'value': 'No', 'rule': 'x', 'uncertain': 'inverted'}]
check('so: agree', FP.so_review(items, FakeDS(), 'facts', post=so_post('No'))['k']['so'] == 'agree')
check('so: disagree', FP.so_review(items, FakeDS(), 'facts', post=so_post('Yes'))['k']['so'] == 'disagree')
check('so: UNSURE → disagree', FP.so_review(items, FakeDS(), 'facts', post=so_post('UNSURE'))['k']['so'] == 'disagree')
def boom(body): raise OSError('down')
check('so: API error → error (Joey)', FP.so_review(items, FakeDS(), 'facts', post=boom)['k']['so'] == 'error')
rw = FP.Rules(FakeDS(), 'facts', use_so=False)
out = rw.review({'k': {'status': 'ok', 'value': 'No', 'rule': 'x', 'uncertain': 'inverted', 'label': items[0]['label']},
                 'm': {'status': 'ok', 'value': 'Sun', 'rule': 'last_name'}}, [dict(items[0], type='radio'), {'key': 'm', 'label': 'Last', 'options': []}])
check('rules wrapper: no second opinion → unknown, confident one kept', out['k']['status'] == 'unknown' and out['m']['status'] == 'ok' and rw.last['k']['so'] == 'error')

# ----------------------------------------------------------------------------- one Greenhouse job offline (fixture), restriction
gh = json.load(open(os.path.join(HERE, 'gh_galtalnev.json')))
FP._get_json = lambda url: gh
rules = FP.Rules(FakeDS(), 'facts', use_so=False)
job = {'id': 'JT1', 'company': 'Galtalnev', 'title': 'Intern', 'url': 'https://job-boards.greenhouse.io/galtalnev/jobs/123', 'score': 80, 'tier': 'B', 'elig': '可投'}
rec = FP.read_job(job, rules, '2026-11-06', mark=None, cand={'citizen_or_pr': False})
check('job: read ok', rec['status'] == 'ok', rec.get('error'))
check('job: work dir under data/forms/work, never applications/', os.path.exists(os.path.join(TMP, 'data', 'forms', 'work', 'JT1', 'plan.json'))
      and not os.path.exists(os.path.join(TMP, 'applications')))
check('job: essay counted apart, not a question', any('good fit' in e for e in rec['essays'])
      and not any('good fit' in q['label'] for q in rec['questions']))
check('job: needs = required questions not used + files + tasks', rec['needs'] == FP.needs_count(rec))
check('job: no question is "used" unless a rule answered it', all(q['route'] != 'used' for q in rec['questions']))
check('job: high-risk questions never on the sheet route', all(q['route'] == 'joey' for q in rec['questions'] if q['risk']))
gh2 = json.loads(json.dumps(gh))
gh2['questions'].append({'label': 'This position requires access to information subject to US export controls (ITAR). Are you a U.S. person or a protected individual?',
                         'required': True, 'fields': [{'name': 'question_999', 'type': 'multi_value_single_select', 'values': [{'label': 'Yes', 'value': 1}, {'label': 'No', 'value': 0}]}]})
FP._get_json = lambda url: gh2
marked = []
rec2 = FP.read_job(dict(job, id='JT2'), rules, '2026-11-06', mark=lambda i, h: marked.append((i, h)) or True, cand={'citizen_or_pr': False})
check('restriction: status restricted, kind restriction, store marked through form_restrictions', rec2['status'] == 'restricted'
      and rec2['restriction'][0]['kind'] == 'restriction' and marked and marked[0][0] == 'JT2' and not rec2['ready'], rec2.get('status'), rec2.get('error'))
rec3 = FP.read_job(dict(job, id='JT3'), rules, '2026-11-06', mark=None, cand={'citizen_or_pr': True})
check('restriction: a citizen passes', rec3['status'] == 'ok')
def gone(url):
    import urllib.error
    raise urllib.error.HTTPError(url, 404, 'nf', None, None)
FP._get_json = gone
check('closed posting → status closed', FP.read_job(dict(job, id='JT4'), rules, '2026-11-06')['status'] == 'closed')
FP._get_json = lambda url: (_ for _ in ()).throw(ValueError('bad json'))
check('any failure → status error, never raises', FP.read_job(dict(job, id='JT5'), rules, '2026-11-06')['status'] == 'error')

# ----------------------------------------------------------------------------- the sheet
def q(label, route='sheet', risk=None, rule='none', options=()):
    return {'key': label, 'label': label, 'options': list(options), 'type': 'text', 'required': True, 'why': 'no rule', 'rule': rule, 'risk': risk, 'route': route}


recs = []
for n in range(5):
    qs = [q('Preferred Last Name' if n % 2 else 'Preferred surname'), q('Which office do you prefer?', options=[f'Office {n}', 'Chicago', 'No preference'])]
    if n < 3:
        qs.append(q('What is your cumulative GPA?', 'joey', 'GPA'))
    if n == 0:
        qs.append(q('A rare question only one job asks'))
    recs.append({'id': f'S{n}', 'status': 'ok', 'tier': 'C', 'questions': qs, 'files': [], 'joey_tasks': []})
recs.append({'id': 'S9', 'status': 'ok', 'tier': 'C', 'questions': [], 'files': [], 'joey_tasks': []})
recs.append({'id': 'SC', 'status': 'closed'})
calls.clear()
with tempfile.TemporaryDirectory() as d:
    ds = FP.DS(os.path.join(d, 'c.jsonl'), 50, ask=stub)
    sheet, md = FP.build_sheet(recs, ds, FACTS, 25)
    n_calls = len(calls)
    sheet2, _ = FP.build_sheet(recs, FP.DS(os.path.join(d, 'c.jsonl'), 50, ask=stub), FACTS, 25)
check('sheet: re-run from the cache, no new call, same sheet', len(calls) == n_calls and sheet2 == sheet)
E = {e['question']: e for e in sheet['questions']}
names = [e['question'] for e in sheet['questions']]
check('sheet: same-meaning wordings merged (DeepSeek grouping)', sum(1 for x in names if 'urname' in x or 'Last Name' in x) == 1, names)
ln = next(e for e in sheet['questions'] if 'urname' in e['question'] or 'Last Name' in e['question'])
check('sheet: merged entry has a match regex + 5 jobs', ln.get('match') and ln['n_jobs'] == 5, ln)
check('sheet: derived block on top, one click', sheet['questions'][0] is ln and ln['block'] == 'derived' and ln['suggested'] == {'text': 'Sun'})
gpa = E.get('What is your cumulative GPA?')
check('sheet: high-risk one by one, no suggestion, not derived', gpa and gpa['kind'] == 'high_risk' and not gpa.get('suggestion') and gpa.get('block') is None)
off = E.get('Which office do you prefer?')
check('sheet: pattern question asked once as a principle', off and off['kind'] == 'pattern' and off['suggested']['pick'][0] == '/Chicago/i', off)
check('sheet: long tail left out', 'A rare question only one job asks' not in E and sheet['summary']['long_tail_left_out'] == 1)
check('sheet: closed jobs not counted', sheet['summary']['jobs'] == 6 and sheet['summary']['closed'] == 1)
check('sheet: ready now 1, after 5 of 6 (S0 keeps its long-tail question)', sheet['summary']['ready_now'] == 1 and sheet['summary']['ready_after'] == 5, sheet['summary'])
check('sheet md: first line says N and X %', 'Answer these 3 and 83.3 % of the prefetched jobs become ready' in md, md[:300])
check('sheet: ≤ max questions', len(FP.build_sheet(recs, FP.DS(None, 50, ask=stub), FACTS, 1)[0]['questions']) == 1)
nods, _ = FP.build_sheet(recs, FP.DS(None, 0, ask=None, enabled=False), FACTS, 25)
check('sheet without DeepSeek: no suggestions, wordings unmerged', all('suggestion' not in e for e in nods['questions'])
      and len(nods['questions']) == 3, [e['question'] for e in nods['questions']])

# ----------------------------------------------------------------------------- collect_batch --apply compatibility
args = CB.qa_args(dict(ln, answer=None), 'Joey test')
check('apply: empty slot → skipped', args is None)
sheet['accept_derived'] = True
e = CB.sheet_answer(sheet, ln)
args = CB.qa_args(dict(ln, answer=e), 'Joey test')
check('apply: accept_derived fills the block from its suggestion + --match', args and '--text' in args and 'Sun' in args and '--match' in args, args)
check('apply: accept_derived never fills a high-risk entry', CB.sheet_answer(sheet, gpa) is None)
args = CB.qa_args(dict(off, answer=off['suggested']), 'Joey test')
check('apply: a pattern principle → repeated --pick regexes', args and args.count('--pick') == 2 and '/Chicago/i' in args, args)

sys.path.insert(0, os.path.join(RUNNER, '..', 'scripts'))
import qa_add  # noqa: E402
qe = qa_add.entry('Which office do you prefer?', pick=['/Chicago/i', '/No preference/i'], source='t', today='2026-11-06')
check('qa_add: a /regex/ pick is kept as written (pattern principle)', qe['pick'] == ['/Chicago/i', '/No preference/i'] and qe['text'] == 'Chicago', qe)
qe = qa_add.entry('Shift', pick=['Day shift'], source='t', today='2026-11-06')
check('qa_add: a plain pick is still exact', qe['pick'] == ['/^Day\\ shift$/i'] and qe['text'] == 'Day shift', qe)

import shutil  # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)
print('ALL PASS' if not bad else f'{bad} FAILED')
sys.exit(1 if bad else 0)
