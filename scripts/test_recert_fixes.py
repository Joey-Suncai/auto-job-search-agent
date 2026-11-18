#!/usr/bin/env python3
"""JSA-268 … JSA-271 (rule 13): DeepSeek-written cases from scripts/test_cases/recert_fixes_spec.md
(recert_fixes_cases.json, verdicts in recert_fixes_verdicts.json) for plan_build.numeric_answer, run_wd.state_on_review /
block_kind_of / blocks_of and batch_apply.ready. Profile digits are fixed to the spec's (25 / 52000). Offline.
python3 scripts/test_recert_fixes.py"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
import plan_build as PB  # noqa: E402
import batch_apply as BA  # noqa: E402
try:
    import run_wd as W  # noqa: E402
except Exception as e:   # playwright missing on this python: the Workday half is skipped
    W = None
    print(f'recert_fixes: run_wd not importable here ({type(e).__name__}) — its cases are skipped')
PB.jsa_profile.load = lambda: {'answers': {'comp': {'digits': {'hour': '25', 'year': '52000'}}}}

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'recert_fixes_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'recert_fixes_cases.json')))
bad = 0
for c in cases:
    fn, g, exp = c['fn'], c['args'], c['expect']
    if fn in ('state_on_review', 'block_kind_of', 'blocks_of') and W is None:
        continue
    if fn == 'numeric_answer':
        got = list(PB.numeric_answer(g['label'], g['src'], g['ans']))
        ok = got[0] == exp[0] and (got[1].startswith('number box:') if exp[0] is None else got[1] == exp[1])
    elif fn == 'state_on_review':
        got = W.state_on_review(g['value'], g['txt']); ok = got == exp
    elif fn == 'block_kind_of':
        got = W.block_kind_of(g['section']); ok = got == exp
    elif fn == 'blocks_of':
        got = W.blocks_of(g['fields'], g['kind']); ok = got == exp
    else:
        got = BA.ready(g['status'], g['reasons']); ok = got == exp
    if not ok and c['name'] not in verdicts:
        bad += 1
        print('FAIL', c['name'], g, 'expect', exp, 'got', got)
print(f'recert_fixes: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) — fails {bad}')
sys.exit(1 if bad else 0)
