#!/usr/bin/env python3
"""JSA-260 (rule 13): DeepSeek-written cases from scripts/test_cases/audit_covered_spec.md (audit_covered_cases.json,
verdicts in audit_covered_verdicts.json): a wrong answer the current rules already fix is not counted — audit_sample.summary,
platform_scorecard.audit_gate(keep_covered) and score()'s wrong-answer counts; plus fixed checks of cover().
Offline, temp folders only.   python3 scripts/test_audit_covered.py"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix='jsa260_')
os.environ['JSA_HOME'] = TMP
os.environ['JSA_AUDIT_DIR'] = os.path.join(TMP, 'audit')
sys.path.insert(0, HERE)
import audit_sample as A  # noqa: E402
import audit_score as PS  # noqa: E402  (ADR-0011 step 5: score() cases run in the dev repo)

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'audit_covered_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
URL = {'greenhouse': 'https://boards.greenhouse.io/x', 'ashby': 'https://jobs.ashbyhq.com/x', 'lever': 'https://jobs.lever.co/x'}


def check(name, ok, *info):
    global bad
    if not ok and name not in verdicts:
        bad += 1
        print('FAIL', name, *[str(x)[:500] for x in info])


def close(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(close(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) < 0.0006
    return a == b


for c in json.load(open(os.path.join(CASES, 'audit_covered_cases.json'))):
    n, fn, g = c['name'], c['fn'], c.get('args') or {}
    try:
        if fn == 'summary':
            got = A.summary(g['items'])
            check(n, close(got, c['expect']), got, '| want', c['expect'])
        elif fn == 'audit_gate':
            kw = {k: g[k] for k in ('need', 'keep_covered') if g.get(k) is not None}
            got = PS.audit_gate(g['items'], g['window'], **kw)
            check(n, close(got, c['expect']), got, '| want', c['expect'])
        elif fn == 'score':
            continue                                    # the scorecard's score(): tested in the dev repo (jsa-dev)
            res = [{'folder': s['folder'], 'at': s['at'], 'status': 'submitted', 'url': URL.get(s['platform'], ''), 'ats': s['platform'], 'secs': 30}
                   for s in g['submits']]
            sc = PS.score(res, [], {}, {}, g.get('wrong') or [], '2026-12-31', recert=g.get('recert'))
            got = {p: {k: sc[p][k] for k in v} for p, v in c['expect'].items() if p in sc}
            check(n, got == c['expect'], got, '| want', c['expect'])
        else:
            check(n, False, 'unknown fn ' + fn)
    except Exception as e:
        check(n, False, f'{type(e).__name__}: {e}')

# fixed checks: cover() marks the item and its wrong_answers line
d = os.environ['JSA_AUDIT_DIR']; os.makedirs(d)
os.makedirs(os.path.join(TMP, 'data', 'runner'), exist_ok=True)
it = {'key': 'k1', 'platform': 'lever', 'folder': '2026-11-01_X', 'question': 'Consent: marketing', 'answer': 'Yes', 'check': 'wrong', 'judged': None, 'cls': 'non-critical'}
open(os.path.join(d, 'items.jsonl'), 'w').write(json.dumps(it) + '\n')
check('fixed: cover refuses an unjudged item', A.cover('k1', 'x') == 1)
A.judge('k1', 'wrong', 'marketing No')
check('fixed: cover a wrong item', A.cover('k1', 'rules answer No now', 'release-092') == 0)
item = A.jsonl(os.path.join(d, 'items.jsonl'))[0]
wa = A.jsonl(A.jpaths.data('runner', 'wrong_answers.jsonl'))
check('fixed: item and line marked', item['covered']['by'] == 'release-092' and wa[0]['covered']['by'] == 'release-092', item, wa)
sm = A.summary([item])
check('fixed: summary counts it covered', sm['lever']['wrong'] == 0 and sm['lever']['covered'] == 1 and sm['lever']['accuracy'] is None, sm)

print(f'audit_covered: DeepSeek cases ({len(verdicts)} verdicts) + fixed checks — fails {bad}')
sys.exit(1 if bad else 0)
