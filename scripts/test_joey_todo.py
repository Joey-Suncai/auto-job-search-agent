#!/usr/bin/env python3
"""Harness for scripts/store/joey_todo.py merge rules (JSA-189, rule 13): DeepSeek cases from
test_cases/joey_todo_spec.md; Claude's verdicts in test_cases/joey_todo_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store'))
import joey_todo as J  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'joey_todo_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'joey_todo_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    rows = J.merge(J.parse_queue('\n'.join(c.get('queue') or [])), J.open_checks(c.get('human_checks') or []),
                   J.needs_you(c.get('apply_requests') or []), set(c.get('submitted') or []), c.get('tracker') or {},
                   c.get('jobs') or {}, c.get('job_of') or {}, '2026-11-06')
    got = [{'folder': r['folder'], 'n': r['n'], 'kind': r['kind']} for r in rows]
    exp = [{'folder': e['folder'], 'n': e['n'], 'kind': e['kind']} for e in c.get('expect') or []]
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '\n   got', got, '\n   exp', exp)
print(f'{len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
