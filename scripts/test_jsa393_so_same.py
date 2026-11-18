#!/usr/bin/env python3
"""JSA-393 (rule 13): DeepSeek-written cases (test_cases/jsa393_so_same_cases.json, spec …_spec.md) for second_opinion.same: a longer
version of a name / school / degree is a DIFFERENT answer; 'Yes' = 'Yes, I am …' stays. Plus the real pairs of the JSA-292 review.
Verdicts: jsa393_so_same_verdicts.json.   python3 scripts/test_jsa393_so_same.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path[:0] = [os.path.join(ROOT, 'skills/auto-apply/runner'), os.path.join(ROOT, 'config')]
import second_opinion as SO  # noqa: E402
vp = os.path.join(HERE, 'test_cases', 'jsa393_so_same_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa393_so_same_cases.json')))
cases += [{'name': f'real {a} / {b}', 'rule_value': a, 'model_value': b, 'options': [], 'expect': e} for a, b, e in (
    ('Hyde Park', 'Hyde Park Investment Services', False), ('Computer Science', 'Computer Science and Economics', False),
    ('Master of Science', 'Master of Science in Data Science', False), ('May 2024', 'May 2024 2025', False),
    ('Yes', 'Yes, I am authorized to work', True), ('No', 'No - I would need sponsorship', False), ('F-1 (CPT)', 'F-1', True),
    ('Yes', 'Yes I do', True), ('No', 'Not sure', False), ('Yes', 'Yesterday', False), ('No', 'No, but I will need sponsorship later', False), ('Yes', 'Yes, I am not authorized', False), ('No', 'No - I require sponsorship', False), ('University of Chicago', 'University of Chicago - Booth', False), ('United States', 'United States of America', True), ('Bachelor', 'Bachelors', True), ('F-1', 'F-1 student visa', True), ('Yes', 'Yes, I am authorized', True), ("Master's", "Master's Degree", True), ("Master's Degree", "Master's", True), ("Bachelor's", "Bachelor's Degree in Economics", False), ('Data Science', 'Applied Data Science', False))]
bad = 0
for c in cases:
    got = SO.same(c['rule_value'], c['model_value'], c.get('options') or [])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['rule_value'], '/', c['model_value'], c.get('options'))
print(f'JSA-393: {len(cases)} cases · {len(verdicts)} verdicts · open disagreements {bad}')
sys.exit(1 if bad else 0)
