#!/usr/bin/env python3
"""DeepSeek-written cases (scripts/test_cases/facts_check_cases.json) against facts_check (JSA-248, rule 13).
Claude judges each disagreement in scripts/test_cases/facts_check_verdicts.json ("code" = fixed / "case" = the case
misreads the spec, with why). An unjudged disagreement fails.    python3 skills/resume-updater/scripts/test_facts_check.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import facts_check as C  # noqa: E402

TC = os.path.join(REPO, 'scripts', 'test_cases')
KIND = [('schema', ('entry ', 'fact #', 'schema:')), ('number_drift', ('is not in its S/T/A/R',)),
        ('no_entry', ('no entry in facts.json',)), ('unmapped', ('maps to no fact',)),
        ('unsupported_number', ('bullet number',)), ('never_phrase', ('never-phrase',))]


def kinds(errs):
    out = set()
    for e in errs:
        for k, marks in KIND:
            if k == 'schema' and 'is not in its S/T/A/R' in e:
                continue
            if any(m in e for m in marks) and (k != 'schema' or e.startswith(('entry ', 'fact ', 'schema:'))):
                out.add(k)
                break
    return out


def run(case):
    fb = case['facts']
    errs = C.check_schema(fb)
    drift = [e for e in errs if 'is not in its S/T/A/R' in e]
    schema = [e for e in errs if e not in drift]
    if schema:
        return {'schema'}
    with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(case.get('bank_md') or '')
    warns = []
    try:
        e2, _ = C.check_bank(fb, f.name, warns)
    finally:
        os.unlink(f.name)
    stale = sorted({n for w in warns for n in w.split(': ', 1)[1].split(' in: ')[0].split(', ')})
    return kinds(drift + e2) | ({'stale:' + ','.join(stale)} if stale else set())


def main():
    cases = json.load(open(os.path.join(TC, 'facts_check_cases.json'), encoding='utf-8'))
    hp = os.path.join(TC, 'facts_check_history_cases.json')
    cases += json.load(open(hp, encoding='utf-8')) if os.path.exists(hp) else []
    vp = os.path.join(TC, 'facts_check_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = run(c)
            if 'expect_stale' not in c:
                got = {g for g in got if not g.startswith('stale:')}
        except Exception as ex:   # a malformed case still needs a verdict
            got = {f'crash:{type(ex).__name__}'}
        want = set(c.get('expect_problems') or [])
        if c.get('expect') == 'pass':
            want = set()
        if c.get('expect_stale') and 'schema' not in want:
            want.add('stale:' + ','.join(sorted(str(x) for x in c['expect_stale'])))
        if got == want:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '— judged:', v['why'][:110]); continue
        bad += 1
        print('DIFF ', c['name'], '| want', sorted(want), '| got', sorted(got), '|', c.get('why', '')[:90])
    ex = C.check_schema(C.load(os.path.join(REPO, 'config', 'facts.example.json')))
    print('PASS ' if not ex else 'FAIL ', 'config/facts.example.json schema', ex[:3])
    bad += bool(ex)
    print(f'{len(cases)} cases, {bad} unresolved')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
