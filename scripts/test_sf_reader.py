#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sf_reader_cases.json) against eligibility_fetch.SF_URL and
sf_text (SuccessFactors career-site pages in the gate, JSA-092). Verdicts in sf_reader_verdicts.json.
    python3 scripts/test_sf_reader.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import eligibility_fetch as F  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_reader_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_reader_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = bool(F.SF_URL.search(c['args']['url'])) if c['fn'] == 'sf_url' else F.sf_text(c['args']['html'])
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', json.dumps(got)[:200], 'want', json.dumps(c['expect'])[:200])
    rc = json.load(open(os.path.join(HERE, 'test_cases', 'sf_route_cases.json')))      # routing (Built In excluded)
    for c in (rc['cases'] if isinstance(rc, dict) else rc):
        cases.append(c); got = F.sf_route(c['url'])
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', got, 'want', c['expect'], '|', c['url'])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
