#!/usr/bin/env python3
"""JSA-413: the Last email link of the Waiting-for-you table (cases: test_cases/waiting_email_cases.json, written by DeepSeek
from waiting_email_spec.md)."""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store'))
import joey_todo as J  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'waiting_email_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'waiting_email_verdicts.json')
skip = set(json.load(open(vp))) if os.path.exists(vp) else set()
bad = []
for c in cases:
    if c['name'] in skip:
        continue
    apps = copy.deepcopy(c['apps']); before = copy.deepcopy(apps)
    got = {r['job_id']: r for r in J.tracker_actions(apps, c['today'])}
    for jid, want in c['expect'].items():
        r = got.get(jid)
        if r is None:
            bad.append(f"{c['name']}: {jid} missing"); continue
        for k, v in want.items():
            if r.get(k) != v:
                bad.append(f"{c['name']}: {jid}.{k} = {r.get(k)!r} want {v!r}")
    for jid in c.get('expect_absent', []):
        if jid in got:
            bad.append(f"{c['name']}: {jid} should not be a to-do row")
    if apps != before:
        bad.append(f"{c['name']}: input modified")
print(f'waiting email: {len(bad)} failure(s) in {len(cases)} cases')
for b in bad:
    print('FAIL', b)
sys.exit(1 if bad else 0)
