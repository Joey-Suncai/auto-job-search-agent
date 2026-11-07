#!/usr/bin/env python3
"""Harness for export_public.keep, scan.phone_re / find_hits and launchagent install.render (rule 13, JSA-078/079):
DeepSeek cases in test_cases/export_public_cases.json, verdicts in export_public_verdicts.json."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'public')); sys.path.insert(0, os.path.join(HERE, 'launchagent'))
import export_public as X, scan as S, install as I  # noqa: E402
cases = [c for f in ('export_public_cases.json', 'export_public_b_cases.json') for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]   # b = config/ (JSA-118)
vp = os.path.join(HERE, 'test_cases', 'export_public_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    f = c['fn']
    if f == 'keep':
        got = X.keep(c['path'])
    elif f == 'phone_re':
        rx = S.phone_re(c['phone']); got = None if rx is None else bool(re.search(rx, c['text'], re.I))
    elif f == 'find_hits':
        got = S.find_hits(c['rel'], c['text'], [tuple(t) for t in c['terms']])
    else:
        try:
            got = I.render(c['template'], c['values'])
        except ValueError:
            got = 'error'
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', f, c['name'], '| got', repr(got)[:160], '| expect', repr(c['expect'])[:160])
# fixed check (2026-11-05): every config/*.py module the code imports is in the export — config/paths.py was missing and
# the public tree's tests all failed ("third-party 'paths' not installed")
ROOT = os.path.dirname(HERE)
mods = {f[:-3] for f in os.listdir(os.path.join(ROOT, 'config')) if f.endswith('.py') and '.example.' not in f}
used = set()
for d, _, fs in os.walk(ROOT):
    rel = os.path.relpath(d, ROOT)
    if rel.split(os.sep)[0] in ('.git', 'node_modules', '.claude', 'data', 'applications'):
        continue
    for f in fs:
        if f.endswith('.py'):
            try:
                t = open(os.path.join(d, f), encoding='utf-8').read()
            except (UnicodeDecodeError, OSError):
                continue
            for m in mods:
                if re.search(rf'^\s*(import {m}\b|from {m} import)', t, re.M):
                    used.add(m)
for m in sorted(used):
    if not X.keep(f'config/{m}.py') and m != 'resume_content':      # resume_content.py = private facts; the code falls back to the .example
        bad += 1; print('NOT EXPORTED', f'config/{m}.py', '(imported by the code)')
print(f'{len(cases)} cases · config modules imported: {sorted(used)} · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
