#!/usr/bin/env python3
"""JSA-244 (rule 13): DeepSeek-written cases from scripts/test_cases/jsa244_spec.md (jsa244_cases.json, verdicts in
jsa244_verdicts.json): form_prefetch.skipped (skip list), prefetch_due.pending with per-question handled marks, and the
full rule set (runner/rules_bridge.js, example profile, no saved answers) for language questions and "No" on a statement
list.   python3 scripts/test_jsa244.py"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNNER = os.path.join(ROOT, 'skills', 'auto-apply', 'runner')
TMP = tempfile.mkdtemp(prefix='jsa244_')
os.environ['JSA_HOME'] = TMP
os.environ['JSA_NO_PUSH'] = '1'
for p in (os.path.join(HERE, 'store'), RUNNER):
    sys.path.insert(0, p)
import prefetch_due as PD  # noqa: E402
import form_prefetch as FP  # noqa: E402

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'jsa244_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'jsa244_cases.json')))
bad = 0


def check(name, ok, *info):
    global bad
    if not ok and name not in verdicts:
        bad += 1
        print('FAIL', name, *info)


# the example profile (fictional candidate) with no saved answers, so only the rules answer
prof = json.load(open(os.path.join(ROOT, 'config', 'profile.example.json')))
prof['qa'] = []
pp = os.path.join(TMP, 'profile.json')
json.dump(prof, open(pp, 'w'))
fields = [dict(c['field'], key=str(i)) for i, c in enumerate(cases) if c['fn'] == 'rules']
got = {}
if fields:
    r = subprocess.run(['node', os.path.join(RUNNER, 'rules_bridge.js')], input=json.dumps(fields), capture_output=True,
                       text=True, timeout=120, env=dict(os.environ, JSA_PROFILE=pp, CX_SECOND_OPINION='0'))
    got = json.loads(r.stdout or '{}')
    if r.returncode:
        print(r.stderr[-800:])

for i, c in enumerate(cases):
    n = c['name']
    try:
        if c['fn'] == 'skipped':
            v = FP.skipped(c.get('company'), c.get('names'))
            check(n, v == c['expect'], v)
        elif c['fn'] == 'pending':
            h = c.get('handled')
            if isinstance(h, dict):
                h = {k: (None if v is None else set(v)) for k, v in h.items()}
            v = PD.pending(c['sheet'], h)
            check(n, v == c['expect'], v)
        elif c['fn'] == 'rules':
            a = got.get(str(i)) or {}
            ok = a.get('status') == c['expect_status']
            if ok and c['expect_status'] == 'ok' and c.get('expect_value') is not None:
                ok = a.get('value') == c['expect_value']
            if ok and c['expect_status'] == 'unknown' and c.get('expect_ask') is not None:
                ok = bool(a.get('ask')) == bool(c['expect_ask'])
            check(n, ok, json.dumps(c['field'], ensure_ascii=False)[:200], '→', json.dumps(a, ensure_ascii=False)[:300])
        else:
            check(n, False, 'unknown fn')
    except Exception as e:
        check(n, False, f'{type(e).__name__}: {e}')

print(f'jsa244: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) — fails {bad}')
sys.exit(1 if bad else 0)
