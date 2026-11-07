#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/referrer_pool_cases.json, spec referrer_pool_spec.md) against
answer_rules.js through rules_bridge.js with the hiring company (JSA-195, Joey 2026-11-05): company in the referrer pool →
ask, not in it → No / N/A / None, none given → ask; recruiter and how-did-you-hear questions unaffected. The pool is the
spec's fictional one ($JSA_CONNECTIONS), the profile the live one without its qa table. Verdicts in referrer_pool_verdicts.json.
    python3 scripts/test_referrer_pool.py"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, HERE)
import test_sr_1105 as T  # noqa: E402  (profile_without_qa)

POOL = {'connections': {
    'amazon': [['Pat Lee', 'Engineer @ Amazon'], ['Sam Ortiz', 'Solutions Architect @ AWS']],
    'ernst and young': [['Dana Fox', 'Tax Analyst @ EY']],
    'micron': [['Lee Chan', 'Product Manager @ Micron']],
    'tiktok': [['Robin Wu', 'Product Manager @ TikTok']],
    'bytedance': [['Kim Park', 'Product @ ByteDance']],
    'rosostbra': [['Alex Grant', 'Vice President']],
    'university of chicago': [['Jordan Hale', 'Lecturer']],
    'ostrosros': [['Casey Moore', 'Product Manager @ OSTROSROS']]}, 'alumni_link': {'acme corp': 'Former Acme analyst'}}


def answers(cases):
    """One rules_bridge call per company (the bridge takes one company per call, like a runner)."""
    prof = T.profile_without_qa()
    pool = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8'); json.dump(POOL, pool); pool.close()
    out = {}
    try:
        for co in dict.fromkeys(c['args'].get('company') for c in cases):
            qs = [{'key': str(i), 'label': c['args']['label'], 'type': c['args']['type'], 'options': c['args'].get('options') or []}
                  for i, c in enumerate(cases) if c['args'].get('company') == co]
            r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                               input=json.dumps({'fields': qs, 'jd': '', 'company': co}), capture_output=True, text=True,
                               env=dict(os.environ, JSA_PROFILE=prof, JSA_CONNECTIONS=pool.name))
            out.update(json.loads(r.stdout or '{}'))
    finally:
        os.unlink(prof); os.unlink(pool.name)
    return out


def check(e, a):
    if e.get('status') == 'unknown':
        return a.get('status') == 'unknown' and (not e.get('ask') or bool(a.get('ask')))
    if e.get('leave'):
        return a.get('status') == 'ok' and bool(a.get('leave')) and not a.get('value')
    return a.get('status') == 'ok' and not a.get('leave') and str(a.get('value')) == str(e.get('value'))


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'referrer_pool_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'referrer_pool_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    ans = answers(cases)
    bad = 0
    for i, c in enumerate(cases):
        a = ans.get(str(i)) or {}
        if check(c['expect'], a):
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        got = {k: a.get(k) for k in ('status', 'rule', 'value', 'leave', 'ask', 'why') if a.get(k) not in (None, '')}
        bad += 1; print('FAIL ', c['name'], '| company', c['args'].get('company'), '| got', json.dumps(got)[:300], '| want', json.dumps(c['expect']))
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
