#!/usr/bin/env python3
"""Harness for canon.check('immigration_status', …) (rule 13): DeepSeek cases, Claude's verdicts in imm_answer_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config')); import jsa_profile; jsa_profile.use_fixture_if_no_user()   # fresh clone: F-1 test fixture (JSA-086)
import canon
cases = json.load(open(os.path.join(HERE, 'test_cases', 'imm_answer_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'imm_answer_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = canon.check('immigration_status', c['answer'])[0]
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['answer'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
