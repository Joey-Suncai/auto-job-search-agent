#!/usr/bin/env python3
"""Harness for gmail_code.choose_mail with zone-less times (rule 13, 2026-11-02): DeepSeek cases, Claude's verdicts in choose_mail_tz_verdicts.json."""
import json, os, sys
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import gmail_code
cases = json.load(open(os.path.join(HERE, 'test_cases', 'choose_mail_tz_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'choose_mail_tz_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    mails = [(datetime.fromisoformat(m['sent']), m['from'], m['subject']) for m in c['mails']]
    got = gmail_code.choose_mail(mails, datetime.fromisoformat(c['since']), c['company'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['company'], [(m['from'], m['subject']) for m in c['mails']])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
