#!/usr/bin/env python3
"""Harness for skills/job-hunt-pipeline/scripts/wellfound_apply.py (rule 13): DeepSeek cases from
scripts/test_cases/wellfound_apply_spec.md, verdicts in wellfound_apply_verdicts.json; plus the synthetic page fixtures
in scripts/test_cases/wellfound_apply_fixtures/ (selectors unverified until the first live run, JSA-171)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import wellfound_apply as W
TC = os.path.join(HERE, 'test_cases')
cases = [c for f in ('wellfound_apply_cases.json', 'wellfound_apply_b_cases.json', 'wellfound_apply_c_cases.json',
                                                     'wellfound_apply_d_cases.json') for c in json.load(open(os.path.join(TC, f)))]
vp = os.path.join(TC, 'wellfound_apply_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}


def run(c):
    f, a = c['fn'], c['args']
    if f == 'clean_url':
        return W.clean_url(a.get('url'))
    if f == 'posting_like':
        return W.posting_like(a.get('url'))
    if f == 'click_out_index':
        return W.click_out_index(a.get('labels'))
    if f == 'opened_stop':
        return W.opened_stop(a.get('info'))
    if f == 'pick_external':
        return W.pick_external(a.get('page') or {})
    if f == 'classify':
        r = W.classify(a.get('page') or {})
        return {k: r[k] for k in ('via', 'ats_url', 'apply_url')}
    r = W.page_from_html(a.get('html'), a.get('url') or '')
    exp = c['expect']
    got = {k: r[k] for k in exp if k in r}
    if 'text_contains' in exp:
        got['text_contains'] = [s for s in exp['text_contains'] if s in r['text']]
    return got


def norm_expect(c):
    e = c['expect']
    if c['fn'] == 'classify' and isinstance(e, dict):
        return {k: e.get(k, '') for k in ('via', 'ats_url', 'apply_url')}
    return e


bad = 0
for c in cases:
    got, exp = run(c), norm_expect(c)
    if got != exp and c['name'] not in verdicts:
        bad += 1
        print('DISAGREE', c['name'], '| got', json.dumps(got, ensure_ascii=False)[:400], '| expect', json.dumps(exp, ensure_ascii=False)[:400])

# synthetic fixtures (written by hand from common Wellfound page shapes — not live pages)
FX = os.path.join(TC, 'wellfound_apply_fixtures')
fx = json.load(open(os.path.join(FX, 'expect.json')))
for name, want in fx.items():
    page = W.page_from_html(open(os.path.join(FX, want.get('file', name)), encoding='utf-8').read(), want['url'])
    page.update(want.get('extra') or {})
    got = W.classify(page)
    if (got['via'], got['ats_url']) != (want['via'], want.get('ats_url', '')):
        bad += 1; print('FIXTURE', name, '| got', got, '| want', want)
# trimmed live page records (job Chrome, 11-05): the nav "Applied" tab is on every page; Apply is a button only;
# the last 3 are --click-out records (Workday, Lever, a LinkedIn job page — never an apply host)
live = json.load(open(os.path.join(FX, 'live_2026-11-05.json'), encoding='utf-8'))
for rec in live:
    got = W.classify({k: v for k, v in rec.items() if not k.startswith('expect_')})
    if got['via'] != rec['expect_via'] or got['ats_url'] != rec.get('expect_ats_url', got['ats_url']):
        bad += 1; print('LIVE', rec['url'], '| got', got, '| want', rec['expect_via'])
print(f'{len(live)} live records checked')
print(f'{len(cases)} cases + {len(fx)} fixtures · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
