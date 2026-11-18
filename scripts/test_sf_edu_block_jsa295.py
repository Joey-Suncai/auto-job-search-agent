#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sf_edu_block_jsa295_cases.json, spec sf_edu_block_jsa295_spec.md)
against the SuccessFactors education-row pieces of JSA-295 (Harwynpell 2026-11-10): sf_background.canon_label (new labels
"School/Institution Name", "Education Type", "Degree Achieved", "Major (Legacy)"), sf_background.other_school_box (the
"If other, enter School / Institution Name" companion), run_successfactors.question_label for a checkbox labelled only
"Acknowledgement", and canon.audit accepting School = "Other" when the row's "If other" box holds his school.
Also the major list (sf_major_other_jsa295_cases.json): sf_combo_edu.major_choice / other_major_box. Verdicts in
<name>_verdicts.json.
    python3 scripts/test_sf_edu_block_jsa295.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
sys.path.insert(0, os.path.join(HERE, '..', 'config'))
import sf_background as B  # noqa: E402
import run_successfactors as S  # noqa: E402
import canon  # noqa: E402
import sf_combo_edu as CE  # noqa: E402


def run(c):
    i = c['input']
    if c['fn'] == 'label_key':
        return B.canon_label(i['label'], 'edu')
    if c['fn'] == 'other_school_box':
        return B.other_school_box(i['fields'])
    if c['fn'] == 'question_label':
        return S.question_label(i['label'], i.get('rows'), i.get('kind'))
    if c['fn'] == 'school_other_ok':
        recs = [dict(r, type='combo' if not canon.re.search(r'\bother\b', r['label'], canon.re.I) else 'text', required=True) for r in i['records']]
        bad = [m['label'] for m in canon.audit(recs) if m['key'] == 'school']
        return [r['label'] for r in i['records'] if r['label'][:120] in bad]
    if c['fn'] == 'major_choice':
        return list(CE.major_choice(i['options'], i['major'], i['has_box']))
    if c['fn'] == 'other_major_box':
        return CE.other_major_box(i['fields'])
    raise ValueError(c['fn'])


def main():
    cases, verdicts = [], {}
    for name in ('sf_edu_block_jsa295', 'sf_major_other_jsa295'):   # + the major list (Joey 2026-11-11: Other + the major typed)
        cs = json.load(open(os.path.join(HERE, 'test_cases', name + '_cases.json')))
        cases += cs['cases'] if isinstance(cs, dict) else cs
        vp = os.path.join(HERE, 'test_cases', name + '_verdicts.json')
        verdicts.update(json.load(open(vp)) if os.path.exists(vp) else {})
    bad = 0
    for c in cases:
        try:
            got = run(c)
        except Exception as e:
            got = f'{type(e).__name__}: {e}'
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why'][:140]); continue
        bad += 1; print('FAIL ', c['name'], c['fn'], 'got', repr(got)[:120], 'want', repr(c['expect'])[:120], '|', json.dumps(c['input'])[:200])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
