#!/usr/bin/env python3
"""DeepSeek cases (scripts/test_cases/prep_fix150_cases.json): plan_build.load_open_answers, canon.classify (school),
prep_batch.FACT_FORMAT (JSA-150). Verdicts in prep_fix150_verdicts.json."""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import plan_build as PB, canon as C, prep_batch as P  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'prep_fix150_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'prep_fix150_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    a = c['args']
    if c['fn'] == 'open_answers':
        d = tempfile.mkdtemp(); open(os.path.join(d, 'open_answers.md'), 'w').write(a['text'])
        got = [list(x) for x in PB.load_open_answers(d)]
    elif c['fn'] == 'canon_school':
        got = C.classify(a['label']) == 'school'
    else:
        got = bool(P.FACT_FORMAT.search(a['label']))
    if got == c['expect']:
        print('PASS ', c['name']); continue
    if (verdicts.get(c['name']) or {}).get('verdict') == 'case':
        print('CASE ', c['name'], '—', verdicts[c['name']]['why']); continue
    bad += 1; print('FAIL ', c['name'], '\n   got ', got, '\n   want', c['expect'])
print(f'{len(cases) - bad}/{len(cases)} ok'); sys.exit(1 if bad else 0)
