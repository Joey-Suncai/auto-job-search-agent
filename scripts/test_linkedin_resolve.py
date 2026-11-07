#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/linkedin_resolve_cases.json, from linkedin_resolve_spec.md) against
skills/job-hunt-pipeline/scripts/linkedin_resolve.py (JSA-178). Claude judges every disagreement in
linkedin_resolve_verdicts.json ("case" = the case misread the spec, with the reason).
    python3 scripts/test_linkedin_resolve.py"""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import linkedin_resolve as R  # noqa: E402

CASE_FILES = [os.path.join(HERE, 'test_cases', f) for f in ('linkedin_resolve_cases.json', 'linkedin_resolve_b_cases.json', 'linkedin_resolve_c_cases.json')]
VERDICTS = os.path.join(HERE, 'test_cases', 'linkedin_resolve_verdicts.json')


def run(c):
    f, a = c['fn'], c['args']
    if f == 'company_link':
        return R.company_link(a['href'])
    if f == 'resolve':
        r = R.resolve(a['info'])
        return {k: r[k] for k in ('li_apply', 'apply_url', 'ats_url')}
    if f == 'apply_row':
        return R.apply_row(copy.deepcopy(a['row']), a['res'], a['li_url'], a['today'])
    if f == 'targets':
        return [list(t) for t in R.targets(a['rows'], a.get('wellfound_pages'), a.get('redo', False))]
    raise ValueError(f)


def main():
    cases = [c for f in CASE_FILES for c in json.load(open(f, encoding='utf-8'))]
    verdicts = json.load(open(VERDICTS, encoding='utf-8')) if os.path.exists(VERDICTS) else {}
    fails = 0
    for c in cases:
        try:
            g = run(c)
        except Exception as e:
            g = f'error {type(e).__name__}: {e}'
        if g == c['expect']:
            continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why'][:140]); continue
        fails += 1; print('FAIL ', c['name'], '| got', json.dumps(g, ensure_ascii=False)[:400], '| want', json.dumps(c['expect'], ensure_ascii=False)[:400])
    print(f'{len(cases)} cases · fails {fails}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
