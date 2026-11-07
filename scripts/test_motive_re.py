#!/usr/bin/env python3
"""Harness for prep_batch.MOTIVE_RE (rule 13): DeepSeek-written cases, Claude's verdicts in motive_re_verdicts.json."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner', 'prep_batch.py'), encoding='utf-8').read()
MOTIVE_RE = eval(re.search(r'^MOTIVE_RE = (re\.compile\(.*?\))\s*(#.*)?$', src, re.M).group(1))
cases = json.load(open(os.path.join(HERE, 'test_cases', 'motive_re_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'motive_re_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = bool(MOTIVE_RE.search(c['label']))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['label'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
