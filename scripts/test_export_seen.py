#!/usr/bin/env python3
"""Harness for export_public.drop_private_lines (rule 13, JSA-085): DeepSeek cases, verdicts in export_seen_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'public'))
import export_public as X  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'export_seen_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'export_seen_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = X.drop_private_lines(c['text'], c['path'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', repr(got)[:120], '| expect', repr(c['expect'])[:120])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
