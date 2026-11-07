#!/usr/bin/env python3
"""Harness for plan_build.override_for (rule 13): DeepSeek cases, Claude's verdicts in override_for_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import plan_build
cases = json.load(open(os.path.join(HERE, 'test_cases', 'override_for_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'override_for_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    try:
        got = plan_build.override_for(c['field'], dict((k, v) for k, v in c['answers']), set(c.get('field_keys') or []))
        got = list(got) if got else None
    except Exception as e:
        got = f'ERROR {e}'
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
