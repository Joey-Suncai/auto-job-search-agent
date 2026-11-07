#!/usr/bin/env python3
"""Harness for wd_signin.verify_pattern (rule 13): DeepSeek cases, Claude's verdicts in verify_pattern_verdicts.json."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import wd_signin
cases = json.load(open(os.path.join(HERE, 'test_cases', 'verify_pattern_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'verify_pattern_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    m = re.search(wd_signin.verify_pattern(c['page_url']), c['link'], re.I)
    got = bool(m and m.start() == 0)
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['page_url'], '|', c['link'])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
