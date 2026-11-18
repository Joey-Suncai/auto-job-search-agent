"""run_wd.record_field and learn/convert_fields.wd_field (JSA-320, rule 13): DeepSeek's cases in test_cases/wd_record_cases.json, written from
test_cases/wd_record_spec.md and not from the code. Claude judges any disagreement in wd_record_verdicts.json.
Plus the replay of the miss: the UIUC GPA box held the résumé parse 3.85 before the fill and 3.60 after it. The record
must say 3.60 (page) and keep 3.85 only as `before`."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
from run_wd import record_field  # noqa: E402
sys.path.insert(0, os.path.join(HERE, 'learn'))
from convert_fields import wd_field, rows_of  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'wd_record_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'wd_record_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = record_field(c['input'])
    if got != c['expect']:
        if c['name'] in verdicts:
            print(f"judged  {c['name']} — {verdicts[c['name']][:90]}")
        else:
            bad += 1
            print(f"DISAGREE {c['name']} | got {json.dumps(got)} | expect {json.dumps(c['expect'])}")
r = record_field({'label': 'Overall Result (GPA)', 'section': 'Education 2', 'type': 'text', 'required': False, 'answer': '3.60',
                  'value': '3.85', 'status': 'ok', 'source': 'profile', 'readback': '3.60', 'readback_ok': True})
ok = r['page'] == '3.60' and r['value'] == '3.60' and r['before'] == '3.85' and r['ok'] is True
print(('PASS  ' if ok else 'FAIL  ') + 'Hartalcor / Wynvernev replay: GPA recorded as the filled 3.60, the résumé parse 3.85 only as before')
bad += 0 if ok else 1
cases2 = json.load(open(os.path.join(HERE, 'test_cases', 'wd_field_cases.json')))
for c in cases2:
    inp = json.loads(json.dumps(c['f']))
    got = wd_field(inp, {tuple(x) for x in c.get('failed') or []})
    if got != c['expect'] or inp != c['f']:
        if c['name'] in verdicts:
            print(f"judged  {c['name']} — {verdicts[c['name']][:90]}")
        else:
            bad += 1
            print(f"DISAGREE wd_field {c['name']} | got {json.dumps(got)} | expect {json.dumps(c['expect'])}")
wynvernev = os.path.expanduser('~/JobAgent/data/applications/2026-11-01_Wynvernev_Intern_AI_Innovation_Engineer')
if os.path.isdir(wynvernev):                               # the live replay: the old Wynvernev log read the way the corpus reads it now
    rows = rows_of(wynvernev)[2]
    gpa = [r['page'] for r in rows if r['question'] == 'Overall Result (GPA)' and r['planned']]
    ok = gpa == ['3.60']
    print(('PASS  ' if ok else 'FAIL  ') + f'Wynvernev 11-01 (old log): the corpus now reads the UIUC GPA as {gpa} (Review screenshot: 3.60)')
    bad += 0 if ok else 1
print(f'{len(cases)} + {len(cases2)} cases + replays · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
