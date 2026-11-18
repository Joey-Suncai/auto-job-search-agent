"""answer_rules.js opt-in boxes (JSA-329, rule 13): DeepSeek's cases in test_cases/optin_cases.json (from optin_spec.md,
not the code), Claude's verdicts in optin_verdicts.json. Plus the Hunt Oil replay of 2026-11-11: "I agree to receive
recruiting campaign communications." was checked (data_consent's "I agree") — it is the marketing opt-in → No, while the
same form's "I agree to receive updates about new job opportunities." stays Yes (talent community)."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js')
cases = json.load(open(os.path.join(HERE, 'test_cases', 'optin_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'optin_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
js = ("const {answerFor}=require(%r);let s='';process.stdin.on('data',d=>s+=d).on('end',()=>process.stdout.write("
      "JSON.stringify(JSON.parse(s).map(l=>answerFor({l,t:'checkbox',o:[]})))))") % os.path.abspath(RULES)
env = dict(os.environ, CX_WHOLE_READ='0', JSA_NO_PUSH='1')


def answers(labels):
    return json.loads(subprocess.run(['node', '-e', js], input=json.dumps(labels), capture_output=True, text=True, env=env, check=True).stdout)


def short(a):
    return a.get('value') if a.get('status') == 'ok' else 'ask'


bad = 0
for c, a in zip(cases, answers([c['label'] for c in cases])):
    g = short(a)
    if g != c['expect']:
        if c['name'] in verdicts:
            print(f"judged  {c['name']} — {verdicts[c['name']][:90]}")
        else:
            bad += 1
            print(f"DISAGREE {c['name']} | {c['label']!r} got {g} ({a.get('rule') or a.get('why')}) expect {c['expect']}")
hunt = answers(['I agree to receive recruiting campaign communications.', 'I agree to receive updates about new job opportunities.'])
checks = [('Hunt Oil: recruiting campaign communications → No (marketing)', short(hunt[0]) == 'No' and hunt[0].get('rule') == 'marketing'),
          ('Hunt Oil: updates about new job opportunities → Yes (talent community)', short(hunt[1]) == 'Yes' and hunt[1].get('rule') == 'future_contact')]
for n, ok in checks:
    print(('PASS  ' if ok else 'FAIL  ') + n + ('' if ok else f'  {hunt}'))
bad += sum(1 for _, ok in checks if not ok)
print(f'{len(cases)} cases + {len(checks)} checks · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
