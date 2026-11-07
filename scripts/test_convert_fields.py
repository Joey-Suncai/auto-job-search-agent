#!/usr/bin/env python3
"""Harness for scripts/learn/convert_fields.rows_of (JSA-187, rule 13): DeepSeek cases from
test_cases/convert_fields_spec.md; Claude's verdicts in test_cases/convert_fields_verdicts.json."""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('CX_DATA', tempfile.mkdtemp())
sys.path.insert(0, os.path.join(HERE, 'learn'))
import convert_fields as CF  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'convert_fields_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'convert_fields_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    d = tempfile.mkdtemp()
    for name, body in (c.get('files') or {}).items():
        with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
            f.write(body if isinstance(body, str) else json.dumps(body))
    got = CF.rows_of(d)
    exp = c.get('expect')
    probs = []
    if exp is None:
        if got is not None:
            probs.append(f'expected None, got {len(got[2])} rows')
    elif got is None:
        probs.append('got None')
    else:
        ats, url, rows = got
        if 'ats' in exp and exp['ats'] != ats: probs.append(f'ats {ats!r} != {exp["ats"]!r}')
        if 'url' in exp and exp['url'] != url: probs.append(f'url {url!r} != {exp["url"]!r}')
        if 'n_rows' in exp and exp['n_rows'] != len(rows): probs.append(f'n_rows {len(rows)} != {exp["n_rows"]}')
        for er in exp.get('rows') or []:
            i = er.get('index', 0)
            if i >= len(rows):
                probs.append(f'row {i} missing'); continue
            for k, v in er.items():
                if k != 'index' and rows[i].get(k) != v:
                    probs.append(f'row {i} {k} {rows[i].get(k)!r} != {v!r}')
    if probs and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], probs[:4])
print(f'{len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
