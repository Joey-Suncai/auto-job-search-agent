#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/successfactors_cases.json) against run_successfactors' pure helpers
(JSA-092): parse_job, clean_label, attached_name, OTHER_TEXT. Verdicts in successfactors_verdicts.json.
    python3 scripts/test_successfactors.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_successfactors as R  # noqa: E402


def call(c):
    a = c['args']
    if c['fn'] == 'parse_job': return R.parse_job(a['url'])
    if c['fn'] == 'clean_label': return R.clean_label(a['text'])
    if c['fn'] == 'attached_name': return R.attached_name(a['text'], a['index'])
    return bool(R.OTHER_TEXT.search(a['label']))


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'successfactors_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'successfactors_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = call(c)
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', json.dumps(got)[:200], 'want', json.dumps(c['expect'])[:200], '|', json.dumps(c['args'])[:150])
    need = ['READ', 'READ_EXTRA', 'EDU_ROWS', 'DOC_RX', 'DONE', 'OTHER_TEXT', 'IF_FOLLOW', 'plan', 'clean_label', 'combo_set', 'combo_options',
            'radio_set', 'date_set', 'fill_education', 'fill_account', 'upload', 'sign_in', 'submit', 'settle', 'readback']   # a bad edit once dropped EDU_ROWS
    gone = [n for n in need if not hasattr(R, n)]
    if gone:
        bad += 1; print('FAIL  missing in run_successfactors:', gone)
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
