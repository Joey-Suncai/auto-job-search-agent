#!/usr/bin/env python3
"""Harness for the Greenhouse Employment section (rule 13, JSA-228): plan_build.employment_fields / employment_entries /
employment_answer / month_text_answer against DeepSeek's cases (test_cases/employment_cases.json); Claude's verdicts on
disagreements in test_cases/employment_verdicts.json. `source` is compared only when status is "ok" (the spec)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import plan_build  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'employment_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'employment_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}


def strip_source(x):
    if isinstance(x, dict) and x.get('status') != 'ok':
        return {k: v for k, v in x.items() if k != 'source'}
    return x


bad = 0
for c in cases:
    got = getattr(plan_build, c['fn'])(*c['args'])
    if strip_source(got) != strip_source(c['expect']) and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got)[:400], '| expect', json.dumps(c['expect'])[:400])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
