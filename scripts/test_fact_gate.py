#!/usr/bin/env python3
"""Harness for the fact gate (JSA-281, rule 13): DeepSeek-written cases (test_cases/fact_gate_cases.json from
fact_gate_spec.md), Claude's verdicts on disagreements in fact_gate_verdicts.json; plus the 11-10 audit cases."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import fact_gate  # noqa: E402

PROF = {'answers': {'conviction': {'yes': False}, 'start_date': {'text': '06/14/2027'}, 'ft_start': {'after': '2028-01'}},
        'work_auth': {'restricted': True},
        'education': [{'level': 'master', 'degree': 'M.S. Applied Data Science', 'major': 'Applied Data Science', 'current': True},
                      {'level': 'bachelor', 'degree': 'B.A. Economics', 'major': 'Economics'}],
        'qa': [{'q': "Do you have a valid driver's license?", 'yes': True},
               {'q': "What best describes the type of opportunities you're interested in:", 'pick': ['/product/i'], 'text': 'Product'}]}

AUDIT = [   # the 11-10 independent audit's wrong answers (labels as the forms wrote them) → must block
    ("As an insurance company, TalRosros … prohibits employing a person … convicted of certain felonies. TalRosros will conduct a post-offer criminal background check. "
     "Have you ever been convicted of a felony involving dishonesty, breach of trust, or a violation of the Act that would prohibit your employment in the business of insurance? "
     "(Please disclose any conviction, even if you believe said conviction may have been expunged or may no longer appear on your record or background check.)", 'Yes', 'select', [], '', 'fact:conviction'),
    ('Are you legally authorized to work for any U.S Employer?', 'Yes', 'select', ['Yes', 'No'], 'rules:authorized', 'fact:any_employer'),
    ('Undergrad Discipline(s)', 'Data Science', 'multi', ['Economics', 'Data Science'], 'rules:discipline', 'fact:major'),
    ('Secondary Major', 'Data Science', 'select', ['Data Science', 'Economics'], 'rules:discipline', 'fact:major'),
    ('Level of education completed once you’ve graduated?', 'Bachelor', 'select', ['Bachelor', 'Masters'], 'rules:qa:146', 'fact:degree_level'),
    ('What is your target compensation (salary and bonus)?', '^agree$', 'text', [], 'rules:qa:118', 'fact:pattern'),
    ('Are you currently pursuing a Bachelor’s, Master’s, or PhD in Data Science, Computer Science, Math, Physics, Economics, Statistics, Engineering, or another quantitative field?', 'No', 'radio', ['Yes', 'No'], 'rules:qa:9', 'fact:degree_level'),
    ('What is your availability to start a new position?', '6/1/2027', 'date', [], 'answers.json', 'fact:start_date'),
    ("What best describes the type of opportunities you're interested in:", 'Machine Learning', 'multi', ['Machine Learning', 'Product'], 'answers.json', 'fact:qa'),
]


def main():
    bad = 0
    for lab, val, typ, opts, src, want in AUDIT:
        m = fact_gate.check(lab, val, PROF, typ, None, opts, src)
        if not m or m['key'] != want:
            bad += 1; print('FAIL audit', lab[:70], '→', m and m['key'], 'want', want)
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'fact_gate_cases.json'), encoding='utf-8'))
    vp = os.path.join(HERE, 'test_cases', 'fact_gate_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    for c in cases:
        m = fact_gate.check(c['label'], c.get('value'), PROF, c.get('type') or '', None, c.get('options') or [], c.get('source') or '')
        got = 'block:' + m['key'].split(':', 1)[1] if m else 'pass'
        if got != c['expect'] and c['name'] not in verdicts:
            bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '|', c['label'][:100], '|', str(c.get('value'))[:40], c.get('source'))
    # JSA-310 (Joey 2026-11-11, work_auth.claim_authorized): authorization = Yes; a No is the mismatch; sponsorship / permanent untouched
    P2 = dict(PROF, work_auth={'restricted': True, 'claim_authorized': True})
    for lab, val, want in (('Are you legally authorized to work for any U.S Employer?', 'Yes', None),
                           ('Are you legally authorized to work for any U.S Employer?', 'No', 'fact:any_employer'),
                           ('Are you authorized to work in the U.S. without restriction?', 'No, I am not authorized', 'fact:any_employer'),
                           ('Are you authorized to work in this country for any employer?', 'Yes, I am authorized to work in this country for any employer', None),
                           ('Are you permanently authorized to work for any employer in the United States?', 'No', None),
                           ('Are you authorized to work for any employer without the current or future need for sponsorship?', 'No', None)):
        m = fact_gate.check(lab, val, P2, 'select', None, ['Yes', 'No'], 'rules:authorized')
        if (m and m['key']) != want:
            bad += 1; print('FAIL JSA-310', lab[:70], val, '→', m and m['key'], 'want', want)
    P3 = dict(P2, answers=dict(PROF['answers'], citizen_pr={'yes': False}))   # JSA-310 (KBR): authorized AS a citizen / PR → No
    for lab, val, want in (('Are you currently lawfully authorized to work in the U.S., as a (i) U.S. citizen or national; or (ii) permanent resident?', 'Yes', 'fact:citizen_pr'),
                           ('Are you currently lawfully authorized to work in the U.S., as a (i) U.S. citizen or national; or (ii) permanent resident?', 'No', None),
                           ('Are you legally authorized to work in the United States (e.g., U.S. citizen, permanent resident, F-1 OPT)?', 'Yes', None)):
        m = fact_gate.check(lab, val, P3, 'select', None, ['Yes', 'No'], 'rules:authorized')
        if (m and m['key']) != want:
            bad += 1; print('FAIL JSA-310 citizen', lab[:70], val, '→', m and m['key'], 'want', want)
    # learned values pass (the user confirmed one for this tenant)
    m = fact_gate.check('Undergrad Discipline(s)', 'Other', PROF, 'select', {'fact:major': ['Other']})
    if m:
        bad += 1; print('FAIL learned value still blocks')
    print(f'{len(AUDIT)} audit cases + {len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
