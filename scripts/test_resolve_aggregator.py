#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/resolve_aggregator_cases.json, from resolve_aggregator_spec.md)
against resolve_aggregator.decide() with the case's tables as the network (JSA-046). Claude judges every disagreement in
resolve_aggregator_verdicts.json ("code" = fixed / "case" = the case misread the spec, with the reason).
    python3 scripts/test_resolve_aggregator.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import resolve_aggregator as RA  # noqa: E402


def run(c):
    called = []
    def follow(u):
        called.append(u); return (c.get('follow') or {}).get(u)
    board = lambda ats, tok: [tuple(x) for x in (c.get('boards') or {}).get(f'{ats}:{tok}', [])]
    wd = lambda host, ten, site, title: [tuple(x) for x in (c.get('wd') or {}).get(f'{ten}:{site}', [])]
    tup = lambda xs: [tuple(x) for x in xs or []]
    r = RA.decide(c['row'], follow, tup(c.get('known')), tup(c.get('guesses')), tup(c.get('tenants')), board, wd)
    got = None if r is None else {k: v for k, v in r.items() if k in ('code', 'ats_url')}
    want = c['expect']
    d = [] if got == want else [f'got {got} want {want}']
    if c.get('expect_follow_called') is not None and bool(called) != c['expect_follow_called']:
        d.append(f'follow called {bool(called)} want {c["expect_follow_called"]}')
    return d


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'resolve_aggregator_cases.json')))
    vp = os.path.join(HERE, 'test_cases', 'resolve_aggregator_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            d = run(c)
        except Exception as e:
            d = [f'crash {type(e).__name__}: {e}']
        if not d:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1
        print('FAIL ', c['name'], '\n    ' + '\n    '.join(d))
    print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
