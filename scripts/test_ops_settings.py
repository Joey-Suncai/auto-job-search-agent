#!/usr/bin/env python3
"""JSA-344: ops/settings.json — the using session's settings (installed into the data home by the release). Joey 2026-11-17 turned the sandbox off:
in the first batch the sandbox blocked the Ashby API (403), soffice, launchctl, osascript, and the real submit (chrome.lock); only Keychain worked.
    python3 scripts/test_ops_settings.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, '..', 'ops', 'settings.json')))
bad = 0
def T(name, ok, info=''):
    global bad
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}')); bad += not ok

T('sandbox is off (no sandbox section): the using session applies outside it — Joey 2026-11-17', 'sandbox' not in S, S.get('sandbox'))
T('the SessionStart hook is still there', any('ops_session.py' in h['command'] for e in S['hooks']['SessionStart'] for h in e['hooks']))
d = S['permissions']['deny']
T('the Edit deny rules and the --no-verify rules are kept', all(x in d for x in ['Edit(//Users/you/Projects/**)', 'Edit(//Users/you/projects/**)', 'Edit(//Users/you/JobAgent/app/**)', 'Bash(git commit *--no-verify*)']), d)
sys.exit(1 if bad else 0)
