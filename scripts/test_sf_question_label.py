#!/usr/bin/env python3
"""SuccessFactors question text (JSA-232): run_successfactors.question_label — a field whose own label is only a
placeholder ("Please select one of the options", Ostlumcor 11-06) takes the question from the text-only row above it.
DeepSeek wrote the cases from scripts/test_cases/sf_question_label_spec.md (rule 13); disagreements judged in
sf_question_label_verdicts.json. Prints `N/M ok`.
    python3 scripts/test_sf_question_label.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_successfactors as R  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_question_label_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_question_label_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    ok, bad = 0, []
    for c in cases:
        g = R.question_label(c['label'], c.get('rows'))
        v = verdicts.get(c['name'])
        exp = v['expect'] if v and 'expect' in v else c['expect']
        if v and v.get('skip'):
            ok += 1; continue
        if g == exp:
            ok += 1
        else:
            bad.append((c['name'], c['label'], exp, g))
    for n, l, e, g in bad:
        print(f'FAIL {n}: label {l!r}\n  expect {e!r}\n  got    {g!r}')
    print(f'{ok}/{len(cases)} ok')
    sys.exit(0 if not bad else 1)


if __name__ == '__main__':
    main()
