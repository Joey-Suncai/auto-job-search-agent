#!/usr/bin/env python3
"""Harness for content.lead_on_resume (rule 13, JSA-255): DeepSeek cases from test_cases/lead_on_resume_spec.md, verdicts in
test_cases/lead_on_resume_verdicts.json; plus the real builders: a role with the Leadership section off builds no such section."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'resume-updater', 'scripts'))
import content as C  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'lead_on_resume_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'lead_on_resume_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = C.lead_on_resume(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
# _lead_on: missing file → True, voice false → False, unreadable → False
import tempfile
d = tempfile.mkdtemp(); org = (C.LEAD or {}).get('org')
good = os.path.join(d, 'f.json'); json.dump({'entries': [{'id': 'v', 'org': org, 'on_resume': False}]}, open(good, 'w'))
on = os.path.join(d, 'on.json'); json.dump({'entries': [{'id': 'v', 'org': org}]}, open(on, 'w'))
bad_f = os.path.join(d, 'bad.json'); open(bad_f, 'w').write('{not json')
for name, path, want in (('missing', os.path.join(d, 'none.json'), True), ('false', good, False), ('on', on, True), ('unreadable', bad_f, False)):
    if C._lead_on(path) is not want:
        bad += 1; print('DISAGREE _lead_on', name)
# the live shim: LEAD_ON follows the data home's facts (voice on_resume false) — recorded, not asserted on the user's facts
print('LEAD_ON =', C.LEAD_ON)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
