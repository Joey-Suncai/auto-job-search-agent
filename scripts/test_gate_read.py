#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/gate_read_cases.json, from gate_read_spec.md) against
gate_run.read() (JSA-046). Verdicts for disagreements: gate_read_verdicts.json.    python3 scripts/test_gate_read.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import gate_run as G  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'gate_read_cases.json')))
    vp = os.path.join(HERE, 'test_cases', 'gate_read_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        loads = []
        def load(u):
            loads.append(u); return {'status': (c.get('load') or {}).get(u, 'unreadable'), 'from': u}
        r = G.read(c['row'], load)
        if r['from'] == c['expect_from'] and loads == c['expect_loads']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], f"got from {r['from']!r} loads {loads} want {c['expect_from']!r} {c['expect_loads']}")
    print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
