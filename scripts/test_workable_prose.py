#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/workable_prose_cases.json) against run_workable's prose-box and
required-field helpers (JSA-151): essay_like, guard_short_answers, apply_drafts, required_empty. Verdicts in
workable_prose_verdicts.json.
    python3 scripts/test_workable_prose.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_workable as W  # noqa: E402


def call(c):
    a = c['args']
    if c['fn'] == 'essay_like':
        return W.essay_like(a['field'])
    if c['fn'] == 'guard_short_answers':
        return {k: v.get('status') for k, v in W.guard_short_answers(a['fields'], a['answers']).items()}
    if c['fn'] == 'apply_drafts':
        ans, miss = W.apply_drafts(a['fields'], a['answers'], a.get('drafts') or {}, a.get('cover'))
        return {'ok_keys': [f['key'] for f in a['fields'] if (ans.get(f['key']) or {}).get('status') == 'ok'], 'missing': [q['id'] for q in miss]}
    return W.required_empty(a['rows'])


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'workable_prose_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'workable_prose_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = call(c)
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got), 'want', repr(c['expect']))
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
