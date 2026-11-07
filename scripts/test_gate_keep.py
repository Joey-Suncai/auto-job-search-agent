#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/gate_keep_cases.json, from gate_keep_spec.md) against
eligibility_merge.apply_result() (JSA-054). Verdicts for disagreements: gate_keep_verdicts.json.
    python3 scripts/test_gate_keep.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import eligibility_merge as M  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'gate_keep_cases.json')))
    vp = os.path.join(HERE, 'test_cases', 'gate_keep_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        j = {k: v for k, v in (c.get('row') or {}).items() if v is not None}
        try:
            M.apply_result(j, c['result'], c['today'])
            d = [f'{k}: got {j.get(k)!r} want {v!r}' for k, v in c['expect'].items() if j.get(k) != v]
        except Exception as e:
            d = [f'crash {type(e).__name__}: {e}']
        if not d:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], '\n    ' + '\n    '.join(d))
    print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
