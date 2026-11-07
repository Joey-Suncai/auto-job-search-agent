#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/linkedin_survey.py helpers (rule 13, JSA-176): DeepSeek cases in
test_cases/linkedin_survey_cases.json, verdicts in linkedin_survey_verdicts.json."""
import json, os, sys, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import linkedin_survey as L
cases = json.load(open(os.path.join(HERE, 'test_cases', 'linkedin_survey_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'linkedin_survey_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f, a, exp = c['fn'], c.get('args') or {}, c.get('expect')
    if f == 'search_url':
        u = urllib.parse.urlsplit(L.search_url(a['keyword'], a.get('easy', False), a.get('start', 0)))
        got = {'path': u.path, 'query': {k: v[0] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}}
        if u.netloc != 'www.linkedin.com' or u.scheme != 'https':
            got['host'] = u.scheme + '://' + u.netloc
        exp = {'path': exp.get('path'), 'query': {k: str(v) for k, v in (exp.get('query') or {}).items()}}
    elif f == 'parse_count':
        got = L.parse_count(a.get('text'))
    elif f == 'classify_button':
        got = L.classify_button(a.get('text'))
    elif f == 'link_target':
        got = L.link_target(a.get('href'))
    elif f == 'card_easy':
        got = L.card_easy(a.get('lines'))
    elif f == 'pick_sample':
        got = L.pick_sample(a.get('groups') or [], a.get('n'))
    elif f == 'card_title':
        got = L.card_title(a.get('lines'))
    elif f == 'intern_title':
        got = L.intern_title(a.get('title'))
    elif f == 'share':
        got = L.share(a.get('part'), a.get('total'))
    else:
        got = f'unknown fn {f}'
    if got != exp and c['name'] not in verdicts:
        bad += 1
        print('DISAGREE', c['name'], '| got', json.dumps(got, ensure_ascii=False), '| expect', json.dumps(exp, ensure_ascii=False),
              '| args', json.dumps(a, ensure_ascii=False)[:400])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
