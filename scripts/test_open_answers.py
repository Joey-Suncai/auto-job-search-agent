#!/usr/bin/env python3
"""Harness for plan_build.load_open_answers (rule 13): DeepSeek-written cases in scripts/test_cases/open_answers_cases.json,
Claude's verdicts on disagreements in open_answers_verdicts.json."""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import plan_build
cases = json.load(open(os.path.join(HERE, 'test_cases', 'open_answers_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'open_answers_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    d = tempfile.mkdtemp()
    open(os.path.join(d, 'open_answers.md'), 'w', encoding='utf-8').write(c['text'])
    got = [list(x) for x in plan_build.load_open_answers(d)]
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '\n  got   ', got, '\n  expect', c['expect'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
