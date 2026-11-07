#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sf_background_cases.json) against sf_background.bg_plan — the
SuccessFactors Previous Employment / Formal Education planner (Morbrapell 2026-11-04). The facts come from the spec
(sf_background_spec.md), not from config, so the cases stay fixed. Verdicts in sf_background_verdicts.json.
    python3 scripts/test_sf_background.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import sf_background as B  # noqa: E402

WORK = [{'match': 'hyde park', 'Job Title': 'Business Analyst Intern', 'Company': 'Hyde Park Investment Services, Inc.', 'Location': 'Champaign, Illinois',
         'From': '08/2025', 'To': '10/2025', 'current': False, 'Description': 'Hyde Park description'},
        {'match': 'frost', 'Job Title': 'Consulting Assistant Intern', 'Company': 'Frost & Sullivan', 'Location': 'Shanghai, China',
         'From': '06/2024', 'To': '08/2024', 'current': False, 'Description': 'Frost description'}]
EDUS = [{'school': 'University of Chicago', 'match_re': 'chicago', 'level': 'master', 'major': 'Applied Data Science', 'start': '2026-09', 'end': '2027-12', 'current': True},
        {'school': 'University of Illinois Urbana-Champaign', 'match_re': 'illinois', 'level': 'bachelor', 'major': 'Economics', 'start': '2024-08', 'end': '2026-05'}]


def got_for(case):
    sec = case['section']
    p = B.bg_plan(sec, WORK, EDUS, today='2026-11')
    if p is None:
        return None, None
    rows = {}
    for r in p['rows']:
        row = sec['rows'][r['idx']]
        opts = {f['label']: f.get('options') or [] for f in row.get('fields') or []}
        vals = {'who': r['who']}
        for k, v in r['set'].items():
            vals[k] = B.pick_option(opts.get(k) or [], v) if opts.get(k) else v
        rows[str(r['idx'])] = vals
    return p, rows


def compare(case):
    exp = case.get('expect')
    p, rows = got_for(case)
    if exp is None:
        return [] if p is None else [f'expected not handled, got kind {p["kind"]}']
    if p is None:
        return ['expected handled, got None']
    bad = []
    if p['kind'] != exp.get('kind'):
        bad.append(f"kind {p['kind']} != {exp.get('kind')}")
    for k in ('add', 'unmatched', 'delete'):
        if list(p[k]) != list(exp.get(k) or []):
            bad.append(f'{k} {p[k]} != {exp.get(k)}')
    for idx, want in (exp.get('rows') or {}).items():
        have = rows.get(str(idx))
        if have is None:
            bad.append(f'row {idx} not set'); continue
        for lab, v in want.items():
            if str(have.get(lab)) != str(v):
                bad.append(f'row {idx} {lab}: {have.get(lab)!r} != {v!r}')
    extra = set(rows) - {str(i) for i in (exp.get('rows') or {})}
    if extra:
        bad.append(f'rows set that the case does not expect: {sorted(extra)}')
    return bad


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_background_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_background_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    fails = 0
    for c in cases:
        bad = compare(c)
        if not bad:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        fails += 1; print('FAIL ', c['name'], '|', '; '.join(bad)[:400])
    print(f'{len(cases) - fails}/{len(cases)} ok')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
