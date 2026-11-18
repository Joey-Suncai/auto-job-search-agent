#!/usr/bin/env python3
"""JSA-240 (rule 13): DeepSeek-written cases (test_cases/jsa240_prefetch_audit_cases.json, spec …_spec.md) for audit_prefetch.verdict /
audit, plus real suggestion-vs-answer pairs from the 2026-11-12..17 sheets, and the run() report on a temp data home.
Verdicts: jsa240_prefetch_audit_verdicts.json.   python3 scripts/test_jsa240_prefetch_audit.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit_prefetch as A  # noqa: E402
vp = os.path.join(HERE, 'test_cases', 'jsa240_prefetch_audit_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa240_prefetch_audit_cases.json')))
bad = 0
for c in cases:
    if c['kind'] == 'verdict':
        got = A.verdict(c['suggestion'], c['joey'], c.get('options') or [])
    else:
        r = A.audit(c['rows']); e = c['expect']
        got = {k: r[k] for k in e if k != 'disagreeing'}
        got['disagreeing'] = [d['question'] for d in r['disagreeing']] if 'disagreeing' in e else None
        if 'disagreeing' not in e:
            got.pop('disagreeing')
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
n = len(cases)


def check(name, ok, *info):
    global bad, n
    n += 1
    if not ok:
        bad += 1; print('FAIL', name, *info)


# real pairs: sheet 2026-11-17 suggestions vs Joey's saved answers
check('P14 Chicago, Illinois, United States agrees', A.verdict('Chicago, Illinois, United States', 'Chicago, Illinois, United States') == 'agree')
check('P10 industry experience: suggestion ASK, Joey None → asked', A.verdict('ASK', 'None', ['None', 'Less than 3 years']) == 'asked')
check('P9 SMS consent Yes / Yes', A.verdict('Yes', 'Yes', ['Yes', 'No']) == 'agree')
check('Yes vs "Yes, I do" picks the same option', A.verdict('Yes', 'Yes, I do', ['Yes, I do', 'No, I do not']) == 'agree')
check('different answers disagree', A.verdict('No', 'Yes', ['Yes', 'No']) == 'disagree')
# run(): a temp data home with one suggestions file and a profile qa
home = tempfile.mkdtemp(prefix='jsa240_')
for d in ('config', 'data/forms'):
    os.makedirs(os.path.join(home, d))
base = json.load(open(os.path.join(HERE, '..', 'config', 'profile.example.json')))
base['qa'] = [{'q': 'Are you currently employed?', 'text': 'No', 'source': 'Joey 2026-11-17 (prefetch)', 'added': '2026-11-17'},
              {'q': 'Derived one', 'text': 'No', 'source': 'Joey 2026-11-17 (prefetch)', 'added': '2026-11-17'}]
json.dump(base, open(os.path.join(home, 'config', 'profile.json'), 'w'))
today = '2026-11-17'
with open(os.path.join(home, 'data', 'forms', 'suggestions.jsonl'), 'w') as f:
    for q, s in (('Are you currently employed?', 'Yes'), ('Unanswered question', 'Maybe'), ('Derived one', 'No')):
        f.write(json.dumps({'date': today, 'sheet': 'prefetch-2026-11-17', 'question': q, 'options': ['Yes', 'No'] if q.startswith('Are') else [], 'suggestion': s, 'fact': 'x', 'derived': q == 'Derived one'}) + '\n')
os.environ['JSA_HOME'] = home
import importlib, paths
importlib.reload(paths)
from datetime import date
A.run(7, date(2026, 11, 17))
rep = open(os.path.join(home, 'data', 'forms', 'audit_2026-11-17.md')).read()
check('report lists the disagreement and counts, derived block apart', 'disagree 1' in rep and 'open 1' in rep and 'derived block apart: agree 1' in rep and 'suggested **Yes**' in rep and 'Joey **No**' in rep, rep)
print(f'JSA-240: {n} cases · {len(verdicts)} verdicts · open disagreements {bad}')
sys.exit(1 if bad else 0)
