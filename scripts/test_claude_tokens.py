#!/usr/bin/env python3
"""Harness for platform_scorecard.claude_tokens (rule 13): DeepSeek cases from claude_tokens_spec.md, verdicts in claude_tokens_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import platform_scorecard as P
cases = json.load(open(os.path.join(HERE, 'test_cases', 'claude_tokens_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'claude_tokens_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = P.claude_tokens(c['msgs'], c['results'])
    diffs = []
    for plat, want in c['expect'].items():
        g = got.get(plat)
        if plat == '_unallocated':
            if g != want: diffs.append(f'_unallocated got {g} want {want}')
            continue
        if g is None: diffs.append(f'{plat} missing'); continue
        for k, v in want.items():
            if g.get(k) != v and not (isinstance(v, list) and isinstance(g.get(k), list) and all(abs(a - b) <= 1 for a, b in zip(g[k], v))):
                diffs.append(f'{plat}.{k} got {g.get(k)} want {v}')
    if diffs and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '|', '; '.join(diffs))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
