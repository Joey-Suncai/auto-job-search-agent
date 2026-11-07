#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/qa_table_cases.json) against the profile's question-and-answer
table (JSA-164): qa_add.entry() builds each entry, a temp copy of the example profile holds them, answer_rules.js answers
through rules_bridge.js. Also round-trips qa_add.add() (duplicates, replace). Verdicts in qa_table_verdicts.json.
    python3 scripts/test_qa_table.py"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts')
sys.path.insert(0, SC)
import qa_add  # noqa: E402

BASE = os.path.join(HERE, '..', 'config', 'profile.example.json')


def answer(case):
    prof = json.load(open(BASE, encoding='utf-8'))
    prof['qa'] = []
    for q in case.get('qa') or []:
        e = qa_add.entry(q['q'], q.get('text'), q.get('yes'), [q['pick']] if q.get('pick') else None, q.get('match'), 'test', '2026-11-04')
        prof['qa'].append(e)
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as fh:
        json.dump(prof, fh)
    try:
        fields = [{'key': 'x', 'label': case['label'], 'type': case.get('type') or 'text', 'options': case.get('options') or []}]
        r = subprocess.run(['node', os.path.join(SC, '..', 'runner', 'rules_bridge.js'), os.path.join(SC, 'answer_rules.js')],
                           input=json.dumps({'fields': fields, 'jd': ''}), capture_output=True, text=True, env=dict(os.environ, JSA_PROFILE=fh.name))
        return (json.loads(r.stdout or '{}') or {}).get('x') or {}
    finally:
        os.unlink(fh.name)


def source(a):
    if a.get('status') != 'ok' or a.get('leave'):
        return 'none', None
    return ('qa' if str(a.get('rule', '')).startswith('qa:') else 'rule'), a.get('value')


def unit():
    bad = 0
    p, how = qa_add.add({}, qa_add.entry('Typing speed?', '60 wpm', source='t'))
    try:
        qa_add.add(p, qa_add.entry('typing speed', '70 wpm', source='t')); bad += 1; print('FAIL  duplicate accepted')
    except ValueError:
        print('PASS  duplicate refused')
    p, how = qa_add.add(p, qa_add.entry('typing speed', '70 wpm', source='t'), replace=True)
    ok = how == 'replaced' and len(p['qa']) == 1 and p['qa'][0]['text'] == '70 wpm'
    print(('PASS ' if ok else 'FAIL ') + ' replace keeps one entry'); bad += not ok
    for args in ((None, None, None), ('x', True, None)):
        try:
            qa_add.entry('Q?', *args); bad += 1; print('FAIL  entry with', args)
        except ValueError:
            print('PASS  entry refuses', args)
    return bad


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'qa_table_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'qa_table_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    fails = unit()
    for c in cases:
        src, val = source(answer(c))
        exp = c['expect']
        good = src == exp['source'] and (src != 'qa' or str(val).strip().lower() == str(exp.get('value')).strip().lower())
        if good:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        fails += 1; print('FAIL ', c['name'], '| got', src, repr(val), '| want', exp, '|', c['label'][:80], c.get('options', [])[:5], c.get('qa'))
    print(f'{len(cases) - fails}/{len(cases)} ok')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
