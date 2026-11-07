#!/usr/bin/env python3
"""Harness for plan_build.education_entries + run_form.edu_same (rule 13, JSA-056): DeepSeek cases, verdicts in test_cases/education_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import plan_build, run_form  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'education_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'education_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    fn = plan_build.education_entries if c['fn'] == 'education_entries' else run_form.edu_same
    got = fn(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got)[:300], '| expect', json.dumps(c['expect'])[:300])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
