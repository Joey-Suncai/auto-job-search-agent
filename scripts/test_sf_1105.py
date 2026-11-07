#!/usr/bin/env python3
"""Runs the DeepSeek-written cases for the SuccessFactors helpers added after the 2026-11-05 batch (JSA-092 types S–W):
register form (sf_register_cases.json: pw_limits, pick_password, privacy_link, radio_question) and page helpers
(sf_page_1105_cases.json: chat_overlay, label_from_options, split_fix in run_successfactors.py; canon_label in
sf_background.py). Verdicts in <name>_verdicts.json. Plus fixed checks from the Acuity form (bg_plan with its labels).
Second 11-05 batch (types W–Y): sf_register_apply_cases.json (option_text, radio_selector, page_kind, accept_link,
privacy_accepted, account_ok) and sf_school_short_cases.json (school_words, school_fits, school_query, pick_school in
sf_combo_edu.py), plus fixed checks from the Newell / Danfoss / Acuity pages (fixed_1105b).
    python3 scripts/test_sf_1105.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_successfactors as S  # noqa: E402
import sf_background as B  # noqa: E402
import sf_combo_edu as CE  # noqa: E402

ENT = {'A': {'school': 'University of Chicago', 'short': 'UChicago'}, 'B': {'school': 'University of Illinois Urbana-Champaign', 'short': 'UIUC'}}


def _ent(a):
    return ENT[a['entry']] if 'entry' in a else {'school': a['school']}

FN = {'pw_limits': lambda a: list(S.pw_limits(a['text'])),
      'pick_password': lambda a: (lambda r: list(r) if r else None)(S.pick_password(a['text'], [tuple(x) for x in a['items']])),
      'privacy_link': lambda a: S.privacy_link(a['text']),
      'radio_question': lambda a: S.radio_question(a['texts'], a['options']),
      'chat_overlay': lambda a: S.chat_overlay(a['el']),
      'label_from_options': lambda a: S.label_from_options(a['label'], a['options']),
      'split_fix': lambda a: S.split_fix(a['field']),
      'canon_label': lambda a: B.canon_label(a['label'], a['kind']),
      'option_text': lambda a: S.option_text(a['c']),
      'radio_selector': lambda a: S.radio_selector(a['opt']),
      'page_kind': lambda a: S.page_kind(a['sig']),
      'accept_link': lambda a: S.accept_link(a['text']),
      'privacy_accepted': lambda a: S.privacy_accepted(a['text'], a.get('dpcs_value', '')),
      'account_ok': lambda a: S.account_ok(a['key'], a['want'], a['got']),
      'school_words': lambda a: CE.school_words(a['name']),
      'school_fits': lambda a: CE.school_fits(a['option'], _ent(a)),
      'school_query': lambda a: CE.school_query(_ent(a)),
      'pick_school': lambda a: list(CE.pick_school(a['options'], _ent(a)))}


def run_file(name):
    cases = json.load(open(os.path.join(HERE, 'test_cases', name + '_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', name + '_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    fails = 0
    for c in cases:
        try:
            got = FN[c['fn']](c['args'])
        except Exception as e:
            got = f'error {type(e).__name__}: {e}'
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why'][:140]); continue
        fails += 1; print('FAIL ', c['name'], '| got', repr(got)[:120], '| want', repr(c['expect'])[:120], '|', json.dumps(c['args'])[:200])
    print(f'{name}: {len(cases) - fails}/{len(cases)} ok')
    return fails


WORK = [{'match': 'hyde park', 'Job Title': 'Business Analyst Intern', 'Company': 'Hyde Park Investment Services, Inc.', 'Location': 'Champaign, Illinois',
         'From': '08/2025', 'To': '10/2025', 'current': False},
        {'match': 'frost', 'Job Title': 'Consulting Assistant Intern', 'Company': 'Frost & Sullivan', 'Location': 'Shanghai, China',
         'From': '06/2024', 'To': '08/2024', 'current': False}]
EDUS = [{'school': 'University of Chicago', 'match_re': 'chicago', 'level': 'master', 'major': 'Applied Data Science', 'start': '2026-09', 'end': '2027-12', 'current': True},
        {'school': 'University of Illinois Urbana-Champaign', 'match_re': 'illinois', 'level': 'bachelor', 'major': 'Economics', 'start': '2024-08', 'end': '2026-05'}]


def fixed():
    """The Lumsevsev 11-05 form: parser rows labelled "Company Name" / "Title" match the facts (before: unmatched + 2 rows added);
    education rows labelled "College/University" / "Degree/Certificate" / "Still Attending?" get values."""
    bad = []
    def row(c, t):
        return {'fields': [{'label': 'Present Employer', 'value': 'No', 'type': 'combo'}, {'label': 'Company Name', 'value': c, 'type': 'text'},
                           {'label': 'Title', 'value': t, 'type': 'text'}, {'label': 'Type of Business', 'value': '', 'type': 'combo'}],
                'dates': [{'name': 'Start Date', 'value': ''}, {'name': 'End Date', 'value': ''}]}
    for c1, c2 in ((S.unsplit('HYDE P ARK INVESTMENT S ERVICES'), S.unsplit('FROST & S ULLIVAN')), ('HYDE P ARK INVESTMENT S ERVICES', 'FROST & S ULLIVAN')):
        p = B.bg_plan({'head': 'Previous Employment', 'rows': [row(c1, 'Business Analyst Intern'), row(c2, 'Consulting Assistant Intern')]}, WORK, EDUS, today='2026-11')
        if p['unmatched'] or p['add'] or [r['who'] for r in p['rows']] != ['Hyde Park Investment Services, Inc.', 'Frost & Sullivan']:
            bad.append(f'work rows {c1!r}: {p}')
        elif p['rows'][0]['set'].get('Current') != '/^no\\b/i' or B.canon_label('Company Name', 'work') != 'Company':
            bad.append('work Current / Company Name')
    erow = {'fields': [{'label': 'Degree/Certificate', 'value': '', 'type': 'combo'}, {'label': 'College/University', 'value': '', 'type': 'combo'},
                       {'label': 'Major', 'value': '', 'type': 'combo'}, {'label': 'Still Attending?', 'value': '', 'type': 'combo'}],
            'dates': [{'name': 'Start Date', 'value': ''}, {'name': 'Degree/Certificate Completion Date', 'value': ''}, {'name': 'End Date', 'value': ''}]}
    p = B.bg_plan({'head': 'Education', 'rows': [erow, erow]}, WORK, EDUS, today='2026-11')
    s0, s1 = p['rows'][0]['set'], p['rows'][1]['set']
    if s0.get('Attending') != '/^yes\\b/i' or s1.get('Attending') != '/^no\\b/i' or 'Completion Date' in s0 or s1.get('Completion Date') != '05/31/2026' or s1.get('From Date') != '08/01/2024':
        bad.append(f'education values {s0} {s1}')
    if B.edu_pick('Type', ['No Selection', 'Associate of Arts', 'Bachelor of Architecture', 'Bachelor of Arts'], dict(EDUS[1], degree_full='Bachelor of Arts')) != 'Bachelor of Arts':
        bad.append('edu_pick Type: Bachelor of Arts')
    if B.edu_pick('Subject', ['Accounting', 'Data Science', 'Economics'], EDUS[0]) != 'Data Science':
        bad.append('edu_pick Subject: Data Science')
    if S.label_from_options('* Please Select:', ['I Am Not a Protected Veteran']) != 'Please Select (I Am Not a Protected Veteran)':
        bad.append('label_from_options Acuity')
    if not S.chat_overlay({'tag': 'iframe', 'id': 'phenomChatbotIframe', 'cls': '', 'title': 'Phenom Career Bot', 'name': '', 'src': ''}):
        bad.append('chat_overlay Danfoss')
    if S.pw_limits('Password must not be longer than 18 characters.')[1] != 18 or S.pick_password('must not be longer than 18 characters', [('a', 'x' * 20), ('b', 'y' * 12)]) != ('b', 'y' * 12):
        bad.append('Newell password rule')
    if not S.privacy_link('Read and accept the data privacy agreement'):
        bad.append('Newell privacy agreement link')
    for b in bad:
        print('FAIL  fixed:', b[:300])
    print(f'fixed Acuity / Danfoss / Newell checks: {"ok" if not bad else str(len(bad)) + " failed"}')
    return len(bad)


def fixed_1105b():
    """The second 11-05 rerun: Newell's profile-visibility radios (no id, no label: text in aria-label + a loose <label>),
    Danfoss's one-page register-and-apply form (CV + fbclc_ fields + "Read and accept terms of use" + #fbqa_apply), Acuity's
    short school list ("Chicago, U of", "Illinois, U of/ChUrb", "Illinois, U of/Chgo")."""
    bad = []
    newell = 'Any Sevfengal recruiter worldwide (Selecting this option will enable us (for the duration indicated in the privacy policy below) to contact you about other opportunities globally)'
    if S.option_text({'label': '', 'aria': newell + '\n', 'after': newell, 'value': '1'}) != newell:
        bad.append('Newell option text')
    if S.radio_selector({'id': '', 'name': 'fbclc_searPref', 'value': '1', 'idx': 0, 'dup': False}) != ['input[type=radio][name="fbclc_searPref"][value="1"]', 0]:
        bad.append('Newell radio selector (no id)')
    if S.page_kind({'app': False, 'account': True, 'apply_btn': True, 'attach': True, 'upload': True, 'signin': False}) != 'register_apply':
        bad.append('Danfoss page kind')
    if S.page_kind({'account': True}) != 'register' or S.page_kind({'signin': True}) != 'sign_in':
        bad.append('Newell register / sign-in page kind')
    if not S.accept_link('Read and accept terms of use') or S.accept_link('Danfoss Job Portal Terms') or S.accept_link('Privacy policy'):
        bad.append('Danfoss terms-of-use link')
    if not S.privacy_accepted('Data privacy statement has been accepted.') or not S.privacy_accepted('', 'abc') or S.privacy_accepted('Accepted file types: DOCX, PDF Terms of Use: * Read and accept terms of use'):
        bad.append('Danfoss accepted check')
    A, B_ = ENT['A'], ENT['B']
    acuity = ['Chicago State U', 'Chicago, U of', 'Illinois, U of/Chgo', 'Illinois, U of/ChUrb', 'Loyola U Chicago', 'Other']
    if CE.pick_school(acuity, A) != ('Chicago, U of', 'match') or CE.pick_school(acuity, B_) != ('Illinois, U of/ChUrb', 'match'):
        bad.append(f'Acuity schools {CE.pick_school(acuity, A)} {CE.pick_school(acuity, B_)}')
    if CE.pick_school(['Illinois, U of/Chgo', 'Illinois State U', 'Other'], B_) != ('Other', 'other'):
        bad.append('Chgo is never UIUC (Other when nothing else fits)')
    if CE.pick_school(['Illinois, U of', 'Other'], B_) != (None, 'ambiguous'):
        bad.append('campus-less Illinois, U of → ask, never Other')
    if CE.school_query(A) != 'Chicago' or CE.school_query(B_) != 'Illinois':
        bad.append('school_query')
    for b in bad:
        print('FAIL  fixed_1105b:', b[:300])
    print(f'fixed Newell / Danfoss / Acuity (2nd run) checks: {"ok" if not bad else str(len(bad)) + " failed"}')
    return len(bad)


def main():
    fails = run_file('sf_register') + run_file('sf_page_1105') + fixed() + run_file('sf_register_apply') + run_file('sf_school_short') + fixed_1105b()
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
