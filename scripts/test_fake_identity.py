#!/usr/bin/env python3
"""JSA-403: scripts/fake_identity.py swaps a profile's identity onto the repo's fictional one. The "real" profile below is itself made up."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_identity as F

OTHER = {'name': {'first': 'Zed', 'last': 'Quill', 'preferred': 'Zee', 'full': 'Zed Quill', 'signature': 'Zed (Zee) Quill', 'file_prefix': 'Zed_Quill'},
         'contact': {'email': 'zed.quill@example.net', 'phone': '555-019-0199', 'linkedin': 'linkedin.com/in/zedq', 'website': 'github.com/zee-quill', 'secondary_email': 'zq@example.org'},
         'accounts': {'gmail': 'zed.quill@example.net'},
         'answers': {'address': {'text': '9 Birch St S'}, 'city_state_zip': {'text': 'Peoria, IL 61602'}, 'zip': {'text': '61602'},
                     'permanent_address': {'text': 'Flat 5, Harbour House, Porto 4000, Portugal'}, 'name_pronunciation': {'text': 'ZED KWIL (I go by Zee)'}}}
FK = F.fake()
bad = 0


def check(name, ok):
    global bad
    if not ok: bad += 1
    print(('PASS ' if ok else 'FAIL ') + name)


R = F.swap_rules(OTHER)
sw = lambda t: F.apply(t, R)
check('full name', sw('Name: Zed Quill.') == 'Name: ' + FK['full'] + '.')
check('signature before the parts', sw('Zed (Zee) Quill') == FK['signature'])
check('file prefix', sw('Zed_Quill_Resume_X.pdf') == FK['file_prefix'] + '_Resume_X.pdf')
check('e-mail, case-insensitive', sw('ZED.QUILL@example.net and zq@example.org') == FK['email'] + ' and ' + FK['secondary_email'])
check('phone keeps its format', sw('555-019-0199 | (555) 019-0199 | +1 555 019 0199 | 5550190199') == ' | '.join(
    [FK['phone'], '(555) 010-2030', '+1 555 010 2030', '5550102030']))
check('a longer digit run is not a phone', sw('id 15550190199123') == 'id 15550190199123')
check('street, long form and city/zip', sw('9 Birch St S; 9 Birch Street South; Peoria, IL 61602; 61602') == f"{FK['street']}; {FK['street_long']}; {FK['city_state_zip']}; {FK['zip']}")
check('permanent address and pronunciation', sw('Flat 5, Harbour House, Porto 4000, Portugal | ZED KWIL (I go by Zee)') == FK['permanent_address'] + ' | ' + FK['pronunciation'] + f" (I go by {FK['preferred']})")
check('handles', sw('linkedin.com/in/zedq github.com/zee-quill') == FK['linkedin'] + ' ' + FK['website'])
check('preferred full name and quoted last name', sw('Zee Quill / "Quill" / Zed / Zee') == f"{FK['preferred']} {FK['last']} / \"{FK['last']}\" / {FK['first']} / {FK['preferred']}")
check('unrelated text stays', sw('Chicago, IL; a quill pen') == 'Chicago, IL; a quill pen')
check('the fictional set has no real-looking value', FK['email'].endswith('@example.com') and FK['phone'].startswith('555-010-'))

with tempfile.TemporaryDirectory() as d:     # swap_home: config/ and facts/ of a clone
    os.makedirs(d + '/config'); os.makedirs(d + '/facts'); os.makedirs(d + '/data')
    json.dump(OTHER, open(d + '/config/profile.json', 'w'))
    open(d + '/facts/x.md', 'w').write('mail zed.quill@example.net')
    open(d + '/data/keep.md', 'w').write('mail zed.quill@example.net')
    os.makedirs(d + '/resume'); open(d + '/resume/Zed_Quill_Resume_X.docx', 'w').write('x')
    n = F.swap_home(d)
    check('generated files carry the fictional file prefix', os.path.exists(d + '/resume/' + FK['file_prefix'] + '_Resume_X.docx'))
    check('swap_home rewrites config/ and facts/ only', n == 3 and open(d + '/facts/x.md').read() == 'mail ' + FK['email']
          and 'zed.quill' in open(d + '/data/keep.md').read() and FK['full'] in open(d + '/config/profile.json').read())

print('FAILED' if bad else 'ALL PASS')
sys.exit(1 if bad else 0)
