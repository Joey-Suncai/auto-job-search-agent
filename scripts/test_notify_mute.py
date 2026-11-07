#!/usr/bin/env python3
"""scripts/daily/notify.py mute switch (JSA-181): DeepSeek cases from test_cases/notify_mute_spec.md; osascript is
replaced by a counter, so nothing is ever shown.   python3 scripts/test_notify_mute.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'daily'))
import notify as N  # noqa: E402

calls = []
class R: returncode = 0; stderr = ''
N.osa = lambda *a: (calls.append(a), R())[1]
cases = json.load(open(os.path.join(HERE, 'test_cases', 'notify_mute_cases.json'), encoding='utf-8'))
fails = 0
for c in cases:
    if c['fn'] == 'muted':
        g = N.muted(c['env'])
        if g != c['expect']: fails += 1; print('FAIL', c['name'], c['env'], 'got', g)
        continue
    old = os.environ.copy(); os.environ.clear(); os.environ.update(c['env']); calls.clear()
    try:
        g = N.notify(c['title'], c['body'])
    finally:
        os.environ.clear(); os.environ.update(old)
    want_calls = c['expect_calls']; ok_calls = (len(calls) == 0) if want_calls == 0 else (len(calls) >= 1)
    ok_ret = (g == []) if c['expect'] == [] else bool(g)
    if not (ok_calls and ok_ret): fails += 1; print('FAIL', c['name'], 'calls', len(calls), 'ret', g)
print(f'{len(cases)} cases · fails {fails}'); sys.exit(1 if fails else 0)
