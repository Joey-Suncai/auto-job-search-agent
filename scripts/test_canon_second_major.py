#!/usr/bin/env python3
"""JSA-293: canon accepts a second major / minor left empty (or "None") when none is on file — Joey 2026-11-10, his
JSA-281 decision — and replay.load_reasons keeps a canon acceptance when a later plain reason records the same answer.
DeepSeek wrote the cases from scripts/test_cases/canon_second_major_spec.md (rule 13); disagreements judged in
canon_second_major_verdicts.json. Prints `N/M ok`.
    python3 scripts/test_canon_second_major.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
sys.path.insert(0, os.path.join(HERE, 'learn'))
import canon  # noqa: E402
import replay  # noqa: E402


def run(c):
    if c['fn'] == 'audit':
        hard = [m for m in canon.audit([{'label': c['label'], 'value': c['value'], 'required': True}]) if m['key'] == 'education_field']
        return bool(hard) == c['expect_mismatch'] and (not hard or c.get('expect_reason') in (None, hard[0]['reason'])), hard
    with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as t:
        t.write('\n'.join(c['lines']) + '\n')
    got = replay.load_reasons(t.name).get(c['key']) or {}
    os.unlink(t.name)
    e = c['expect']
    g = {'status': got.get('status'), 'value': got.get('value'), 'reason': got.get('reason'), 'kind': got.get('kind')}
    return g == {'status': e.get('status'), 'value': e.get('value'), 'reason': e.get('reason'), 'kind': e.get('kind')}, g


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'canon_second_major_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'canon_second_major_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        ok, got = run(c)
        if ok:
            continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why'][:140]); continue
        bad += 1; print('FAIL ', c['name'], '| got', json.dumps(got)[:200], '| case', json.dumps({k: c[k] for k in c if k not in ('spec_quote', 'lines')})[:300])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
