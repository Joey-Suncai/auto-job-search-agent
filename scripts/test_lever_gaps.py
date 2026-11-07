#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/lever_gaps_cases.json, from lever_gaps_spec.md) against
plan_build.lever_urls, prep_batch.optional_essay and the city_state answer rule (JSA-144). Verdicts in lever_gaps_verdicts.json.
    python3 scripts/test_lever_gaps.py"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUN)
import plan_build as PB  # noqa: E402
import prep_batch as P  # noqa: E402


def city_state(label, typ):
    q = [{'key': 'q', 'label': label, 'type': typ, 'options': []}]
    r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.join(RUN, '..', 'scripts', 'answer_rules.js')],
                       input=json.dumps(q), capture_output=True, text=True, timeout=60)
    a = json.loads(r.stdout or '{}').get('q') or {}
    return a.get('value') if a.get('status') == 'ok' and a.get('rule') == 'city_state' else None


def run(c):
    f, a = c['fn'], c['args']
    if f == 'lever_urls':
        return [{'key': x['key'], 'label': x['label'], 'required': x['required']} for x in PB.lever_urls(a['page'])]
    if f == 'optional_essay':
        return P.optional_essay(a['field'])
    if f == 'city_state':
        return city_state(a['label'], a.get('type', 'text'))
    raise ValueError(f)


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'lever_gaps_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'lever_gaps_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = run(c)
        except Exception as e:
            got = f'crash {type(e).__name__}: {e}'
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1
        print('FAIL ', c['name'], f'\n   got  {got!r}\n   want {c["expect"]!r}')
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
