#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/platform_scorecard_cases.json, from platform_scorecard_spec.md)
against platform_scorecard.score() (JSA-045). Claude judges every disagreement in platform_scorecard_verdicts.json
("code" = fixed / "case" = the case misread the spec, with the reason). A disagreement without a verdict fails.
    python3 scripts/test_platform_scorecard.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import platform_scorecard as P  # noqa: E402


def expand(c):
    res, em, fmap = list(c.get('results') or []), list(c.get('emails') or []), dict(c.get('fmap') or {})
    g = c.get('generate')
    for g in ([g] if isinstance(g, dict) else g or []):
        for n in range(1, int(g['n']) + 1):
            f = f"{g.get('day', '2026-10-01')}_Gen{n}"
            res.append({'at': f"{g.get('day', '2026-10-01')}T10:00:00", 'folder': f, 'url': g['platform_url'],
                        'status': g.get('status', 'submitted'), 'secs': g.get('secs', 10)})
            fmap[f] = f'J{n}'; em.append({'job_id': f'J{n}', 'date': g.get('day', '2026-10-01'), 'type': 'Confirmation'})
    return res, em, fmap


def compare(got, c):
    diffs = []
    for plat, keys in (c.get('expect') or {}).items():
        if plat not in got:
            diffs.append(f'{plat}: missing'); continue
        for k, v in keys.items():
            g = got[plat].get(k)
            if isinstance(v, float) or isinstance(g, float):
                same = g is not None and v is not None and abs(float(g) - float(v)) < 1e-4
            else:
                same = g == v
            if not same:
                diffs.append(f'{plat}.{k}: got {g!r} want {v!r}')
    diffs += [f'{p}: should be absent' for p in c.get('expect_absent') or [] if p in got]
    return diffs


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'platform_scorecard_cases.json')))
    vp = os.path.join(HERE, 'test_cases', 'platform_scorecard_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        res, em, fmap = expand(c)
        try:
            d = compare(P.score(res, em, fmap, c.get('ds_cost') or {}, c.get('wrong') or [], c['today']), c)
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
