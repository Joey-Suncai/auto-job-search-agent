#!/usr/bin/env python3
"""JSA-292 (rule 13): DeepSeek-written cases (test_cases/jsa292_whole_read_fp_cases.json, spec …_spec.md) for whole_read.block_context /
same, plus the real false stops of the 2026-11-10 replay (Talkelsev "School", Protective "major and minor"). Verdicts:
jsa292_whole_read_fp_verdicts.json.   python3 scripts/test_jsa292_whole_read_fp.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path[:0] = [os.path.join(ROOT, 'skills/auto-apply/runner'), os.path.join(ROOT, 'scripts'), os.path.join(ROOT, 'config')]
import whole_read as W  # noqa: E402
vp = os.path.join(HERE, 'test_cases', 'jsa292_whole_read_fp_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa292_whole_read_fp_cases.json')))
bad = 0
for c in cases:
    got = W.block_context(c['label'], c['context']) if c['kind'] == 'context' else W.major_lenient(c.get('label') or 'What is your major?', c['a'], c['b'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', {k: c[k] for k in c if k in ('label', 'context', 'a', 'b')})
n = len(cases)


def check(name, ok, *info):
    global bad, n
    n += 1
    if not ok:
        bad += 1; print('FAIL', name, *info)


check('Talkelsev: School after a High School question has no context', W.block_context('School', ['High School Name', 'Graduation year']) == [])
check('real: Protective major and minor', W.major_lenient('What is your major and minor/concentration?', 'Data Science', 'Applied Data Science | None'))
check('real: High School name is not the rule school', not W.same('University of Chicago', 'Springtown No.2 High School', []))
check('prompt for School shows no previous-block context', 'High School Name' not in W.prompt({'label': 'School', 'context': ['High School Name']}, 'facts'))
check('same() itself is unchanged: no containment', not W.same('Data Science', 'Applied Data Science', []))
for a, b in (('I do not require sponsorship', 'require sponsorship'), ('Not a veteran', 'a veteran'), ('Hyde Park', 'Hyde Park Investment Services'),
             ('Master of Science', 'Master of Science in Data Science'), ('May 2024', 'May 2024 2025'), ('Yes | None', 'Yes'), ('Computer Science', 'Computer Science and Economics')):
    check(f'review: {a!r} vs {b!r} is not lenient on a non-major label', not W.major_lenient('Are you authorized to work?', a, b))
check('review: negation inside a major is not lenient', not W.major_lenient('Major', 'Data Science', 'Not Data Science'))
check('review: a block starter with options keeps the last context line', W.block_context('Company', ['Are you currently employed?'], True) == ['Are you currently employed?'])
print(f'JSA-292: {n} cases · {len(verdicts)} verdicts · open disagreements {bad}')
sys.exit(1 if bad else 0)
