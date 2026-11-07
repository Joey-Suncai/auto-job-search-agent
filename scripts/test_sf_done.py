#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sf_done_cases.json) against run_successfactors.done_text — a
success phrase counts only when it is new after Apply (Morbrapell 11-04: the form's intro "Thank you for your interest" was
read as a confirmation). Verdicts in sf_done_verdicts.json.
    ~/.job-agent-venv/bin/python scripts/test_sf_done.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_successfactors as S  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_done_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_done_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    fails = 0
    for c in cases:
        got = S.done_text(c['after'], c.get('before') or '')
        if got == bool(c['expect']):
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        fails += 1; print('FAIL ', c['name'], 'got', got, '| before', c.get('before', '')[:80], '| after', c['after'][:120])
    print(f'{len(cases) - fails}/{len(cases)} ok')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
