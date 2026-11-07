#!/usr/bin/env python3
"""Harness for the 2026-11-05 Workday fixes (rule 13: DeepSeek wrote the cases from the specs, Claude judges):
JSA-206 eeo_left_empty (a free-text box that lists protected categories is not an EEO question) ·
JSA-207 wd_signin.message_kind / failure_code (why sign-in failed after the create-account form).
Specs + cases in test_cases/wd_eeo_review_* and wd_signin_fail_*; verdicts (case misreads the spec) in <name>_verdicts.json.
Plus sanitized fixtures from the 11-05 rerun (Central Hudson Review; gaig / aba / Invesco sign-in traces)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_wd, wd_signin

def run(name, call, same=lambda a, b: a == b):
    cases = json.load(open(os.path.join(HERE, 'test_cases', f'{name}_cases.json')))
    vp = os.path.join(HERE, 'test_cases', f'{name}_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        if c.get('ambiguous') and c['name'] in verdicts: continue
        got = call(c)
        if not same(got, c['expect']) and c['name'] not in verdicts:
            bad += 1; print(f'DISAGREE {name}/{c["name"]} | got {got!r} | expect {c["expect"]!r} | {json.dumps(c, ensure_ascii=False)[:300]}')
    print(f'{name}: {len(cases)} cases · disagreements without a verdict: {bad}')
    return bad

norm = lambda xs: [re.sub(r'\s+', ' ', str(x)).strip().rstrip('*').strip().lower() for x in xs]
bad = run('wd_eeo_review', lambda c: run_wd.eeo_left_empty(c['review_text'], c.get('free_text_labels') or []),
          same=lambda a, b: norm(a) == norm(b))
bad += run('wd_signin_fail', lambda c: wd_signin.message_kind(c['text']) if c['fn'] == 'message_kind' else wd_signin.failure_code(c['t']))

# ---- fixtures from the 11-05 rerun (personal data removed)
fails = 0
def T(name, ok, got=''):
    global fails
    fails += (not ok); print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  -> {got}'))

CIVIC = ('Please list professional, trade, business or civic activities and offices held: (Exclude those which would reveal sex, '
         'race, religion, national origin, age, ancestry, sexual orientation, physical or mental disability or other protected status).')
review = ('Application Questions\nDo you have any friends working for the company?*\nNo\n'
          'List relevant certifications and/or specialized technical licenses.\nNo Response\n' + CIVIC + '\nNo Response\n'
          'What is your desired annual salary or wage?*\nOpen / per internship program standard\n'
          'Voluntary Disclosures\nPlease select your gender.\nI do not wish to answer\nVeteran Status*\nI am not a protected veteran\n')
T('Central Hudson Review: the civic-activities box does not block', run_wd.eeo_left_empty(review, []) == [], run_wd.eeo_left_empty(review, []))
T('Central Hudson Review: also as a recorded free-text box', run_wd.eeo_left_empty(review, [CIVIC]) == [])
T('a real EEO question left empty still blocks', run_wd.eeo_left_empty(review.replace('I do not wish to answer', 'No Response'), [CIVIC])
  == ['Please select your gender.'])
T('one-line form ("Veteran Status* No Response") still blocks', run_wd.eeo_left_empty('Veteran Status* No Response', []) == ['Veteran Status'])
T('free-text label match by the first 60 characters', run_wd.eeo_left_empty('Tell us about your veteran service history (optional)\nNo Response',
                                                                             ['Tell us about your veteran service history (optional) ']) == [])

T('tenant_key gaig', wd_signin.tenant_key('https://gaig.wd1.myworkdayjobs.com/en-US/GAIG_External/job/X_R1') == 'gaig')
T('tenant_key myworkdaysite', wd_signin.tenant_key('https://wd3.myworkdaysite.com/recruiting/kelkeltal/x') == 'kelkeltal')
T('tenant_key other host', wd_signin.tenant_key('https://example.com/x') == '')
base = {'created': True, 'exists_msg': False, 'verify_banner': False, 'verified': False, 'agent_since': wd_signin.AGENT_SINCE}
gaig = dict(base, error='wrong_password', tried_long=True, mails=[{'date': '2025-10-21', 'kind': 'other'}, {'date': '2025-10-22', 'kind': 'other'}])
T('gaig 11-05: own application mails from 2025, no verify mail → old_account', wd_signin.failure_code(gaig) == 'old_account', wd_signin.failure_code(gaig))
aba = dict(base, error='wrong_password', tried_long=True, mails=[{'date': '2025-10-31', 'kind': 'other'}])
T('aba 11-05 → old_account', wd_signin.failure_code(aba) == 'old_account')
ivz = dict(base, error='none', mails=[{'date': '2026-11-01', 'kind': 'verify'}])
T('Invesco 11-05: agent account (verified 11-01), no recognisable answer → no_answer', wd_signin.failure_code(ivz) == 'no_answer', wd_signin.failure_code(ivz))
T('Invesco with a wrong-password message → agent_account_password', wd_signin.failure_code(dict(ivz, error='wrong_password')) == 'agent_account_password')
T('every failure code has a queue text', all(k in wd_signin.JOEY_TODO for k in ('locked', 'old_account', 'agent_account_password', 'no_verify_mail', 'no_answer', 'other')))
T('queue texts never say the agent resets a password', not any(re.search(r'agent (will )?(reset|change)', v) for v in wd_signin.JOEY_TODO.values()))
print(f'fixtures fails {fails}')
sys.exit(1 if bad or fails else 0)
