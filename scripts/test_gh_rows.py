#!/usr/bin/env python3
"""Harness for run.gh_rows (rule 13, JSA-196): DeepSeek cases from test_cases/gh_rows_spec.md, verdicts in
test_cases/gh_rows_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run as RUN  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'gh_rows_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'gh_rows_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = RUN.gh_rows(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got)[:300], '| expect', json.dumps(c['expect'])[:300])
# a fill failure verify.js did not list (field_problems) is not confirmed either
rows = RUN.gh_rows([{'key': 'a', 'label': 'A', 'answer': 'x', 'status': 'ok'}, {'key': 'b', 'label': 'B', 'answer': 'y', 'status': 'ok'}], [], {'b': 'fill failed'})
if [r['ok'] for r in rows] != [True, False] or rows[1]['page'] != '':
    bad += 1; print('DISAGREE field_problems row', rows)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
