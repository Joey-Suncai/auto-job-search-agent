#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/rules_sf_jsa232_cases.json) against answer_rules.js through
rules_bridge.js, as the SuccessFactors runner does (JSA-232, Ostlumcor 2026-11-10): relatives asked as "related to anyone
that works for <Co>", the closing "I HAVE READ AND AGREE WITH THE ABOVE STATEMENTS", and "Do you wish to furnish this
information?" (Joey 2026-11-10: Yes, his saved answer in config/profile.json qa). Verdicts in rules_sf_jsa232_verdicts.json.
    python3 scripts/test_rules_sf_jsa232.py"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, os.path.join(HERE, '..', 'config'))
sys.path.insert(0, RUN)
import jsa_profile  # noqa: E402
import run_successfactors as S  # noqa: E402

VIS = {'pick': ['/^any\\b.{0,80}\\brecruiters?\\b.{0,30}\\bworldwide\\b/i'], 'text': 'Any recruiter worldwide'}


FURNISH = {'q': 'Do you wish to furnish this information?', 'yes': True, 'source': 'Joey 2026-11-10 (Ostlumcor, SuccessFactors EEO)',
           'match': r"/^\W*do you wish to (furnish|provide|disclose|share) (this|the following|your) (voluntary )?(self[- ]identification )?information\W*$|^\W*do you wish to (voluntarily )?self[- ]identify\W*$/i"}


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'rules_sf_jsa232_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'rules_sf_jsa232_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    prof = jsa_profile.load()
    prof.setdefault('answers', {}).setdefault('profile_visibility', VIS)
    if not any('furnish' in str(q.get('q', '')) for q in prof.get('qa') or []):   # the repo's test profile is older than Joey's 11-10 answer
        prof.setdefault('qa', []).append(FURNISH)
    with tempfile.TemporaryDirectory() as td:
        pf = os.path.join(td, 'profile.json'); json.dump(prof, open(pf, 'w'))
        qs = [{'key': str(i), 'label': S.label_from_options(c['label'], c.get('options')) if c.get('type') in ('select', 'radio') else c['label'],
               'type': c.get('type') or 'text', 'options': c.get('options') or []} for i, c in enumerate(cases)]
        r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                           input=json.dumps(qs), capture_output=True, text=True, env=dict(os.environ, JSA_PROFILE=pf))
    ans = json.loads(r.stdout or '{}')
    if not ans:
        print(r.stderr[:500]); return 1
    bad = 0
    for i, c in enumerate(cases):
        a = ans.get(str(i)) or {}
        got = str(a.get('value')) if a.get('status') == 'ok' and not a.get('leave') else 'none'
        if got.strip() == str(c['expect']).strip():
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why'][:140]); continue
        bad += 1; print('FAIL ', c['name'], 'got', repr(got)[:60], a.get('rule'), a.get('why') or '', 'want', repr(c['expect'])[:60], '|', qs[i]['label'][:110], c.get('options', [])[:6])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
