"""rules_bridge.ynTextBox (JSA-322, rule 13): DeepSeek's cases in test_cases/yn_textbox_cases.json (from
yn_textbox_spec.md, not the code), Claude's verdicts in yn_textbox_verdicts.json. Plus the GALLUMPELL replay: the optional box
"Is there any other context you'd like to share about your U.S. Immigration sponsorship needs?" gets no bare "Yes"."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
RULES = os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js')
cases = json.load(open(os.path.join(HERE, 'test_cases', 'yn_textbox_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'yn_textbox_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
js = ("const {ynTextBox}=require(%r);let s='';process.stdin.on('data',d=>s+=d).on('end',()=>"
      "process.stdout.write(JSON.stringify(JSON.parse(s).map(l=>ynTextBox(l)))))") % os.path.join(RUNNER, 'rules_bridge.js')
got = json.loads(subprocess.run(['node', '-e', js], input=json.dumps([c['label'] for c in cases]), capture_output=True, text=True, check=True).stdout)
bad = 0
for c, g in zip(cases, got):
    if g != c['expect']:
        if c['name'] in verdicts:
            print(f"judged  {c['name']} — {verdicts[c['name']][:90]}")
        else:
            bad += 1
            print(f"DISAGREE {c['name']} | {c['label']!r} got {g} expect {c['expect']}")
imc = [{'key': 'q', 'label': 'Is there any other context you’d like to share about your U.S. Immigration sponsorship needs?', 'type': 'textarea', 'options': []},
       {'key': 'w', 'label': 'Will you require immigration sponsorship in the future to continue working for GALLUMPELL?', 'type': 'text', 'options': []}]
env = dict(os.environ, CX_WHOLE_READ='0', JSA_NO_PUSH='1')
out = json.loads(subprocess.run(['node', os.path.join(RUNNER, 'rules_bridge.js'), RULES], input=json.dumps(imc), capture_output=True, text=True, env=env, check=True).stdout)
checks = [('GALLUMPELL: the "any other context" box gets no bare Yes', not (out['q'].get('status') == 'ok' and str(out['q'].get('value')).lower() in ('yes', 'no'))),
          ('a yes/no sponsorship question as a text box still gets its answer', out['w'].get('status') == 'ok' and out['w'].get('value') == 'Yes')]
for n, ok in checks:
    print(('PASS  ' if ok else 'FAIL  ') + n + ('' if ok else f'  {out}'))
bad += sum(1 for _, ok in checks if not ok)
print(f'{len(cases)} cases + {len(checks)} checks · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
