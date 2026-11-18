#!/usr/bin/env python3
"""Harness for wd_signin.choose_verify_link (rule 13, JSA-274): DeepSeek cases (verify_mail_cases.json, from
verify_mail_spec.md), Claude's verdicts on disagreements in verify_mail_verdicts.json, plus the real Vanguard mail."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import wd_signin
cases = json.load(open(os.path.join(HERE, 'test_cases', 'verify_mail_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'verify_mail_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases.append({'name': 'real_vanguard_2026_11_10', 'since': '2026-11-10T19:12:50+00:00', 'company': 'Vanguard',
              'page_url': 'https://vanguard.wd5.myworkdayjobs.com/en-US/vanguard_external/job/Charlotte-NC/x_181765/apply',
              'mails': [{'date': '2026-11-10T11:12:59-08:00', 'from': 'CrewCentral_noreply@vanguardhr.com',
                         'subject': 'Verify your candidate account',
                         'body': 'https://vanguard.wd5.myworkdayjobs.com/vanguard_external/activate/abc123 '
                                 'https://www.vanguardjobs.com/site-privacy-policy/'}],
              'expect': 'https://vanguard.wd5.myworkdayjobs.com/vanguard_external/activate/abc123'})
bad = 0
for c in cases:
    got = wd_signin.choose_verify_link(c['mails'], c['since'], c['page_url'], c.get('company'))
    v = verdicts.get(c['name'])
    want = v['expect'] if v and 'expect' in v else c['expect']
    if got != want:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', want, '|', c.get('rule', '')[:100])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
