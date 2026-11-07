#!/usr/bin/env python3
"""Harness for the big-tech career-site helpers (rule 13, JSA-133): ats_search parse_amazon / parse_apple /
parse_google_list, resolve_careers.big_tech, eligibility_fetch js_string_after / apple_parse / google_parse.
DeepSeek cases in test_cases/bigtech_cases.json + bigtech_jd_cases.json; verdicts in bigtech_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import ats_search as A, resolve_careers as R, eligibility_fetch as E  # noqa: E402
FN = {'parse_amazon': A.parse_amazon, 'parse_apple': A.parse_apple, 'parse_google_list': A.parse_google_list, 'big_tech': R.big_tech,
      'js_string_after': E.js_string_after, 'apple_parse': E.apple_parse, 'google_parse': E.google_parse}
cases = [c for f in ('bigtech_cases.json', 'bigtech_jd_cases.json') for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]
vp = os.path.join(HERE, 'test_cases', 'bigtech_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
norm = lambda v: json.loads(json.dumps(v))            # tuples → lists, so [('amazon','amazon')] equals [["amazon","amazon"]]
bad = 0
for c in cases:
    try:
        got = norm(FN[c['fn']](*c['args']))
    except Exception as e:
        got = f'ERROR {type(e).__name__}: {e}'
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], c['fn'], '| got', json.dumps(got)[:260], '| expect', json.dumps(c['expect'])[:260])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
