#!/usr/bin/env python3
"""SuccessFactors register form (JSA-335): run_successfactors.option_answer — a radio group with no readable question
(Arthrex 11-12) is answered only when exactly one option matches exactly one saved pick pattern (answers.profile_visibility).
DeepSeek wrote the cases from scripts/test_cases/sf_option_answer_spec.md (rule 13); disagreements judged in
sf_option_answer_verdicts.json. Also checks the real Arthrex options against the real saved pattern. Prints `N/M ok`.
    python3 scripts/test_sf_option_answer.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_successfactors as R  # noqa: E402

REAL = {'name': 'arthrex_1112_real', 'args': {'options': [
    'Any Arthrex recruiter worldwide. All recruiters within Arthrex can potentially see your profile and approach you for other positions.',
    'Only recruiters in my region. Only recruiters in the region of the position I apply for can see my profile.'],
    'saved': {'profile_visibility': ['/^any\\b.{0,80}\\brecruiters?\\b.{0,30}\\bworldwide\\b/i']}},
    'expect': ['Any Arthrex recruiter worldwide. All recruiters within Arthrex can potentially see your profile and approach you for other positions.',
               'answers.profile_visibility.pick (option content)']}


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_option_answer_cases.json')))
    cases = (cases['cases'] if isinstance(cases, dict) else cases) + [REAL]
    vp = os.path.join(HERE, 'test_cases', 'sf_option_answer_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    ok, bad = 0, []
    for c in cases:
        v = verdicts.get(c['name'])
        if v and v.get('skip'):
            ok += 1; continue
        exp = v['expect'] if v and 'expect' in v else c['expect']
        g = R.option_answer(c['args'].get('options'), c['args'].get('saved'))
        g = list(g) if g else None
        if g == exp:
            ok += 1
        else:
            bad.append((c['name'], exp, g))
    for n, e, g in bad:
        print(f'FAIL {n}\n  expect {e!r}\n  got    {g!r}')
    print(f'{ok}/{len(cases)} ok')
    sys.exit(0 if not bad else 1)


if __name__ == '__main__':
    main()
