#!/usr/bin/env python3
"""Harness for the re-certification rule of platform_scorecard.score() (JSA-188, Joey 2026-11-05: Greenhouse re-certifies
after 10 submits with 0 wrong answers): DeepSeek cases from test_cases/platform_recert_spec.md; Claude's verdicts in
test_cases/platform_recert_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import platform_scorecard as P  # noqa: E402

URL = {'greenhouse': 'https://job-boards.greenhouse.io/acme/jobs/{n}', 'ashby': 'https://jobs.ashbyhq.com/acme/{n}',
       'lever': 'https://jobs.lever.co/acme/{n}', 'workday': 'https://acme.wd1.myworkdayjobs.com/x/job/{n}'}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'platform_recert_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'platform_recert_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    res, wrong = [], []
    for n, a in enumerate(c.get('apps') or []):
        f = f'2026-11-01_App{n}_{a["platform"]}'
        at = a.get('submitted_at') or '2026-11-01T09:00:00'
        res.append({'at': at, 'folder': f, 'url': URL[a['platform']].format(n=n), 'status': 'submitted' if a.get('submitted_at') else 'dry-run', 'secs': 10})
        wrong += [{'folder': f, 'field': 'x', 'class': 'critical'}] * int(a.get('wrong_answers') or 0)   # the re-cert bar is about critical wrong answers (Joey 11-05 split)
    got = P.score(res, [], {}, {}, wrong, '2026-11-20', recert=c.get('recert') or {})
    diffs = []
    for plat, exp in (c.get('expect') or {}).items():
        g = got.get(plat, {})
        for k, v in exp.items():
            if g.get(k) != v:
                diffs.append(f'{plat}.{k}: got {g.get(k)!r} want {v!r}')
    if diffs and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], diffs)
print(f'{len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
