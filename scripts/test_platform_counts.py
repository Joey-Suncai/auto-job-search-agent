#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/platform_counts_cases.json, from platform_counts_spec.md) against
scripts/platform_counts.py (JSA-113). Claude judges every disagreement in platform_counts_verdicts.json
("code" = fixed / "case" = the case misread the spec, with the reason).
    python3 scripts/test_platform_counts.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import platform_counts as PC  # noqa: E402

CASE_FILES = [os.path.join(HERE, 'test_cases', f) for f in
              ('platform_counts_cases.json', 'platform_counts_sf_cases.json', 'platform_runner_cases.json', 'platform_runner_b_cases.json')]   # sf = JSA-170 · runner = JSA-177
VERDICTS = os.path.join(HERE, 'test_cases', 'platform_counts_verdicts.json')


def run(c):
    f, a = c['fn'], c['args']
    if f == 'platform_of':
        return PC.platform_of(a['url'])
    if f == 'row_platform':
        return PC.row_platform(a['row'])
    if f == 'runner_status':
        return PC.runner_status(a['platform'])
    if f == 'runner_fields':
        return PC.runner_fields(a['row'])
    if f == 'summarize':
        return PC.summarize(a['rows'])
    raise ValueError(f)


def main():
    cases = [c for f in CASE_FILES for c in json.load(open(f, encoding='utf-8'))]
    verdicts = json.load(open(VERDICTS, encoding='utf-8')) if os.path.exists(VERDICTS) else {}
    fails = 0
    for c in cases:
        got = run(c)
        if got == c['expect']:
            continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            continue
        fails += 1
        print(f"FAIL {c['name']}: got {json.dumps(got, ensure_ascii=False)} expect {json.dumps(c['expect'], ensure_ascii=False)}")
    print(f"{len(cases)} cases · fails {fails}")
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
