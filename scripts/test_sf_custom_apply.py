#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sf_custom_apply_cases.json, spec sf_custom_apply_spec.md) against
run_successfactors.custom_apply_widget: a job page whose SAP apply link is only hidden and whose visible "Apply now" is a
web component opens the company's own wizard (careers.knorr-bremse.com, KB Signaling 11-05) → stop at once with a clear
reason instead of two 10 s click timeouts (JSA-222). Verdicts in sf_custom_apply_verdicts.json.
    python3 scripts/test_sf_custom_apply.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import run_successfactors as R  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_custom_apply_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_custom_apply_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = R.custom_apply_widget(c['args'].get('info'))
        except Exception as e:
            got = f'RAISES {type(e).__name__}: {e}'
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', got, 'want', c['expect'], json.dumps(c['args'])[:200])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
