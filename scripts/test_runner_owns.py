#!/usr/bin/env python3
"""Harness for lever_fill/server.runner_owns (rule 13, JSA-083): DeepSeek cases in test_cases/runner_owns_cases.json,
verdicts in runner_owns_verdicts.json. Plus: run_form's mark file is read back as owned while its process lives."""
import json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'lever_fill'))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import server
cases = json.load(open(os.path.join(HERE, 'test_cases', 'runner_owns_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'runner_owns_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    calls = []
    alive = lambda pid: (calls.append(pid), pid in c.get('alive_pids', []))[1]
    got = server.runner_owns(c['mark'], c['now_ts'], alive)
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['mark'], c['now_ts'], c.get('alive_pids'))

# round trip with the runner's own writer (no Chrome): mark → owned by this live process → cleared → not owned
import run_form
d = tempfile.mkdtemp()
run_form.mark_runner(d, 'submit', 'https://jobs.lever.co/x/y/apply')
own = server.runner_owns(server.read_mark(d), time.time())
run_form.clear_runner(d)
gone = server.runner_owns(server.read_mark(d), time.time())
dead = server.runner_owns({'ts': time.time(), 'pid': 999999}, time.time())
for name, ok in (('mark written by run_form is owned', own), ('cleared mark is not owned', not gone), ('dead pid is not owned', not dead)):
    if not ok:
        bad += 1; print('FAIL', name)
print(f'{len(cases)} cases + 3 round-trip checks · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
