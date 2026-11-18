#!/usr/bin/env python3
"""DeepSeek-written cases (scripts/test_cases/role_library_cases.json) against role_library's pure functions (JSA-249,
rule 13). Disagreements need a verdict in scripts/test_cases/role_library_verdicts.json.
    python3 skills/resume-updater/scripts/test_role_library.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import role_library as R  # noqa: E402

TC = os.path.join(REPO, 'scripts', 'test_cases')


def close(a, b, tol=0.0011):
    return abs(float(a) - float(b)) <= tol


def run(c):
    fn = c['fn']
    if fn == 'matcher':
        got = bool(R.matcher(c['term']).search(c['text']))
        return got == bool(c['expect']), got
    if fn == 'specific':
        got = R.specific(c['phrase'])
        return got == bool(c['expect']), got
    if fn == 'split_req':
        got = R.split_req(c['text'])
        return got == (c['expect_required'], c['expect_preferred']), got
    if fn == 'select':
        got = R.select(c['jobs'], c['texts'], c['selector'])
        return got == sorted(set(c['expect'])), got
    if fn == 'stats':
        comps, _ = R.stats(c['texts'], R.compile_lexicon(c['lexicon']))
        by = {x['id']: x for x in comps}
        ok = True
        for cid, e in (c.get('expect') or {}).items():
            g = by.get(cid)
            if not g:
                return False, f'no competency {cid}'
            for k in ('df', 'req_share', 'weight'):
                if k in e and not close(g[k], e[k]):
                    ok = False
            kws = {k['term']: k for k in g['keywords']}
            for t, ke in (e.get('keywords') or {}).items():
                for k in ('df', 'req_share'):
                    if k in ke and (t not in kws or not close(kws[t][k], ke[k])):
                        ok = False
        if c.get('expect_order'):
            order = [x['id'] for x in comps if x['id'] in c['expect_order']]
            ok = ok and order == c['expect_order']
        return ok, {x['id']: (x['df'], x['req_share'], x['weight']) for x in comps}
    return False, f'unknown fn {fn}'


def main():
    cases = json.load(open(os.path.join(TC, 'role_library_cases.json'), encoding='utf-8'))
    cases += json.load(open(os.path.join(TC, 'role_library_specific_cases.json'), encoding='utf-8'))
    vp = os.path.join(TC, 'role_library_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            ok, got = run(c)
        except Exception as ex:
            ok, got = False, f'crash {type(ex).__name__}: {ex}'
        if ok:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '— judged:', v['why'][:110]); continue
        bad += 1
        print('DIFF ', c['name'], '|', c['fn'], '| got', str(got)[:160], '|', c.get('why', '')[:120])
    print(f'{len(cases)} cases, {bad} unresolved')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
