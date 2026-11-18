#!/usr/bin/env python3
"""JSA-241 (rule 13): DeepSeek-written cases (test_cases/jsa241_merged_options_cases.json, spec …_spec.md) + the real P1 question of
the 2026-11-06 sheet ("現住城市": the United States list was cut off, qa_add could not save the answer) — merge_options() keeps every
option and the per-form lists; qa_add.check_shapes() accepts an answer found on ANY list; collect_batch.qa_args passes the lists as
JSON (an option may hold "|"). Verdicts: jsa241_merged_options_verdicts.json.   python3 scripts/test_jsa241_merged_options.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path[:0] = [os.path.join(ROOT, 'skills/auto-apply/scripts'), os.path.join(ROOT, 'skills/auto-apply/runner'), os.path.join(ROOT, 'config')]
import qa_add as QA, form_prefetch as FP, collect_batch as CB  # noqa: E402
BASE = json.load(open(os.path.join(ROOT, 'config', 'profile.example.json'), encoding='utf-8'))
TMP = tempfile.mkdtemp(prefix='jsa241_')
Q = 'In what city/town do you currently reside?'
bad = 0


def prof(entry):
    p = os.path.join(TMP, 'p.json'); json.dump(dict(BASE, qa=[entry]), open(p, 'w')); return p


def answerable(lists, pick):
    got = QA.check_shapes(Q, lists, prof(QA.entry(Q, pick=[pick], source='t')))
    return got.get('status') == 'ok'


def run(c):
    if c['kind'] == 'merge':
        o, s = FP.merge_options(c['lists'])
        return {'options': o, 'option_sets': s}
    return answerable(c['lists'], c['pick'])


vp = os.path.join(HERE, 'test_cases', 'jsa241_merged_options_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa241_merged_options_cases.json')))
for c in cases:
    got = run(c); exp = c['expect']
    if c['kind'] == 'merge':
        exp = {'options': exp['options'], 'option_sets': exp.get('option_sets')}
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', exp, '|', c['lists'])
n = len(cases)


def check(name, ok, *info):
    global bad, n
    n += 1
    if not ok:
        bad += 1; print('FAIL', name, *info)


# the real P1: a city list (company 1) and a country list (company 2, 200 entries, United States late in the list)
cities = ['Berlin, Germany', 'Texas, USA', 'Others']
countries = ['Country %d' % i for i in range(190)] + ['Finland', 'France', 'United States', 'Vietnam']
o, s = FP.merge_options([cities, countries, []])
check('P1 keeps United States, no cut', 'United States' in o and len(o) == len(cities) + len(countries), len(o))
check('P1 has both lists', s == [cities, countries])
check('P1: "United States" saves via the country list', answerable([cities, countries], '/^United States$/i'))
check('P1: the union alone also works', answerable([o], '/^United States$/i'))
check('an answer on no list is still refused', not answerable([cities, countries], '/^Mars$/i'))
args = CB.qa_args({'question': Q, 'options': o, 'option_sets': [cities, countries], 'answer': {'pick': '/^United States$/i'}}, 's')
check('qa_args: one --options-json per list', args.count('--options-json') == 2 and '--options' not in args, args[:6])
args = CB.qa_args({'question': 'Q', 'options': ['Yes (full-time) | はい', 'No'], 'answer': {'yes': True}}, 's')
check('qa_args: an option with | travels intact', json.loads(args[args.index('--options-json') + 1]) == ['Yes (full-time) | はい', 'No'], args)
check('same options in another order = one list', FP.merge_options([['A', 'B'], ['B', 'A']])[1] is None)
import subprocess
pp = prof(QA.entry('Chicago q', pick=['/Chicago/i'], source='t'))
r = subprocess.run([sys.executable, os.path.join(ROOT, 'skills/auto-apply/scripts/qa_add.py'), '--profile', pp, '--no-commit', '--q', 'Where2?', '--pick', '/Chicago/i',
                    '--options-json', '["Chicago","Austin"]', '--options-json', '["NYC","Boston"]'], capture_output=True, text=True)
check('qa_add warns when a list misses', 'warning' in r.stdout and '[2]' in r.stdout, r.stdout[-300:], r.stderr[-200:])
r = subprocess.run([sys.executable, os.path.join(ROOT, 'skills/auto-apply/scripts/qa_add.py'), '--profile', pp, '--no-commit', '--q', 'Where3?', '--text', 'x', '--options-json', '"Yes|No"'], capture_output=True, text=True)
check('qa_add refuses a non-list --options-json', r.returncode == 1 and 'JSON list' in r.stdout, r.stdout, r.stderr[-200:])
check('one list → no option_sets', FP.merge_options([['A', 'B'], ['A', 'B']])[1] is None)
print(f'JSA-241: {n} cases · {len(verdicts)} verdicts · open disagreements {bad}')
sys.exit(1 if bad else 0)
