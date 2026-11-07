#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sr_followup_cases.json) against rule citizenship_country
(answer_rules.js) and run_smartrecruiters.IF_OTHER (optional follow-ups stay empty) — Kelrosros 2026-11-04.
Verdicts in sr_followup_verdicts.json.
    python3 scripts/test_sr_followup.py"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUN)
import run_smartrecruiters as R  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sr_followup_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sr_followup_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    qs = [{'key': str(i), 'label': c['label'], 'type': 'select', 'options': ['China', 'China (PRC, including Hong Kong and Macau)', 'Canada', 'None of these', 'Yes', 'No']}
          for i, c in enumerate(cases) if c['fn'] == 'citizenship']
    r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                       input=json.dumps(qs), capture_output=True, text=True)
    ans = json.loads(r.stdout)
    bad = 0
    for i, c in enumerate(cases):
        got = (ans.get(str(i)) or {}).get('rule') == 'citizenship_country' if c['fn'] == 'citizenship' else bool(R.IF_OTHER.search(c['label']))
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', got, 'want', c['expect'], '|', c['label'])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
