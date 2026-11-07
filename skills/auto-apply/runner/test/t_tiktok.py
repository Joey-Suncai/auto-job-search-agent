#!/usr/bin/env python3
"""run_tiktok.py pure helpers vs DeepSeek-written cases (rule 13: spec → DeepSeek cases → Claude judges).
    python3 skills/auto-apply/runner/test/t_tiktok.py        # exit 1 on a disagreement not explained in the verdicts file
Cases: scripts/test_cases/tiktok_runner_cases.json (spec tiktok_runner_spec.md) · verdicts: tiktok_runner_verdicts.json;
tiktok_projects_cases.json (spec tiktok_projects_spec.md, project_plan, JSA-100) · verdicts: tiktok_projects_verdicts.json."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..'))
import run_tiktok as rt  # noqa: E402

TC = os.path.join(ROOT, 'scripts', 'test_cases')
SETS = [('tiktok_runner_cases.json', 'tiktok_runner_verdicts.json'), ('tiktok_projects_cases.json', 'tiktok_projects_verdicts.json')]


def check(case):
    fn = getattr(rt, case['fn'])
    got = fn(*case['args'])
    exp = case['expect']
    if case['fn'].endswith('_plan'):
        plan, problems = got
        want_plan = exp.get('plan', [])
        if len(plan) != len(want_plan):
            return False, f'plan {plan} != {want_plan}'
        for g, w in zip(plan, want_plan):
            diff = {k: (g.get(k), v) for k, v in w.items() if g.get(k) != v}
            if diff:
                return False, f'plan item differs {diff}'
        if 'problems_count' in exp and len(problems) != exp['problems_count']:
            return False, f'{len(problems)} problems {problems} != {exp["problems_count"]}'
        for m in exp.get('problems_mention', []):
            if not any(str(m).lower() in p.lower() for p in problems):
                return False, f'no problem mentions {m!r}: {problems}'
        return True, ''
    return got == exp, f'{got!r} != {exp!r}'


def main():
    cases, verdicts = [], {}
    for cf, vf in SETS:
        cases += json.load(open(os.path.join(TC, cf), encoding='utf-8'))
        if os.path.exists(os.path.join(TC, vf)):
            verdicts.update(json.load(open(os.path.join(TC, vf), encoding='utf-8')))
    fail = 0
    for c in cases:
        try:
            ok, why = check(c)
        except Exception as e:
            ok, why = False, f'{type(e).__name__}: {e}'
        if ok:
            print('PASS', c['name'])
        elif c['name'] in verdicts:
            print('CASE', c['name'], '— verdict:', verdicts[c['name']][:90])
        else:
            fail += 1
            print('FAIL', c['name'], '—', why)
    print(f'{len(cases)} cases · fails {fail}')
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
