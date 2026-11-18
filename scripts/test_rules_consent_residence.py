#!/usr/bin/env python3
"""Consent to future contact / "do you have housing in <city>" (JSA-363): DeepSeek-written cases
(scripts/test_cases/consent_residence_cases.json, from consent_residence_spec.md; the RBC case is the real Workday
question) against answer_rules.js. Verdicts (if any) in consent_residence_verdicts.json. Error classes: a pick pattern that
matches the NEGATED option ("I do not consent" ~ /^i (would|do)\\b/), and a place-of-residence question answered by a
generic housing-support rule.
    python3 scripts/test_rules_consent_residence.py"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'consent_residence_cases.json')))
    vp = os.path.join(HERE, 'test_cases', 'consent_residence_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    qs = [{'key': str(i), 'label': c['label'], 'type': 'radio' if c.get('options') else 'combo', 'options': c.get('options') or []} for i, c in enumerate(cases)]
    r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                       input=json.dumps(qs), capture_output=True, text=True,
                       env=dict(os.environ, JSA_PROFILE=os.path.join(HERE, '..', 'config', 'fixtures', 'f1_student', 'profile.json')))
    ans = json.loads(r.stdout)
    bad = 0
    for i, c in enumerate(cases):
        a = ans.get(str(i)) or {}
        got = str(a.get('value')) if a.get('status') == 'ok' and not a.get('leave') else 'none'
        if got.strip().lower() == str(c['expect']).strip().lower():
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got)[:60], a.get('rule'), 'want', repr(c['expect'])[:60], '|', c['label'][:90])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
