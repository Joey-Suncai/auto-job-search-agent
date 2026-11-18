#!/usr/bin/env python3
"""DeepSeek-written cases (scripts/test_cases/gap_report_cases.json) against gap_report.assess / missing_tools (JSA-253,
rule 13). Disagreements need a verdict in scripts/test_cases/gap_report_verdicts.json.
    python3 skills/resume-updater/scripts/test_gap_report.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import gap_report as G  # noqa: E402

TC = os.path.join(REPO, 'scripts', 'test_cases')


def run(c):
    if c['fn'] == 'missing_tools':
        got = [[t, round(df, 4)] for t, df in G.missing_tools(c['role'], c['facts'])]
        want = [[t, round(float(df), 4)] for t, df in c['expect']]
        return got == want, got
    kw = {k: c[k] for k in ('min_weight', 'proven_share') if c.get(k) is not None}
    rows = G.assess(c['role'], c['facts'], **kw)
    exp = c['expect']
    if len(rows) != len(exp):
        return False, [(r['id'], r['level']) for r in rows]
    for r, e in zip(rows, exp):
        if r['id'] != e['id'] or r['level'] != e['level']:
            return False, [(x['id'], x['level'], x['coverage']) for x in rows]
        if 'coverage' in e and abs(r['coverage'] - float(e['coverage'])) > 0.0011:
            return False, (r['id'], 'coverage', r['coverage'])
        if 'facts' in e and r['facts'] != e['facts']:
            return False, (r['id'], 'facts', r['facts'])
        if 'missing' in e and r['missing'] != e['missing']:
            return False, (r['id'], 'missing', r['missing'])
    return True, None


def main():
    cases = json.load(open(os.path.join(TC, 'gap_report_cases.json'), encoding='utf-8'))
    vp = os.path.join(TC, 'gap_report_verdicts.json')
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
        print('DIFF ', c['name'], '| got', str(got)[:200], '| want', str(c['expect'])[:200])
    print(f'{len(cases)} cases, {bad} unresolved')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
