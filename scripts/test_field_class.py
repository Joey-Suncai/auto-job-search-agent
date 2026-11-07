#!/usr/bin/env python3
"""Harness for scripts/field_class.py (Joey 2026-11-05 critical / non-critical split, rule 13): DeepSeek cases from
test_cases/field_class_spec.md; Claude's verdicts in test_cases/field_class_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from field_class import field_class  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'field_class_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'field_class_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = field_class(c['label'])
    if got != (c['expect_class'], c.get('expect_group') or '') and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', (c['expect_class'], c.get('expect_group')), '|', c['label'][:100])
print(f'{len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
