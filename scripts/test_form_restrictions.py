#!/usr/bin/env python3
"""JSA-231 (rule 13): form_restrictions.find() / applies() on DeepSeek-written cases (test_cases/form_restrictions_cases.json,
verdicts in form_restrictions_verdicts.json), plus fixed checks: check_batch() turns a restricted prep row into
'ineligible_form' and marks the store (stub), and eligibility_merge keeps elig_form on a later gate run.
Offline.      python3 scripts/test_form_restrictions.py"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import form_restrictions as FR  # noqa: E402
import eligibility_merge as EM  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'form_restrictions_cases.json')))
cases = (cases.get('cases', cases) if isinstance(cases, dict) else cases) + json.load(open(os.path.join(HERE, 'test_cases', 'form_restrictions_sanctions_cases.json'))) + json.load(open(os.path.join(HERE, 'test_cases', 'form_restrictions_ask_cases.json')))   # JSA-237 sanctions guard + asking ≠ requiring
vp = os.path.join(HERE, 'test_cases', 'form_restrictions_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    hits = FR.find({'fields': [dict(c['field'], key='q1')]})
    got = {'kind': hits[0]['kind'] if hits else None, 'blocks': FR.applies(hits, {'citizen_or_pr': c['citizen']})}
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'], '\n   ', c['field'].get('label')[:200], c['field'].get('options'))


def check(name, ok):
    global bad
    if not ok:
        bad += 1; print('FAIL', name)


sanctions = {'fields': [{'key': 'q7', 'label': 'Please confirm whether any of the below applies to you. Select all that apply. Note: This information will only be used to ensure compliance with U.S. sanctions and export controls.',
                         'options': ['Citizen or permanent resident of Cuba, Iran, North Korea, or Syria', 'Ordinarily a resident of Cuba, Iran, North Korea, Syria or the Crimea, Donetsk, Luhansk, Zaporizhzhia, or Kherson regions of Ukraine',
                                     'Ordinarily a resident of Russia or Belarus and not willing to relocate for a Kelnevbra role', 'None of the above']}]}
check('sanctions screen (embargoed countries) is not a restriction (Kelnevbra 11-06)', FR.find(sanctions) == [])
divergent = {'fields': [{'key': 'q9', 'label': 'This position requires access to information and technology that is subject to US export controls. Are you any of the following “protected individuals” as defined in the Immigration and Naturalization Act, 8 USC 1324b(a)(3)?',
                         'options': ['US citizen or national', 'US permanent resident (i.e., "green card holder")', 'None of the above']},
                        {'key': 'q1', 'label': 'Are you legally authorized to work in the United States?', 'options': ['Yes', 'No']}]}
with tempfile.TemporaryDirectory() as d:
    for name, plan in (('a', divergent), ('b', {'fields': [{'key': 'q1', 'label': 'Are you a U.S. citizen?'}]})):
        os.makedirs(os.path.join(d, name)); json.dump(plan, open(os.path.join(d, name, 'plan.json'), 'w'))
    marked = []
    st = [{'id': 'J1', 'company': 'Divergent', 'title': 'BI Intern', 'folder': 'a', 'status': 'ok'},
          {'id': 'J2', 'company': 'X', 'title': 'Y', 'folder': 'b', 'status': 'ok'},
          {'id': 'J3', 'company': 'Z', 'title': 'W', 'folder': 'a', 'status': 'closed_or_not_greenhouse'}]
    FR.check_batch(st, lambda f: os.path.join(d, f), cand={'citizen_or_pr': False}, mark=lambda i, h: marked.append(i) or True, log=lambda s: None)
    check('restricted row → ineligible_form', st[0]['status'] == 'ineligible_form' and 'why' in st[0])
    check('status question only → ok', st[1]['status'] == 'ok')
    check('non-ok row untouched', st[2]['status'] == 'closed_or_not_greenhouse')
    check('store marked once', marked == ['J1'])
    st2 = [{'id': 'J1', 'folder': 'a', 'status': 'ok'}]
    FR.check_batch(st2, lambda f: os.path.join(d, f), cand={'citizen_or_pr': True}, mark=lambda i, h: marked.append(i) or True, log=lambda s: None)
    check('citizen passes', st2[0]['status'] == 'ok' and marked == ['J1'])
    # the merge step keeps the form verdict when the JD alone says 可投
    jobs = [{'id': 'J1', 'company': 'Divergent', 'title': 'BI Intern', 'level': 'Internship', 'location': 'Los Angeles, CA', 'score': 50,
             'tier': 'A', 'elig': '不可投', 'elig_form': {'kind': 'export_control', 'label': 'x', 'at': '2026-11-06'}}]
    jp, rp, op = (os.path.join(d, n) for n in ('jobs.json', 'res.json', 'out.json'))
    json.dump(jobs, open(jp, 'w')); json.dump({'J1': {'v': 'Eligible', 'c': 'GRAD_OK', 'e': '', 'key': 'gh:x:1'}}, open(rp, 'w'))
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        EM.main(jp, rp, op, '2026-11-07')
    o = json.load(open(op))[0]
    check('merge keeps elig_form', o['elig'] == '不可投' and 'FORM_RESTRICTION' in o['elig_codes'] and o['tier'] == 'Blocked')
print(f"{len(cases)} cases + fixed checks · disagreements without a verdict: {bad}")
sys.exit(1 if bad else 0)
