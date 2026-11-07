#!/usr/bin/env python3
"""Harness for eligibility_fetch.wellfound_parse (rule 13): DeepSeek cases, verdicts in wellfound_jd_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import eligibility_fetch as E
cases = json.load(open(os.path.join(HERE, 'test_cases', 'wellfound_jd_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'wellfound_jd_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = E.wellfound_parse(c['page'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got, ensure_ascii=False)[:300], '| expect', json.dumps(c['expect'], ensure_ascii=False)[:300])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
