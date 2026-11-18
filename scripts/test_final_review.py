"""Pre-submit independent review (JSA-355, rule 13). DeepSeek's cases (scripts/test_cases/final_review_cases.json, from
final_review_spec.md, not the code) say which page cells are key; the real critical wrong answers the audit found
(data home data/runner/wrong_answers.jsonl, read only) must ALL be key cells; the gate logic is tested with a stubbed
reviewer (no network). Verdicts on disagreeing cases: test_cases/final_review_verdicts.json."""
import json, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNNER = os.path.join(ROOT, 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUNNER); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'config'))
import final_review as FR  # noqa: E402
import paths  # noqa: E402

bad = 0
def check(name, ok, detail=''):
    global bad
    if not ok:
        bad += 1; print('FAIL', name, detail)

cases = json.load(open(os.path.join(HERE, 'test_cases', 'final_review_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'final_review_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
for c in cases:
    a = c['args']
    got = FR.select([{'label': a['label'], 'value': a['value'], 'type': a.get('type', ''), 'options': a.get('options', [])}])
    groups = got[0]['groups'] if got else []
    ok = (not got) if c['expect'] == 'skip' else (bool(got) and (not c.get('group') or c['group'] in groups))
    if not ok and c['name'] in verdicts:
        print('judged ', c['name'], '—', verdicts[c['name']][:90]); continue
    check('select ' + c['name'], ok, f"{a['label'][:60]!r} -> {groups} expect {c['expect']}/{c.get('group')}")

# every critical wrong answer the audit found is a key cell
wa = paths.data('runner', 'wrong_answers.jsonl')
n = 0
if os.path.exists(wa):
    for l in open(wa, encoding='utf-8'):
        r = json.loads(l)
        if r.get('class') != 'critical':
            continue
        m = re.match(r"answered '(.*?)'(?: —| \()", r['note']) or re.match(r"picked the '(.*?)' option", r['note'])
        v = m.group(1) if m else 'x'
        n += 1
        check('wrong-answer is key: ' + r['field'][:50], bool(FR.select([{'label': r['field'], 'value': v, 'type': 'text'}])), repr(v))
    print('wrong_answers critical checked:', n)

# gate logic with a stubbed reviewer (one read per cell here; the two-read rule is tested below)
FR.READS = 1
cell = {'label': 'Will you require sponsorship now?', 'value': 'Yes', 'type': 'radio', 'options': ['Yes', 'No']}
skip = {'label': 'Email', 'value': 'a@b.c', 'type': 'text'}
def stub(verdict):
    calls = []
    def call(prompt):
        calls.append(prompt)
        return json.dumps({'verdicts': [{'i': i, 'verdict': verdict, 'reason': 'because'} for i in range(prompt.count('\n#'))]})
    call.calls = calls
    return call
tmp = tempfile.mkdtemp()
def run(verdict, mode, recs=None, call=None, cache=True):
    call = call or stub(verdict)
    lp = os.path.join(tmp, 'log_%s_%s.jsonl' % (verdict, mode))
    p = FR.problems(recs or [cell, skip], mode=mode, call=call, facts='F-1 student', log_path=lp,
                    cache_path=os.path.join(tmp, 'c_%s_%s.jsonl' % (verdict, mode)) if cache else None)
    return p, call, lp
p, call, lp = run('OK', 'block')
check('OK → no problem', p == [], p); check('only key cell sent', len(call.calls) == 1 and 'a@b.c' not in call.calls[0])
p, _, _ = run('WRONG', 'block'); check('WRONG blocks', len(p) == 1 and 'sponsorship' in p[0] and 'because' in p[0], p)
p, _, _ = run('UNSURE', 'block'); check('UNSURE blocks', len(p) == 1, p)
def boom(prompt): raise RuntimeError('api down')
p, _, _ = run('x', 'block', call=boom); check('API error blocks (fail closed)', len(p) == 1 and 'api down' in p[0], p)
def junk(prompt): return 'not json'
p, _, _ = run('x', 'block', call=junk); check('garbled reply blocks', len(p) == 1, p)
p, _, lp = run('WRONG', 'shadow'); check('shadow: no block', p == [], p)
check('shadow: logged', os.path.exists(lp) and 'WRONG' in open(lp).read())
c0 = stub('OFF'); p, _, _ = run('x', '0', call=c0); check('off: nothing called', p == [] and not c0.calls)
c1 = stub('OK'); p, _, _ = run('x', 'block', recs=[skip], call=c1); check('no key cell → no call', p == [] and not c1.calls)
c2 = stub('OK'); cp = os.path.join(tmp, 'cache2.jsonl')
FR.problems([cell], mode='block', call=c2, facts='F', cache_path=cp, log_path=None)
FR.problems([cell], mode='block', call=c2, facts='F', cache_path=cp, log_path=None)
check('cache: same cell asked once', len(c2.calls) == 1, len(c2.calls))
FR.problems([cell], mode='block', call=c2, facts='F2', cache_path=cp, log_path=None)
check('cache: new facts → asked again', len(c2.calls) == 2)

# mode(): live runs only
check('mode off in tests', FR.mode({'JSA_NO_PUSH': '1', 'CX_SECOND_OPINION': '1'}) == '0')
check('mode off with CX_DATA', FR.mode({'CX_DATA': '/x', 'CX_FINAL_REVIEW': 'block'}) == '0')
check('mode default shadow in a live run', FR.mode({'CX_SECOND_OPINION': '1'}) == 'shadow')
check('mode block', FR.mode({'CX_SECOND_OPINION': '1', 'CX_FINAL_REVIEW': 'block'}) == 'block')
check('mode explicit off', FR.mode({'CX_SECOND_OPINION': '1', 'CX_FINAL_REVIEW': '0'}) == '0')

# two reads, the worse verdict wins
seq = iter(['OK', 'WRONG']); rd = []
def alt(prompt):
    rd.append(1); v = next(seq)
    return json.dumps({'verdicts': [{'i': 0, 'verdict': v, 'reason': 'second read'}]})
FR.READS = 2
p = FR.problems([cell], mode='block', call=alt, facts='F', cache_path=None, log_path=None)
check('two reads: one WRONG blocks', len(rd) == 2 and len(p) == 1 and 'second read' in p[0], (len(rd), p))
FR.READS = 1

# review findings (JSA-355 code review): truncated duplicate, home address stays local, odd records, chunks, typo mode, daily cache
full = 'Are you legally authorized to work in the United States? ' + 'Please read the notice carefully. ' * 6 + 'Answer Yes or No.'
dup = FR.select([{'label': full[:140], 'value': 'Yes', 'type': 'text'}, {'label': full, 'value': 'Yes', 'type': 'radio', 'options': ['Yes', 'No']}])
check('truncated duplicate dropped', len(dup) == 1 and dup[0]['label'] == full, len(dup))
addr = {'label': 'What is your street address? Please also include your city, state, and zip', 'value': '12 Example Rd', 'type': 'text'}
ca = stub('OK'); p, _, _ = run('x', 'block', recs=[addr], call=ca)
check('home address is never sent', not ca.calls and len(p) == 1 and 'locally' in p[0], (p, len(ca.calls)))
ca = stub('OK'); p, _, _ = run('x', 'block', recs=[dict(addr, value='12 Example Rd, Springfield, IL 62701')], call=ca)
hc = {'label': 'Home address (city, state, zip)', 'value': 'Chicago, IL 60601', 'type': 'text'}
ca = stub('OK'); p, _, _ = run('x', 'block', recs=[hc], call=ca)
check('any address label stays local', not ca.calls and p == [], p)
check('date box sees education facts', 'Education entry' in FR.facts_for(['shape'], 'Education entry: X, 2026-09 - 2027-12'))
check('complete address ok, still not sent', p == [] and not ca.calls, p)
p, _, _ = run('x', 'block', recs=[None, cell]); check('a malformed record blocks, no crash (block mode)', len(p) == 1 and 'unavailable' in p[0], p)
p, _, _ = run('x', 'shadow', recs=[None, cell]); check('a malformed record does not block in shadow', p == [], p)
many = [dict(cell, label='Will you require sponsorship now? #%d' % i) for i in range(45)]
cm = stub('OK'); p, _, _ = run('x', 'block', recs=many, call=cm, cache=False)
check('45 key cells → 3 calls of at most 20', len(cm.calls) == 3 and p == [], (len(cm.calls), p))
check('typo of block fails closed', FR.mode({'CX_SECOND_OPINION': '1', 'CX_FINAL_REVIEW': 'blok'}) == 'block')
k1 = FR._key(cell, 'F-1\nToday is 2026-11-16.'); k2 = FR._key(cell, 'F-1\nToday is 2026-11-17.')
check('cache key ignores the date line', k1 == k2)

# only the facts on the cells' topics go out
ft = 'Sponsorship now: No (CPT)\nPhone: 555-0100\nGender: x\nHome: 1 Example Rd\nQuestion consent for talent pool: Yes\nToday is 2026-11-17.'
sl = FR.facts_for(['work_auth'], ft)
check('facts_for keeps the topic + date, drops the rest', 'Sponsorship now' in sl and 'Today is' in sl and 'Phone' not in sl and 'Home' not in sl and 'Gender' not in sl, sl)
sent = []
FR.READS = 1
FR.problems([cell], mode='block', call=lambda t: (sent.append(t), json.dumps({'verdicts': [{'i': 0, 'verdict': 'OK', 'reason': ''}]}))[1], facts=ft, cache_path=None, log_path=None)
check('prompt carries the sliced facts only', 'Sponsorship now' in sent[0] and 'Phone: 555' not in sent[0] and 'Home: 1 Example' not in sent[0])

# the shared submit gate (runner_common) really blocks on a review verdict — Run.check and Run.gate_inside
import runner_common as RC  # noqa: E402
saved = (FR.haiku_call, FR._facts, FR._paths, {k: os.environ.pop(k, None) for k in ('JSA_NO_PUSH', 'CX_DATA')})
os.environ['CX_FINAL_REVIEW'] = 'block'
FR._facts = lambda: 'F-1 student'; FR._paths = lambda n: None
FR.haiku_call = lambda text, system=None: json.dumps({'verdicts': [{'i': 0, 'verdict': 'WRONG', 'reason': 'form is wrong'}]})
try:
    run_ = object.__new__(RC.Run); run_.posting = 'https://example.test/job'; run_.folder = ''; run_.log = lambda m: None
    run_.common = []; run_.stopped_at = None; run_.approved = lambda: True
    res = {'status': 'dry-run', 'fields': [{'label': 'Name pronunciation', 'page': 'Some Full Name', 'ok': True, 'type': 'text'}]}
    probs = run_.check(res)
    check('Run.check blocks on a WRONG verdict', any('final review WRONG' in x for x in probs), probs)
    check('Run.gate_inside refuses to press', run_.gate_inside(dict(res)) is False)
    FR.haiku_call = lambda text, system=None: json.dumps({'verdicts': [{'i': 0, 'verdict': 'OK', 'reason': ''}]})
    probs = run_.check(res)
    check('Run.check passes an OK verdict', not any('final review' in x for x in probs), probs)
finally:
    FR.haiku_call, FR._facts, FR._paths = saved[0], saved[1], saved[2]
    os.environ.pop('CX_FINAL_REVIEW', None)
    for k, v in saved[3].items():
        if v is not None:
            os.environ[k] = v

# every runner's submit path calls the gate
for f in ('run.py', 'run_wd.py', 'run_form.py', 'runner_common.py'):
    check('hook in ' + f, 'final_review' in open(os.path.join(RUNNER, f)).read())

print('FAIL' if bad else 'OK', bad)
sys.exit(1 if bad else 0)
