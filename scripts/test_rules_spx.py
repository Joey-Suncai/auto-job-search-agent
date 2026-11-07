#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/rules_spx_cases.json) against answer_rules.js for the rules
added on the SmartRecruiters batch (Bosch / Pelltalquin / Spring Venture 2026-11-04): degree / class-standing "Other", GPA bands,
MM/YY dates, hours, attestation boxes, enrollment status, employed-by-X, referral names, petition sponsorship, IDs.
Verdicts in rules_spx_verdicts.json.
    python3 scripts/test_rules_spx.py"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'rules_spx_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'rules_spx_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    qs = [{'key': str(i), 'label': c['label'], 'type': c.get('type') or 'text', 'options': c.get('options') or []} for i, c in enumerate(cases)]
    r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                       input=json.dumps(qs), capture_output=True, text=True)
    ans = json.loads(r.stdout)
    bad = 0
    for i, c in enumerate(cases):
        a = ans.get(str(i)) or {}
        got = str(a.get('value')) if a.get('status') == 'ok' and not a.get('leave') else 'none'
        if got.strip().lower() == str(c['expect']).strip().lower():
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got)[:60], a.get('rule'), 'want', repr(c['expect'])[:60], '|', c['label'][:90], c.get('options', [])[:5])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
