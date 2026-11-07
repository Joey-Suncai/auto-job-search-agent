#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/already_submitted_cases.json) against run_form.already_submitted
and posting_key (JSA-145). Verdicts in already_submitted_verdicts.json.
    python3 scripts/test_already_submitted.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_form as R  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'already_submitted_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'already_submitted_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        p = os.path.join(tempfile.mkdtemp(), 'results.jsonl')
        if c.get('lines') is not None:
            open(p, 'w').write(''.join(l + '\n' for l in c['lines']))
        got = R.already_submitted(c['folder'], p)
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', got, 'want', c['expect'])
    pk = json.load(open(os.path.join(HERE, 'test_cases', 'posting_key_cases.json')))   # posting_key (same JSA)
    po = json.load(open(os.path.join(HERE, 'test_cases', 'posting_key_oracle_cases.json')))   # Oracle (JSA-147)
    pk = (pk['cases'] if isinstance(pk, dict) else pk) + (po['cases'] if isinstance(po, dict) else po)
    for c in (pk['cases'] if isinstance(pk, dict) else pk):
        got = R.posting_key(c['url']); cases.append(c)
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', got, 'want', c['expect'])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
