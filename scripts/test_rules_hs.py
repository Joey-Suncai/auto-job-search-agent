#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/rules_hs_cases.json) against rule `hs_diploma`
(high school diploma = Yes, Nevwynost 2026-11-04). Verdicts in rules_hs_verdicts.json.
    python3 scripts/test_rules_hs.py"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'rules_hs_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'rules_hs_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    qs = [{'key': str(i), 'label': c['label'], 'type': 'radio', 'options': ['Yes', 'No']} for i, c in enumerate(cases)]
    r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                       input=json.dumps(qs), capture_output=True, text=True)
    ans = json.loads(r.stdout)
    bad = 0
    for i, c in enumerate(cases):
        a = ans.get(str(i)) or {}
        got = ('Yes' if a.get('value') == 'Yes' else 'other') if a.get('rule') == 'hs_diploma' else 'none'
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', got, a.get('rule'), a.get('value'), 'want', c['expect'], '|', c['label'])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
