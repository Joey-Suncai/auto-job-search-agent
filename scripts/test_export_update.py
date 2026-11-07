#!/usr/bin/env python3
"""Harness for the public export's update mode (JSA-089, rule 13): export_public.parse_version / release_message /
preflight / stale_paths against DeepSeek cases in test_cases/export_update_cases.json; verdicts in export_update_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'public'))
import export_public as X  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'export_update_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'export_update_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f = c['fn']
    if f == 'parse_version':
        r = X.parse_version(c['v']); got = list(r) if r else None
    elif f == 'release_message':
        got = X.release_message(c['version'])
    elif f == 'preflight':
        got = X.preflight(**c['args'])
    else:
        got = X.stale_paths(c['clone_tracked'], c['exported'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', f, c['name'], '| got', repr(got)[:160], '| expect', repr(c['expect'])[:160])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
