#!/usr/bin/env python3
"""Harness for the phone-number rule (rule 13) in BOTH places: run_form.is_phone (Python) and verify.js isPhone (page
script, evaluated with node). DeepSeek cases; Claude's verdicts in is_phone_verdicts.json."""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'); sys.path.insert(0, R)
import run_form
cases = json.load(open(os.path.join(HERE, 'test_cases', 'is_phone_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'is_phone_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
js = re.search(r'function isPhone\(f\) \{.*?\n', open(os.path.join(R, 'verify.js'), encoding='utf-8').read()).group(0)
node = subprocess.run(['node', '-e', js + 'const c=JSON.parse(require("fs").readFileSync(0));console.log(JSON.stringify(c.map(x=>isPhone(x.field))))'],
                      input=json.dumps(cases), capture_output=True, text=True, check=True)
jsres = json.loads(node.stdout)
bad = 0
for c, j in zip(cases, jsres):
    py = run_form.is_phone(c['field'])
    if (py != c['expect'] or j != c['expect']) and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| py', py, '| js', j, '| expect', c['expect'], '|', c['field'])
print(f'{len(cases)} cases (Python + verify.js) · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
