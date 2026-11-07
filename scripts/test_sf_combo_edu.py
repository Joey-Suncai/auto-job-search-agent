#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sf_combo_education_cases.json) against the pure parts of
skills/auto-apply/runner/sf_combo_edu.py (education rows of School / Degree / Major combo lists, Erie 2026-11-04) and
run_successfactors.rebind. The facts come from the spec (sf_combo_education_spec.md), not from config, so the cases
stay fixed. Verdicts in sf_combo_education_verdicts.json. Plus a few fixed checks from the Erie page (form_check.json).
    python3 scripts/test_sf_combo_edu.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUN)
import sf_combo_edu as CE  # noqa: E402

A = {'school': 'University of Chicago', 'short': 'UChicago', 'match_re': 'chicago', 'level': 'master', 'degree_full': 'Master of Science',
     'major': 'Applied Data Science', 'start': '2026-09', 'end': '2027-12', 'current': True}
B = {'school': 'University of Illinois Urbana-Champaign', 'short': 'UIUC', 'match_re': 'illinois', 'level': 'bachelor', 'degree_full': 'Bachelor of Arts',
     'major': 'Economics', 'end': '2026-05'}
EDUS = [A, B]
ENT = {'A': A, 'B': B}


def rebind(row, fields, taken):
    # run_successfactors imports Playwright-free modules only at the top, but it needs config/paths; load it lazily
    import run_successfactors as R
    return R.rebind(row, fields, set(taken))


def got(c):
    fn, a = c['fn'], c.get('args') or {}
    if fn == 'group_rows':
        return [[f['key'] for f in r['fields']] for r in CE.group_rows(a['fields'])]
    if fn == 'row_plan':
        p = CE.row_plan(a['rows'], EDUS)
        return {'rows': {str(k): v for k, v in p['rows'].items()}, 'delete': p['delete'], 'add': p['add'], 'unmatched': p['unmatched']}
    if fn == 'pick_school':
        return list(CE.pick_school(a['options'], ENT[a['entry']]))
    if fn == 'pick_degree':
        return CE.pick_degree(a['options'], ENT[a['entry']])
    if fn == 'pick_major':
        return CE.pick_major(a['options'], a['major'])
    if fn == 'companion':
        return CE.companion(a['fields'])
    if fn == 'pick_status':
        return CE.pick_status(a['options'], ENT[a['entry']], '2026-11')
    if fn == 'rebind':
        r = rebind(a['row'], a['fields'], a.get('taken') or [])
        return r['key'] if r else None
    raise ValueError(fn)


def norm(x):
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items() if not (k in ('delete', 'add', 'unmatched') and not v) and not (k == 'rows' and not v)}
    if isinstance(x, list):
        return [norm(v) for v in x]
    return x


def fixed():
    """The Erie page itself (form_check.json, 11-04): three School / Degree / Major / Status / Comments rows."""
    bad = []
    fields = []
    for i in range(3):
        fields += [{'key': f's{i}', 'label': 'School', 'type': 'combo', 'value': ''}, {'key': f'd{i}', 'label': 'Degree', 'type': 'combo', 'value': ''},
                   {'key': f'm{i}', 'label': 'Major', 'type': 'combo', 'value': ''}, {'key': f't{i}', 'label': 'Status', 'type': 'combo', 'value': ''},
                   {'key': f'c{i}', 'label': 'Comments', 'type': 'text', 'value': ''}]
    fields += [{'key': 'h', 'label': 'How did you learn about this job opportunity?', 'type': 'combo', 'value': ''},
               {'key': 'o', 'label': 'If other, please specify', 'type': 'text', 'value': ''}]
    rows = CE.group_rows(fields)
    if [len(r['fields']) for r in rows] != [5, 5, 5]:
        bad.append(f'Erie rows {[len(r["fields"]) for r in rows]}')
    p = CE.row_plan([{'school': '', 'other': ''}] * 3, EDUS)
    if p != {'rows': {0: A['school'], 1: B['school']}, 'delete': [2], 'add': [], 'unmatched': []}:
        bad.append(f'Erie plan {p}')
    if CE.companion(rows[0]['fields']) != 'c0':
        bad.append('Erie companion')
    schools = ['A.T. Still University of Health Sciences (AZ / MO)', 'Loyola University Chicago (IL)', 'Other', 'There were no results']
    if CE.pick_school(schools, A) != ('Other', 'other'):
        bad.append(f'Erie school {CE.pick_school(schools, A)}')
    if CE.pick_school(['University of Illinois at Urbana-Champaign (IL)', 'Other'], B) != ('University of Illinois at Urbana-Champaign (IL)', 'match'):
        bad.append('UIUC with "at" and state')
    majors = ['Accounting', 'Computer Science', 'Economics', 'Information Systems', 'Other', 'Other Technology']
    if CE.pick_major(majors, A['major']) != 'Computer Science' or CE.pick_major(majors, B['major']) != 'Economics':
        bad.append('Erie majors')
    deg = ['Associates', 'Bachelors', 'Certificate', 'Doctorate', 'Masters', 'Other']
    if CE.pick_degree(deg, A) != 'Masters' or CE.pick_degree(deg, B) != 'Bachelors':
        bad.append('Erie degrees')
    st = ['Attending', 'Graduated', 'No Longer Attending']
    if CE.pick_status(st, A, '2026-11') != 'Attending' or CE.pick_status(st, B, '2026-11') != 'Graduated':
        bad.append('Erie status')
    sch = [{'key': 's0', 'label': 'School'}, {'key': 's1', 'label': 'School'}, {'key': 's2', 'label': 'School'}]
    if rebind({'key': 's1', 'label': 'School'}, sch, ['s0', 's2']) is not None or rebind({'key': 'gone', 'label': 'School'}, sch, []) is not None:
        bad.append('rebind collapsed the School rows')
    if (rebind({'key': 'old', 'label': 'Race'}, [{'key': 'new', 'label': 'Race'}], []) or {}).get('key') != 'new':
        bad.append('rebind lost a re-rendered single field')
    return bad


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_combo_education_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_combo_education_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    fails = 0
    for c in cases:
        try:
            g = got(c)
        except Exception as e:
            g = f'error {type(e).__name__}: {e}'
        if norm(g) == norm(c.get('expect')):
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why'][:140]); continue
        fails += 1; print('FAIL ', c['name'], '| got', json.dumps(g)[:200], '| want', json.dumps(c.get('expect'))[:200])
    es = json.load(open(os.path.join(HERE, 'test_cases', 'sf_empty_sections_cases.json')))   # empty education sections (Erie 11-05)
    for c in es:
        g = CE.sections_to_open(c['sections'])
        if g != c['expect']:
            fails += 1; print('FAIL  empty sections', c['name'], '| got', g, '| want', c['expect'])
    print(f'{len(es)} empty-section cases (DeepSeek, sf_empty_sections_spec.md)')
    fb = fixed()
    for b in fb:
        print('FAIL  fixed:', b)
    print(f'{len(cases) - fails}/{len(cases)} DeepSeek cases ok · fixed Erie checks ' + ('ok' if not fb else f'{len(fb)} failed'))
    return 1 if fails or fb else 0


if __name__ == '__main__':
    sys.exit(main())
