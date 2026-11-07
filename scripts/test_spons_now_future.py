#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/spons_now_future_cases.json) against both layers that answer a
sponsorship question — answer_rules.js (rule spons_now → No, spons_future → Yes) and canon.classify (sponsorship_now /
sponsorship_future). Nevnevcor 2026-11-04: "now or at any time after graduation" was answered No. Verdicts in
spons_now_future_verdicts.json.
    python3 scripts/test_spons_now_future.py"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUN)
import canon  # noqa: E402

RULE = {'spons_now': 'now', 'spons_future': 'future'}
CANON = {'sponsorship_now': 'now', 'sponsorship_future': 'future'}


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'spons_now_future_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'spons_now_future_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    qs = [{'key': str(i), 'label': c['label'], 'type': 'radio', 'options': ['Yes', 'No']} for i, c in enumerate(cases)]
    r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                       input=json.dumps(qs), capture_output=True, text=True)
    ans = json.loads(r.stdout)
    bad = 0
    for i, c in enumerate(cases):
        a = ans.get(str(i)) or {}
        rule = RULE.get(a.get('rule'), 'other') if a.get('status') == 'ok' else 'other'
        can = CANON.get(canon.classify(c['label']), 'other')
        exp = c['expect']
        ok_rule = rule == exp or (exp == 'other' and rule == 'other')
        ok_canon = can == exp or (exp == 'other' and can == 'other')
        if ok_rule and ok_canon:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], f'rule {rule} canon {can} want {exp}', '|', c['label'])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
