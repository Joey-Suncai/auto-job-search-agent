"""The canon's school question (JSA-321, rule 13): DeepSeek's cases in test_cases/canon_school_cases.json (written from
canon_school_spec.md, not the code), Claude's verdicts in canon_school_verdicts.json. Plus the replay of the miss and
"Other" checks: Harharpell 11-11 "Please specify the grading scale used by your current school" is not the school question;
a list without his schools (Quinkelver 10-31) makes "Other" right; an "If not listed" box with his school does too."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import canon  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'canon_school_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'canon_school_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = canon.classify(canon.question_of(c['label'])) == 'school'
    if got != c['expect']:
        if c['name'] in verdicts:
            print(f"judged  {c['name']} — {verdicts[c['name']][:90]}")
        else:
            bad += 1
            print(f"DISAGREE {c['name']} | {c['label']!r} got {got} expect {c['expect']}")
checks = [
    ('Harharpell: the grading-scale question is not the school question',
     canon.classify('Please specify the grading scale used by your current school.') != 'school'),
    ('Harharpell: "4.0 Scale" is not blocked', canon.audit([{'label': 'Please specify the grading scale used by your current school.', 'value': '4.0 Scale', 'required': True}]) == []),
    ('a bare School box still holds his school', canon.audit([{'label': 'School', 'value': 'XJTLU', 'required': True}]) != []),
    ('"What university are you currently enrolled with?" is checked now', canon.classify('What university are you currently enrolled with?') == 'school'),
    ('Quinkelver: "Other" from a list without his schools is right',
     canon.audit([{'label': 'Which college or university do you currently attend?', 'value': 'Other', 'required': True,
                   'options': ['Select...', 'Ohio State University', 'Purdue University', 'Other']}]) == []),
    ('Quinkelver: a "currently attend" list with UIUC but not UChicago — "Other" is right',
     canon.audit([{'label': 'Which college or university do you currently attend?', 'value': 'Other', 'required': True,
                   'options': ['Brown University', 'University of Illinois Urbana-Champaign (UIUC)', 'Other']}]) == []),
    ('Virtu: a "currently attending" list with "UChicago" — "Other" stops',
     canon.audit([{'label': 'Which university are you currently attending? Select "Other" if not listed', 'value': 'Other', 'required': True,
                   'options': ['Caltech', 'MIT', 'UChicago', 'Other']}]) != []),
    ('"Other" with the list unknown still stops', canon.audit([{'label': 'Which college or university do you currently attend?', 'value': 'Other', 'required': True}]) != []),
    ('"Other" from a list that has his school stops',
     canon.audit([{'label': 'School', 'value': 'Other', 'required': True, 'options': ['University of Chicago', 'Other']}]) != []),
    ('"Other" + "If your school is not listed, enter the school name" = UChicago is right (no entry labels)',
     canon.audit([{'label': 'School', 'value': 'Other', 'required': True},
                  {'label': 'If your school is not listed above, please enter the school name here', 'value': 'University of Chicago', 'required': False}]) == []),
]
for n, ok in checks:
    print(('PASS  ' if ok else 'FAIL  ') + n)
bad += sum(1 for _, ok in checks if not ok)
print(f'{len(cases)} cases + {len(checks)} checks · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
