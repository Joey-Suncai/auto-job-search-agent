#!/usr/bin/env python3
"""Harness for form_prefetch.sense (JSA-281, rule 13): DeepSeek-written pairs (test_cases/prefetch_sense_cases.json from
prefetch_sense_spec.md) — "same" pairs must get the same marks, "split" pairs different ones; Claude's verdicts on
disagreements in prefetch_sense_verdicts.json."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import form_prefetch as F  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'prefetch_sense_cases.json'), encoding='utf-8'))
    vp = os.path.join(HERE, 'test_cases', 'prefetch_sense_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    pairs = [('What is your highest level of education?', 'Level of education completed once you’ve graduated?', 'split')]   # Wynrosquin 11-10
    for a, b, want in pairs + [(c['a'], c['b'], c['expect']) for c in cases]:
        got = 'same' if F.sense(a) == F.sense(b) else 'split'
        name = next((c['name'] for c in cases if c['a'] == a and c['b'] == b), 'tinder')
        if got != want and name not in verdicts:
            bad += 1; print('DISAGREE', name, '| got', got, F.sense(a), F.sense(b), '| expect', want, '|', a[:60], '||', b[:60])
    print(f'{len(cases) + len(pairs)} pairs · disagreements without a verdict: {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
