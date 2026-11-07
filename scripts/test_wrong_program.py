#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/wrong_program_cases.json) against ds_materials.wrong_program — the
program is "Applied Data Science", never plain "Data Science" (2026-11-04). Verdicts in wrong_program_verdicts.json.
    python3 scripts/test_wrong_program.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts'))
import ds_materials as D  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'wrong_program_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'wrong_program_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = D.wrong_program(c['text'])
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', got, 'want', c['expect'], '|', c['text'][:110])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
