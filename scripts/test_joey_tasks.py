#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/joey_tasks_cases.json, from joey_tasks_spec.md) against
skills/auto-apply/runner/prep_batch.py joey_tasks / is_test_batch / joey_gate (JSA-141). Claude judges every
disagreement in joey_tasks_verdicts.json.
    python3 scripts/test_joey_tasks.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import prep_batch as P  # noqa: E402


def run(c):
    f, a = c['fn'], c['args']
    if f == 'joey_tasks':
        return P.joey_tasks({'needs_user': a.get('needs_user')})
    if f == 'is_test_batch':
        return P.is_test_batch(a['batch'])
    if f == 'joey_gate':
        return P.joey_gate(dict(a['row']), {'needs_user': a.get('needs_user')}, a['test'])
    raise ValueError(f)


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'joey_tasks_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'joey_tasks_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = run(c)
        except Exception as e:
            got = f'crash {type(e).__name__}: {e}'
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1
        print('FAIL ', c['name'], f'\n   got  {got!r}\n   want {c["expect"]!r}')
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
