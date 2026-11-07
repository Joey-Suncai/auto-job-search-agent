#!/usr/bin/env python3
"""JSA-231 phase 2 (rule 13): gate_second_read.pick() / decide() on DeepSeek-written cases
(test_cases/gate_second_read_cases.json, verdicts in gate_second_read_verdicts.json), plus fixed checks of the cache
(a re-run gives the same result with no call), the call cap, the error path and the candidate prompt (from config,
no personal facts in code). Offline: DeepSeek is a stub.      python3 scripts/test_gate_second_read.py"""
import importlib.util, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('sr', os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts', 'gate_second_read.py'))
sr = importlib.util.module_from_spec(spec); spec.loader.exec_module(sr)
cases = json.load(open(os.path.join(HERE, 'test_cases', 'gate_second_read_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'gate_second_read_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    r = dict(c['rule'], e='rule evidence')
    out = sr.decide(r, sr.pick(r), c['ds'])
    got = {'v': out['v'], 'ds_code': sr.DS_CODE in sr.codes_of(out), 'ds_attached': 'ds' in out}
    orig_kept = all(x in sr.codes_of(out) for x in sr.codes_of(r))
    if (got != c['expect'] or not orig_kept) and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], c['rule'], c['ds'], '| got', got, '| expect', c['expect'])


def check(name, ok):
    global bad
    if not ok:
        bad += 1; print('FAIL', name)


# cache: the second run makes no call and gives the same verdicts; the cap limits new calls; errors keep the rule verdict
calls = []
def stub(msg):
    calls.append(msg)
    if 'BROKEN' in msg: raise RuntimeError('net down')
    return {'eligible': 'yes' if 'Summer' in msg else 'no', 'notes': 'stub', 'blocking': []}
pad = ' lorem ipsum' * 30
jds = {f'J{i}': {'id': f'J{i}', 'title': ('Summer ' if i % 2 else 'Fall ') + f'Intern {i}', 'loc': 'Chicago, IL', 'level': 'Internship', 'text': 'x' + pad} for i in range(6)}
jds['J5']['title'] = 'BROKEN Summer Intern'
base = {i: {'v': 'Ineligible', 'c': 'OFF_CYCLE', 'e': 'ev'} for i in jds}
base['J4'] = {'v': 'Ineligible', 'c': 'CITIZEN_OR_CLEARANCE', 'e': 'ev'}
with tempfile.TemporaryDirectory() as d:
    cp = os.path.join(d, 'c.jsonl')
    r1, s1 = sr.apply({k: dict(v) for k, v in base.items()}, jds, sr.Reader(cp, 'SYS', ask=stub), ds_max=10, workers=2)
    n1 = len(calls)
    r2, s2 = sr.apply({k: dict(v) for k, v in base.items()}, jds, sr.Reader(cp, 'SYS', ask=stub), ds_max=10, workers=2)
    check('hard block not re-read', 'ds' not in r1['J4'] and r1['J4']['v'] == 'Ineligible')
    check('yes → Review', r1['J1']['v'] == 'Review' and sr.DS_CODE in r1['J1']['c'])
    check('no → stays Ineligible', r1['J0']['v'] == 'Ineligible' and 'ds' in r1['J0'])
    check('error → rule verdict, no ds', r1['J5'] == base['J5'])
    check('first run calls 5', n1 == 5)
    check('re-run: only the failed one is asked again', len(calls) == n1 + 1)
    check('re-run same verdicts', all(r1[k] == r2[k] for k in r1))
    calls.clear()
    r3, s3 = sr.apply({k: dict(v) for k, v in base.items()}, jds, sr.Reader(os.path.join(d, 'c2.jsonl'), 'SYS', ask=stub), ds_max=2, workers=2)
    check('cap: 2 calls', len(calls) == 2 and s3['skipped_cap'] == 3)
    check('cap: unread rows unchanged', sum(1 for k in r3 if r3[k] == base[k]) == 4)
# weekly audit: samples only single hard block codes, lists DeepSeek disagreements in the report
with tempfile.TemporaryDirectory() as d:
    res = {f'H{i}': {'v': 'Ineligible', 'c': 'CITIZEN_OR_CLEARANCE', 'e': 'ev'} for i in range(8)}
    res['S1'] = {'v': 'Ineligible', 'c': 'OFF_CYCLE', 'e': 'ev'}
    jd = {i: {'id': i, 'title': ('Summer ' if i in ('H1', 'H2') else '') + 'Intern', 'text': 'x' + pad} for i in res}
    md = os.path.join(d, 'audit.md')
    cnt = sr.weekly_audit(res, jd, sr.Reader(None, 'SYS', ask=stub), md, per_code=8, seed=1)
    txt = open(md).read()
    check('audit counts', cnt['CITIZEN_OR_CLEARANCE'] == {'sampled': 8, 'disagree': 2} and cnt['OFF_CYCLE' if 'OFF_CYCLE' in cnt else 'NON_US'] == {'sampled': 0, 'disagree': 0})
    check('audit lists disagreements', '| H1 |' in txt and '| H2 |' in txt and '| H3 |' not in txt)
# the candidate paragraph follows config (F-1 default vs citizen), no school names in code
t1 = sr.candidate_text({'needs_sponsorship': True, 'citizen_or_pr': False, 'grad': '2027-12', 'degree_level': 'masters', 'intern_summer': 2027, 'fulltime_from': '2028-01'})
t2 = sr.candidate_text({'needs_sponsorship': False, 'citizen_or_pr': True, 'grad': '2026-05', 'degree_level': 'bachelors', 'intern_summer': 2026})
check('F-1 prompt', 'CPT' in t1 and 'December 2027' in t1 and "master's" in t1 and 'January 2028' in t1)
check('citizen prompt', 'CPT' not in t2 and 'May 2026' in t2 and "bachelor's program" in t2 and 'Summer 2026' in t2)
check('no school names', 'Chicago' not in sr.SYSTEM + t1 and 'UIUC' not in t1)
print(f"{len(cases)} cases + fixed checks · disagreements without a verdict: {bad}")
sys.exit(1 if bad else 0)
