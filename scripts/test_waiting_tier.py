#!/usr/bin/env python3
"""JSA-404: the Tier column of the dashboard's "Waiting for you" table (cases: scripts/test_cases/waiting_tier_cases.json,
written by DeepSeek from waiting_tier_spec.md)."""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store'))
import joey_todo as J  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'waiting_tier_cases.json'), encoding='utf-8'))
verdicts_p = os.path.join(HERE, 'test_cases', 'waiting_tier_verdicts.json')
skip = set(json.load(open(verdicts_p))) if os.path.exists(verdicts_p) else set()
bad = []
for c in cases:
    if c['name'] in skip:
        continue
    rows = copy.deepcopy(c['rows']); before = copy.deepcopy(rows)
    got = J.add_tiers(rows, c.get('jobs'))
    if [r['tier'] for r in got] != c['expect']:
        bad.append(f"{c['name']}: {[r['tier'] for r in got]} != {c['expect']}")
    if rows != before:
        bad.append(f"{c['name']}: input rows modified")
    if [{k: v for k, v in r.items() if k != 'tier'} for r in got] != before:
        bad.append(f"{c['name']}: other fields changed")
print(f'waiting tier: {len(bad)} failure(s) in {len(cases)} cases')
for b in bad: print('FAIL', b)
sys.exit(1 if bad else 0)
