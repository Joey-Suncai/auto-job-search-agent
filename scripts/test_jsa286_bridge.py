#!/usr/bin/env python3
"""JSA-286: plan_build.run_rules passes the job folder's cover.txt to the rules (rules_bridge.js → ctx.cover): the optional
"Message to the Hiring Manager" box gets the cover letter's first sentences; no cover.txt → the box is left empty.
    python3 scripts/test_jsa286_bridge.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path[:0] = [os.path.join(ROOT, 'skills/auto-apply/runner'), os.path.join(ROOT, 'config')]
base = json.load(open(os.path.join(ROOT, 'config', 'profile.example.json')))
base['qa'] = []
tmp = tempfile.mkdtemp(prefix='jsa286b_')
json.dump(base, open(os.path.join(tmp, 'p.json'), 'w'))
os.environ['JSA_PROFILE'] = os.path.join(tmp, 'p.json')
import plan_build as PB  # noqa: E402
bad = 0
F = [{'key': 'm', 'label': 'Message to the Hiring Manager:', 'type': 'text', 'options': []}]
folder = tempfile.mkdtemp(prefix='jsa286f_')
if PB.load_cover(folder) != '':
    bad += 1; print('FAIL load_cover without a file')
open(os.path.join(folder, 'cover.txt'), 'w').write('Dear Acme team,\n\nI like data. I build models. I ship them. I write docs.\n\nSincerely,\nJ\n')
r = PB.run_rules(F, '', 'Acme', PB.load_cover(folder))['m']
if r.get('value') != 'I like data. I build models. I ship them.':
    bad += 1; print('FAIL cover reaches the rule', r)
r = PB.run_rules(F, '', 'Acme', '')['m']
if not (r.get('leave') and r.get('value') == ''):
    bad += 1; print('FAIL no cover leaves the box empty', r)
print('JSA-286 bridge:', 'ALL PASS' if not bad else f'{bad} FAILED')
sys.exit(1 if bad else 0)
