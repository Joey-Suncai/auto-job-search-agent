#!/usr/bin/env python3
"""JSA-261 (rule 13): DeepSeek-written cases from scripts/test_cases/audit_source_spec.md (audit_source_cases.json) for
audit_sample.source_check — any filled job-source answer is right (Joey 2026-11-09). Offline.
python3 scripts/test_audit_source.py"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['JSA_HOME'] = tempfile.mkdtemp(prefix='jsa_src_')
sys.path.insert(0, HERE)
import audit_sample as A  # noqa: E402

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'audit_source_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
cases = json.load(open(os.path.join(CASES, 'audit_source_cases.json')))
bad = 0
for c in cases:
    got = A.source_check(c['args']['question'], c['args']['answer'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1
        print('FAIL', c['name'], c['args'], 'expect', c['expect'], 'got', got)
# fixed: the Harmorquin wording the audit once judged wrong
if A.source_check('Please provide the name of the job board where you learned about this position.', 'Other') != 'right':
    bad += 1
    print('FAIL fixed: Harmorquin job board')
for q, a, e in [('How Did You Hear About Us?', 'Arrowstreet Contacted Me', None), ('How Did You Hear About Us?', 'Staffing Company / Agency', None),
                ('How Did You Hear About Us?', 'Integrated Agency Search Firm', None), ('How Did You Hear About Us?', 'Billboard', 'right'),
                ('How Did You Hear About Us?', 'Campus Recruiting Event', 'right')]:
    if A.source_check(q, a) != e:
        bad += 1
        print('FAIL fixed:', a)
print(f'audit_source: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) + fixed checks — fails {bad}')
sys.exit(1 if bad else 0)
