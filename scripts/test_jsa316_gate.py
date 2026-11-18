#!/usr/bin/env python3
"""Harness for JSA-316 (rule 13): DeepSeek-written cases (test_cases/jsa316_gate_cases.json from jsa316_gate_spec.md)
for field_class's "defense" group and fact_gate.check_defense; Claude's verdicts on disagreements in
jsa316_gate_verdicts.json. The profile is a fixture with the one saved Harcorgal answer (the spec's)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import fact_gate  # noqa: E402
from field_class import field_class  # noqa: E402

PROF = {'answers': {'conviction': {'yes': False}}, 'work_auth': {'restricted': True}, 'education': [],
        'qa': [{'q': 'Are there any reasons why you would not be able to fully contribute in support of the U.S. military and allied forces?',
                'match': '/(any )?reasons? (why )?you (would|could) not (be able to )?(fully )?(contribute|support|work).{0,80}(military|defen[cs]e|armed forces|allied forces)/i',
                'pick': ['/^Yes$/i'], 'text': 'Yes'}]}


def got_class(label):
    c, g = field_class(label)
    return 'non-critical' if c == 'non-critical' else 'critical:' + (g if g in ('defense', 'eeo') else 'other')


def got_gate(label, value):
    m = fact_gate.check(label, value, PROF, 'select', None, ['Yes', 'No', 'Other'])
    return 'pass' if not m or m['key'] != 'fact:defense' else 'block:defense'


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa316_gate_cases.json'), encoding='utf-8'))
    vp = os.path.join(HERE, 'test_cases', 'jsa316_gate_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        gc, gg = got_class(c['label']), got_gate(c['label'], c['value'])
        ok = (c['expect_class'] == 'any' or gc == c['expect_class']) and gg == c['expect_gate']
        if not ok and c['name'] not in verdicts:
            bad += 1
            print('DISAGREE', c['name'], '| class', gc, 'want', c['expect_class'], '| gate', gg, 'want', c['expect_gate'], '|', c['label'][:110], '=', c['value'])
    print('%d DeepSeek cases · disagreements without a verdict: %d' % (len(cases), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
