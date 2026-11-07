#!/usr/bin/env python3
"""DeepSeek writes the test cases, Claude judges the results (Joey 2026-10-31: 「不要你既出题又判断」).

Give DeepSeek the spec (never the implementation) and a case format; it returns test cases with the outcome the spec
calls for. The caller runs them against the code and judges every disagreement itself (spec wrong? code wrong? case
wrong?) — the generator never sees the code or the results.

    python3 scripts/ds_testgen.py --spec <file> [--spec <file> …] --format <file> --n 25 --out <cases.json>
Cost goes to stdout (calls, tokens). Key: ~/deepseek/api_key (same as the runner).
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import ladder  # noqa: E402  (ask_deepseek: DeepSeek chat API, JSON mode)

SYSTEM = """You are an independent test designer. You get a SPEC and a CASE FORMAT. Write test cases that check whether an
implementation follows the spec — including edge cases, near misses, combinations of rules, and cases that must PASS
(no false alarms). You never see the implementation. For each case state the outcome the spec requires and quote the
spec sentence it comes from. Return JSON: {"cases": [ ... ]}. Use only facts in the spec; if the spec is ambiguous for a
case, set "ambiguous": true and say why."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', action='append', required=True); ap.add_argument('--format', required=True)
    ap.add_argument('--n', type=int, default=20); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    spec = '\n\n'.join(open(p, encoding='utf-8').read() for p in a.spec)
    fmt = open(a.format, encoding='utf-8').read()
    usage, t0 = {'calls': 0, 'prompt': 0, 'out': 0}, time.time()
    res = ladder.ask_deepseek(f"SPEC:\n{spec}\n\nCASE FORMAT:\n{fmt}\n\nWrite {a.n} cases.", usage, system=SYSTEM)
    cases = res.get('cases', [])
    json.dump(cases, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"{len(cases)} cases → {a.out} · DeepSeek calls {usage['calls']} · prompt {usage['prompt']} · output {usage['out']} tokens · {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
