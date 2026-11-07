#!/usr/bin/env python3
"""Harness for runner/collect_batch.py helpers (JSA-189, rule 13): DeepSeek cases from test_cases/collect_batch_spec.md;
Claude's verdicts in test_cases/collect_batch_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import collect_batch as CB  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'collect_batch_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'collect_batch_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    fn = c.get('fn')
    if fn == 'parse_unknown':
        q, o = CB.parse_unknown(c['input']); ok = [q, o] == c['expect']; got = [q, o]
    elif fn == 'qnorm_same':
        got = CB.qnorm(c['a']) == CB.qnorm(c['b']); ok = got == c['expect']
    elif fn == 'merge':
        qs, human = CB.merge(c['items'])
        got = {'entries': [{'question_key_of': e['question'], 'folders': e['folders'], 'options': e['options'], 'kind': e['kind']} for e in qs], 'human': len(human)}
        exp = c['expect']
        ok = got['human'] == exp.get('human', 0) and len(got['entries']) == len(exp.get('entries') or []) and all(
            CB.qnorm(g['question_key_of']) == CB.qnorm(x['question_key_of']) and g['folders'] == x['folders'] and g['options'] == x['options'] and g['kind'] == x['kind']
            for g, x in zip(got['entries'], exp.get('entries') or []))
    elif fn == 'qa_args':
        got = CB.qa_args(c['entry'], c.get('source', '')); ok = got == c['expect']
    else:
        got, ok = 'unknown fn', False
    if not ok and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], fn, '| got', json.dumps(got, ensure_ascii=False)[:300], '| exp', json.dumps(c.get('expect'), ensure_ascii=False)[:300])
print(f'{len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
