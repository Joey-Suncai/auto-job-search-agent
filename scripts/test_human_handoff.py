#!/usr/bin/env python3
"""Harness for the human-check hand-off (JSA-106; rule 13: DeepSeek wrote the cases from test_cases/human_handoff_spec.md,
Claude judges). Verdicts (case misreads the spec) in test_cases/human_handoff_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import human_check as H


def judge(c):
    fn, a, e = c['fn'], c['args'], c['expect']
    if fn == 'company': return H.company(a['folder']) == e, H.company(a['folder'])
    if fn == 'pending': got = [r['folder'] for r in H.pending(a['rows'])]; return got == e, got
    if fn == 'summary':
        got = H.summary(a['rows'])
        if e is None: return got is None, got
        if got is None: return False, got
        t, b = got
        ok = t == e['title'] and all(s in b for s in e.get('body_contains', [])) and not any(s in b for s in e.get('body_not_contains', []))
        return ok, got
    t, b = H.message(a['folder'], a['checks'], a.get('parked', True)); lines = b.split('\n')
    want = e['body_lines']
    if want and want[-1] == '<<LAST>>':
        phrase = 'runner 已先去投下一份' if a.get('parked', True) else 'runner 在等'
        ok = lines[:-1] == want[:-1] and 'job Chrome' in lines[-1] and phrase in lines[-1]
    else:
        ok = lines == want
    return ok and t == e['title'], (t, lines)


cases = json.load(open(os.path.join(HERE, 'test_cases', 'human_handoff_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'human_handoff_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    if c['name'] in verdicts: continue
    ok, got = judge(c)
    if not ok:
        bad += 1; print(f'DISAGREE {c["name"]} | got {json.dumps(got, ensure_ascii=False)[:400]}\n    case {json.dumps(c, ensure_ascii=False)[:600]}')
print(f'human_handoff: {len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
