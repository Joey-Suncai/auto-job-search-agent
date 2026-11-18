#!/usr/bin/env python3
"""JSA-277 (rule 13): DeepSeek-written cases from scripts/test_cases/qa_overlap_spec.md (qa_overlap_cases*.json, verdicts
in qa_overlap_verdicts.json) for both layers — qa_add.py's overlap check before a save (qa_overlap.js, the matching of
answer_rules.js) and answer_rules.js qaAnswer trying every matching entry newest first — plus fixed checks of
qa_add.change() (--replace-entry / --narrow-entry) and overlap_lines(). Offline; the example profile with the case's
table.   python3 t_qa_overlap.py"""
import glob, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(SCRIPTS, '..', '..', '..'))
sys.path.insert(0, SCRIPTS)
import qa_add as QA  # noqa: E402

BASE = json.load(open(os.path.join(ROOT, 'config', 'profile.example.json'), encoding='utf-8'))
TMP = tempfile.mkdtemp(prefix='jsa_qa_')
bad = 0


def check(name, ok, *info):
    global bad
    if not ok:
        bad += 1; print('FAIL', name, *info)


def profile(table):
    p = os.path.join(TMP, 'profile.json')
    json.dump(dict(BASE, qa=table), open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    return p


ANSWER_JS = """const {qaAnswer} = require(process.argv[1]); let s = ''; process.stdin.on('data', d => s += d).on('end', () => {
  const f = JSON.parse(s); const T = {select: 'combo', radio: 'radio', checkbox: 'checkbox', text: 'text'};
  process.stdout.write(JSON.stringify(qaAnswer({l: f.label, t: T[f.type] || 'text', o: f.options || []}, f.label))); });"""


def answer(table, field):
    r = subprocess.run(['node', '-e', ANSWER_JS, os.path.join(SCRIPTS, 'answer_rules.js')], input=json.dumps(field),
                       capture_output=True, text=True, env=dict(os.environ, JSA_PROFILE=profile(table)), timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300])
    return json.loads(r.stdout)


def run_case(c):
    i = c['input']
    if c['kind'] == 'overlap':
        table = list(i['table']) + [i['new']]
        res = QA.overlaps(profile(table), len(table))
        ci, ic = sorted(x['n'] for x in res['catches_it']), sorted(x['n'] for x in res['it_catches'])
        return {'blocked': bool(ci or ic), 'catches_it': ci, 'it_catches': ic}
    a = answer(i['table'], {'label': i['label'], 'type': i.get('type'), 'options': i.get('options') or []})
    return None if a is None else {k: a.get(k) for k in ('status', 'value', 'rule') if k in a}


CASES = os.path.join(ROOT, 'scripts', 'test_cases')
vp = os.path.join(CASES, 'qa_overlap_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = [c for p in sorted(glob.glob(os.path.join(CASES, 'qa_overlap_cases*.json'))) for c in json.load(open(p))]
n_dis = 0
for c in cases:
    try:
        got = run_case(c)
    except Exception as e:
        got = f'error {type(e).__name__}: {e}'
    exp = c.get('expect')
    same = (all(got.get(k) == v for k, v in exp.items()) if isinstance(got, dict) and isinstance(exp, dict) else got == exp)
    if not same and c['name'] not in verdicts:
        n_dis += 1; bad += 1
        print('DISAGREE', c['name'], json.dumps(c['input'])[:400], '| got', got, '| expect', exp)
print(f'{len(cases)} DeepSeek cases, {len(verdicts)} verdicts, {n_dis} open disagreements')

# ----------------------------------------------------------------------------- fixed: the user's choice on an overlap
E = lambda q, **k: dict({'q': q, 'text': 'x', 'source': 't', 'added': '2026-11-10'}, **k)
p, how = QA.change({'qa': [E('A'), E('B')]}, E('C'), replace_entry=1)
check('replace-entry puts the new entry in N', [x['q'] for x in p['qa']] == ['C', 'B'] and how == 'replaced #1', p, how)
p, how = QA.change({'qa': [E('A', match='/a|c/i')]}, E('C'), narrow_entry=1, narrow_match='/^a$/i')
check('narrow-entry changes N and adds', p['qa'][0]['match'] == '/^a$/i' and p['qa'][1]['q'] == 'C' and 'narrowed' in how, p, how)
p, _ = QA.change({'qa': [E('A', match='/a/i')]}, E('C'), narrow_entry=1, narrow_match='-')
check('narrow-match - drops the regex', 'match' not in p['qa'][0])
for kw, why in ((dict(replace_entry=3), 'out of range'), (dict(narrow_entry=1), 'no --narrow-match'),
                (dict(narrow_entry=1, narrow_match='a|c'), 'not a /regex/'), (dict(replace_entry=2), 'duplicate of another entry')):
    try:
        QA.change({'qa': [E('A'), E('B')]}, E('A'), **kw); check('refused: ' + why, False)
    except ValueError:
        pass
check('overlap_lines names both directions', len(QA.overlap_lines({'catches_it': [{'n': 1, 'q': 'a', 'answer': 'x'}],
                                                                    'it_catches': [{'n': 2, 'q': 'b', 'match': '/b/'}]})) == 2)
check('overlap_lines: none → []', QA.overlap_lines({'catches_it': [], 'it_catches': []}) == [])
# the case that started it (prefetch 11-08 / 11-10): an older entry whose pick misses this form's list no longer blocks
t = [E('Current school', match='/current school/i', pick=['/^University of Illinois$/i'], text='University of Illinois'),
     E('Current school or university:', pick=['/^(the )?university of chicago/i'], text='University of Chicago')]
a = answer(t, {'label': 'Current school or university:', 'type': 'select', 'options': ['University of Chicago', 'Other']})
check('newer entry answers when the older misses', a and a.get('rule') == 'qa:2' and a.get('value') == 'University of Chicago', a)
a = answer(t, {'label': 'Current school or university:', 'type': 'select', 'options': ['Northwestern', 'Other']})
check('all miss → the newest catching entry\'s miss', a and a.get('status') == 'unknown' and a.get('rule') == 'qa:2', a)
p1 = [E('What is your work authorization status?', pick=['/^f1 \\/ stem opt$/i'], text='^f1 \\/ stem opt$')]
a = answer(p1, {'label': 'What is your work authorization status?', 'type': 'text', 'options': []})
check('a pattern-only answer is never typed into a box without options (Simon 11-10)', a and a.get('status') == 'unknown', a)
a = answer(p1, {'label': 'What is your work authorization status?', 'type': 'select', 'options': ['US Citizen', 'F1 / STEM OPT']})
check('… but picks from a list', a and a.get('value') == 'F1 / STEM OPT', a)
check('whole-table listing finds the pair', len(QA.overlaps(profile(t))) == 1)
print('ALL PASS' if not bad else f'{bad} FAILED')
sys.exit(1 if bad else 0)
