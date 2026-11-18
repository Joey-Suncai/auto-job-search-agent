#!/usr/bin/env python3
"""DeepSeek-written cases (scripts/test_cases/gap_reserve_cases.json) for gap_reserve.py's pure functions — JSA-262,
rule 13. Disagreements need a verdict in scripts/test_cases/gap_reserve_verdicts.json.
    python3 skills/resume-updater/scripts/test_gap_reserve.py"""
import copy
import json
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import gap_reserve as GR  # noqa: E402

TCDIR = os.path.join(REPO, 'scripts', 'test_cases')
OWN = ('entry_not_on_master', 'not_new', 'no_gap_term')


def _fb(f):
    f = copy.deepcopy(f or {})
    f.setdefault('entries', [])
    f.setdefault('facts', [])
    f.setdefault('skills', {})
    f['skills'].setdefault('true', {})
    f['skills'].setdefault('not_true', [])
    for x in f['facts']:
        x.setdefault('skills', [])
    return f


def run(c):
    fn = c['fn']
    if fn == 'tags':
        got = [list(x) for x in GR.tags_for(c['spellings'], _fb(c['facts']))]
        return got == [list(x) for x in c['expect']], got
    if fn == 'gaps':
        g = GR.jd_gaps(c['jd'], c.get('title') or '', c['role'], _fb(c['facts']), c.get('page') or '', c.get('n') or 12)
        got = [{k: x[k] for k in ('term', 'jd_spelling', 'state', 'score', 'facts')} for x in g]
        want = [{k: (round(float(x[k]), 4) if k == 'score' else x[k]) for k in ('term', 'jd_spelling', 'state', 'score', 'facts')}
                for x in c['expect']]
        return got == want, got
    if fn == 'aggregate':
        rows = GR.aggregate(c['per_jd'], c['n_jds'])
        got = [{k: r[k] for k in ('term', 'jds', 'share', 'score', 'spellings', 'states', 'facts')} for r in rows]
        want = [{k: (round(float(x[k]), 4) if k in ('share', 'score') else x[k]) for k in ('term', 'jds', 'share', 'score', 'spellings', 'states', 'facts')}
                for x in c['expect']]
        return got == want, got
    if fn == 'deny':
        fb = _fb(c['facts'])
        removed = GR.deny(fb, c['spellings'], c['fact_id'])
        F = {f['id']: f['skills'] for f in fb['facts']}
        ok = removed == c['expect_removed']
        after = {}
        for k in (c.get('expect_skills') or {}):
            after[k] = F[k] if k in F else fb['skills']['true'] if k == 'skills.true' else fb['skills']['true'].get(k)
        ok = ok and after == (c.get('expect_skills') or {})
        return ok, [removed, after]
    if fn == 'candidates':
        smap = GR.spellings_map(c.get('role') or {})
        master = c['master']
        ents = {e['entry_id'] for e in master.get('entries') or []}
        known = {b['text'] for e in master.get('entries') or [] for b in e.get('bullets') or []} | {r['text'] for r in master.get('reserve') or []}
        got = []
        for cand in c['candidates']:   # the three own rules only (direction_master.check is tested elsewhere)
            got.append(own_rules(cand, ents, known, smap))
        return [sorted(x) for x in got] == [sorted(x) for x in c['expect_kinds']], got
    if fn == 'bank':
        got = GR.bank_insert(c['bank'], c['heading'], c['lines'])
        return got == c['expect'], got
    raise ValueError(f'unknown fn {fn}')


def own_rules(cand, ents, known, smap):
    """The kinds check_candidates reports for one candidate from its own rules (same code path, DM.check stubbed)."""
    import direction_master as DM
    real = DM.check
    DM.check = lambda *a, **k: []
    try:
        master = {'entries': [{'entry_id': e, 'bullets': []} for e in ents],
                  'reserve': [{'text': t, 'entry_id': None} for t in known]}
        errs = GR.check_candidates(master, [cand], None, None, smap)
    finally:
        DM.check = real
    return [k for k in OWN if any(f': {k} ' in e for e in errs)]


def main():
    cases = json.load(open(os.path.join(TCDIR, 'gap_reserve_cases.json'), encoding='utf-8'))
    vp = os.path.join(TCDIR, 'gap_reserve_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            ok, got = run(c)
        except Exception as ex:
            ok, got = False, f'crash:{type(ex).__name__}:{ex}'
        if ok:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '— judged:', v['why'][:100]); continue
        bad += 1
        print('DIFF ', c['name'], '| got', json.dumps(got, ensure_ascii=False)[:300], '|', c.get('why', '')[:200])
    print(f'gap_reserve: {len(cases)} cases, {bad} unresolved')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
