#!/usr/bin/env python3
"""Harness for cert_supply.select (rule 13): DeepSeek cases, Claude's verdicts in cert_supply_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import cert_supply, resolve_builtin as RB
cases = json.load(open(os.path.join(HERE, 'test_cases', 'cert_supply_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'cert_supply_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    ctx = {'blocked': {RB.company_key(b) for b in c.get('blocked') or []}, 'blocked_boards': set(c.get('blocked_boards') or []), 'known': set(c.get('known') or []),
           'flags': lambda p, f=c.get('flags') or []: f}
    got = list(cert_supply.select(c['post'], ctx))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['post'].get('title'), '|', c['post'].get('location'))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
