#!/usr/bin/env python3
"""DeepSeek cases (scripts/test_cases/sync_testdata_cases.json) for scripts/store/sync_results.test_data (JSA-146)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store'))
import sync_results as S  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'sync_testdata_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'sync_testdata_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = S.test_data(c['cx'], c['runner'])
    if got == c['expect']:
        print('PASS ', c['name']); continue
    if (verdicts.get(c['name']) or {}).get('verdict') == 'case':
        print('CASE ', c['name']); continue
    bad += 1; print('FAIL ', c['name'], 'got', got, 'want', c['expect'])
print(f'{len(cases) - bad}/{len(cases)} ok'); sys.exit(1 if bad else 0)
