#!/usr/bin/env python3
"""Harness for the critical / non-critical wrong-answer bars of platform_scorecard.score() (Joey 2026-11-05, rule 13):
DeepSeek cases from test_cases/scorecard_critical_spec.md; Claude's verdicts in scorecard_critical_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import platform_scorecard as P  # noqa: E402
URL = {'greenhouse': 'https://job-boards.greenhouse.io/acme/jobs/{n}', 'ashby': 'https://jobs.ashbyhq.com/acme/{n}'}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'scorecard_critical_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'scorecard_critical_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    res, wrong, counts = [], [], {}
    for n, a in enumerate(c.get('apps') or []):
        f = f'2026-11-01_App{n}_{a["platform"]}'
        res.append({'at': a.get('submitted_at') or '2026-11-01T09:00:00', 'folder': f, 'url': URL[a['platform']].format(n=n),
                    'status': 'submitted' if a.get('submitted_at') else 'dry-run', 'secs': 10})
        counts[f] = int(a.get('noncrit_answers') or 0)
        wrong += [dict(w, folder=f) for w in a.get('wrong') or []]
    got = P.score(res, [], {}, {}, wrong, '2026-11-20', recert=c.get('recert') or {}, field_counts=counts)
    diffs = [f'{pl}.{k}: got {got.get(pl, {}).get(k)!r} want {v!r}' for pl, exp in (c.get('expect') or {}).items()
             for k, v in exp.items() if got.get(pl, {}).get(k) != v]
    if diffs and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], diffs)
print(f'{len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
