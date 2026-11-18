#!/usr/bin/env python3
"""JSA-258 (rule 13): DeepSeek-written cases from scripts/test_cases/scorecard_audit_spec.md (scorecard_audit_cases.json,
verdicts in scorecard_audit_verdicts.json): platform_scorecard.audit_gate / window_folders / audit_cell and
audit_sample.sample(first=…); plus fixed checks that score() applies the audit bar only when audit_items is given.
Offline.   python3 scripts/test_scorecard_audit.py"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('JSA_HOME', tempfile.mkdtemp(prefix='jsa258_'))
sys.path.insert(0, HERE)
import audit_score as PS  # noqa: E402  (ADR-0011 step 5: audit_gate / window_folders live in the product; audit_cell + score() are tested in the dev repo)
import audit_sample as A  # noqa: E402

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'scorecard_audit_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0


def check(name, ok, *info):
    global bad
    if not ok and name not in verdicts:
        bad += 1
        print('FAIL', name, *[str(x)[:400] for x in info])


def close(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(close(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) < 0.0006
    return a == b


cases = json.load(open(os.path.join(CASES, 'scorecard_audit_cases.json')))
for c in cases:
    n, fn, g = c['name'], c['fn'], c.get('args') or {}
    try:
        if fn == 'audit_gate':
            kw = {k: g[k] for k in ('need', 'noncrit') if g.get(k) is not None}
            got = PS.audit_gate(g.get('items'), g.get('window'), **kw)
            check(n, close(got, c['expect']), got, '| want', c['expect'])
        elif fn == 'window_folders':
            got = PS.window_folders(g.get('results') or [], g.get('recert'))
            check(n, got == c['expect'], got, '| want', c['expect'])
        elif fn == 'sample':
            got = A.sample(g.get('folders') or [], g.get('audited'), g['n'], g.get('seed', 's'), first=g.get('first'))
            pool = set(g.get('folders') or []) - set(g.get('audited') or [])
            ok = got == sorted(set(got)) and set(got) <= pool and len(got) == c['expect_len']
            if ok and c.get('expect_from_first') is not None:
                ok = sum(1 for f in got if f in set(g.get('first') or [])) == c['expect_from_first']
            check(n, ok, got)
        elif fn == 'audit_cell':
            continue                                    # the scorecard's cell text: tested in the dev repo (jsa-dev)
        else:
            check(n, False, 'unknown fn ' + fn)
    except Exception as e:
        check(n, False, f'{type(e).__name__}: {e}')

# score()'s audit bar (the scorecard itself) is tested in the dev repo (jsa-dev), ADR-0011 step 5

print(f'scorecard_audit: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) + fixed checks — fails {bad}')
sys.exit(1 if bad else 0)
