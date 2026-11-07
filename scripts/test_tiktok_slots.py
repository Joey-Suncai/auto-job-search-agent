#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/tiktok_slots_cases.json, from tiktok_slots_spec.md) against
skills/auto-apply/scripts/tiktok_slots.check() (JSA-097). Claude judges every disagreement and records it in
scripts/test_cases/tiktok_slots_verdicts.json (case name → {"verdict": "case", "why": …}); a disagreement without a
"case" verdict fails the run. Plus fixed checks of the prefilter / runner wiring.    python3 scripts/test_tiktok_slots.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts'))
import tiktok_slots as T  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'tiktok_slots_cases.json'), encoding='utf-8'))
    vp = os.path.join(HERE, 'test_cases', 'tiktok_slots_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = T.check(c['job'], c.get('apps') or [], c['today'])
        want = c['expect']
        keys = [k for k in ('allowed', 'counted', 'period', 'program') if k in want]
        if want.get('counted', got['counted']):
            keys += [k for k in ('used', 'remaining') if k in want]
        diff = {k: (want[k], got[k]) for k in keys if want[k] != got[k]}
        if not got['allowed'] and not ('2' in got['reason'] and got['period'] in got['reason']):
            diff['reason'] = got['reason']
        if not diff:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '— judged: case misreads the spec:', v['why'][:110]); continue
        bad += 1
        print('DIFF ', c['name'], '| want/got', diff)
    # fixed checks: the live tracker shape (J00109, Applied 2026-10-27) and the runner's banner comparison
    j109 = {'job_id': 'J00109', 'company': 'TikTok', 'title': 'Strategy Product Manager Intern', 'level': 'Internship',
            'status': 'Applied', 'applied_on': '2026-10-27', 'url': 'https://lifeattiktok.com/search/7670420287191517493'}
    one = {'company': 'ByteDance', 'title': 'Product Manager Intern', 'level': 'Internship', 'url': ''}
    fixed = [
        (T.check(one, [j109], '2026-11-03')['remaining'] == 1, '2026H2 intern: 1 left after J00109'),
        (not T.check(one, [j109, dict(j109, job_id='J2', company='ByteDance')], '2026-11-03')['allowed'], '3rd 2026H2 intern refused'),
        (T.check(one, [j109, dict(j109, job_id='J2')], '2027-01-02')['remaining'] == 2, '2027H1 starts fresh'),
        (T.check(dict(one, title='Product Manager - Project Intern'), [j109, dict(j109, job_id='J2')], '2026-11-03')['allowed'], 'Project Intern exempt'),
        (T.period_of('2026-06-30') == '2026H1' and T.period_of('2026-07-01') == '2026H2', 'period boundary'),
    ]
    sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
    import run_tiktok as R
    sl = T.check(one, [j109], '2026-11-03')
    fixed += [
        (R.banner_problem({'remaining': 0, 'project': 'x', 'limit': 2}, sl) != '', 'banner 0 vs tracker 1 → problem'),
        (R.banner_problem({'remaining': 1, 'project': 'x', 'limit': 2}, sl) == '', 'banner agrees → no problem'),
        (R.banner_problem(None, sl) == '', 'no banner (Project Intern) → no problem'),
    ]
    for ok, name in fixed:
        print('PASS ' if ok else 'FAIL ', 'fixed:', name); bad += 0 if ok else 1
    print(f'{len(cases)} cases + {len(fixed)} fixed, {bad} unresolved')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
