#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/rules_on_opt_cases.json, spec rules_on_opt_spec.md) against
answer_rules.js through rules_bridge.js: on_opt does not take authorization questions that name OPT only as an example (Goldman 2026-11-05).
Verdicts in rules_on_opt_verdicts.json.
    python3 scripts/test_rules_on_opt.py"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, os.path.join(HERE, '..', 'config'))
import jsa_profile  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'rules_on_opt_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'rules_on_opt_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    gpa = str(jsa_profile.get('answers.gpa.text') or '')
    qs = [{'key': str(i), 'label': c['label'], 'type': c.get('type') or 'text', 'options': c.get('options') or []} for i, c in enumerate(cases)]
    r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                       input=json.dumps(qs), capture_output=True, text=True)
    ans = json.loads(r.stdout)
    bad = 0
    for i, c in enumerate(cases):
        a = ans.get(str(i)) or {}
        got = str(a.get('value')) if a.get('status') == 'ok' and not a.get('leave') else 'none'
        want = str(c['expect']).replace('GPA_ON_FILE', gpa)
        if got.strip() == want.strip() or (not (c.get('type') in ('text', 'textarea')) and got.strip().lower() == want.strip().lower()):
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why'][:140]); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got)[:60], a.get('rule'), a.get('why') or '', 'want', repr(c['expect'])[:60], '|', c['label'][:110], c.get('options', [])[:5])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
