#!/usr/bin/env python3
"""Harness for run_form.system_fields / wait_until (rule 13, JSA-073): DeepSeek cases in
test_cases/system_wait_cases.json, verdicts in system_wait_verdicts.json. Simulated clock: only sleep() advances it."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_form
cases = json.load(open(os.path.join(HERE, 'test_cases', 'system_wait_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'system_wait_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    if c['fn'] == 'system_fields':
        got = [f['key'] for f in run_form.system_fields(c['plan'])]
        ok = got == c['expect']
    else:
        t = [0.0]; sleeps = [0]
        def sleep(s): t[0] += s; sleeps[0] += 1
        appear = c.get('appear_at') or {}
        present = lambda k: k in appear and appear[k] is not None and t[0] >= appear[k]
        got = run_form.wait_until(present, c['keys'], c['timeout'], c.get('step', 0.5), clock=lambda: t[0], sleep=sleep)
        ok = got == c['expect'] and ('expect_sleeps' not in c or sleeps[0] == c['expect_sleeps'])
        got = (got, sleeps[0])
    if not ok and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], c.get('expect_sleeps', ''))
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
