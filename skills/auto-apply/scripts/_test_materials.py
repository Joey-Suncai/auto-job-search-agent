#!/usr/bin/env python3
"""Offline tests for materials_probe.py + materials_check.py. Run: python3 _test_materials.py -> must print fails 0."""
import hashlib, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import materials_probe as P
import materials_check as M

fails = []


def check(name, cond, detail=''):
    if not cond:
        fails.append('%s: %s' % (name, detail))


def folder():
    return tempfile.mkdtemp()


def write(path, data):
    with open(path, 'wb') as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def gh_api(d):
    q = [
        {'label': 'First Name', 'required': True, 'fields': [{'name': 'first_name', 'type': 'input_text'}]},
        {'label': 'Resume/CV', 'required': True, 'fields': [{'name': 'resume', 'type': 'input_file'}]},
        {'label': 'Cover Letter', 'required': True, 'fields': [{'name': 'cover_letter', 'type': 'input_file'}]},
        {'label': 'Why do you want to work here?', 'required': True, 'fields': [{'name': 'q_why', 'type': 'textarea'}]},
        {'label': 'Phone', 'required': True, 'fields': [{'name': 'phone', 'type': 'input_text'}]},
    ]
    json.dump({'questions': q}, open(os.path.join(d, 'gh_api.json'), 'w'))


# 1. the probe reads the form, not the platform's reputation
f = folder(); gh_api(f)
out, data = P.probe(f)
kinds = {r['kind'] for r in data['requirements']}
check('resume detected', 'resume' in kinds, str(kinds))
check('cover letter detected', 'cover_letter' in kinds, str(kinds))
check('essay detected', 'essay' in kinds, str(kinds))
check('plain text field ignored', 'phone' not in kinds and 'unknown' not in kinds, str(kinds))
check('evidence recorded', all(r.get('evidence') for r in data['requirements']), str(data['requirements']))
check('requirements.json written', os.path.exists(out))

# 2. a complete, consistent set passes the gate
f = folder(); gh_api(f); P.probe(f)
write(os.path.join(f, 'resume.pdf'), b'%PDF-1.4 resume')
write(os.path.join(f, 'letter.pdf'), b'%PDF-1.4 letter')
write(os.path.join(f, 'open_answers.md'), 'A long enough answer to the written question, verified against the story bank.')
json.dump({'resume': {'file': 'resume.pdf', 'sha256': sha(os.path.join(f, 'resume.pdf')), 'check': 'pass'},
           'letter': {'decision': 'generated', 'file': 'letter.pdf', 'sha256': sha(os.path.join(f, 'letter.pdf')), 'fact_check': 'pass'}},
          open(os.path.join(f, 'materials_manifest.json'), 'w'))
probs = M.check(f)
check('consistent set passes', probs == [], str(probs))

# 3. a resume regenerated after the manifest is caught
write(os.path.join(f, 'resume.pdf'), b'%PDF-1.4 resume v2')
probs = M.check(f)
check('sha mismatch caught', any('sha mismatch' in p for p in probs), str(probs))
write(os.path.join(f, 'resume.pdf'), b'%PDF-1.4 resume')
check('restored file passes again', M.check(f) == [], str(M.check(f)))

# 4. a required cover letter that was never generated is caught
man = json.load(open(os.path.join(f, 'materials_manifest.json')))
man['letter'] = {'decision': 'not_requested'}
json.dump(man, open(os.path.join(f, 'materials_manifest.json'), 'w'))
probs = M.check(f)
check('missing required letter caught', any('cover_letter' in p for p in probs), str(probs))

# 5. a form that does not ask for a letter must not require one
f2 = folder()
json.dump({'questions': [{'label': 'Resume/CV', 'required': True, 'fields': [{'name': 'resume', 'type': 'input_file'}]}]},
          open(os.path.join(f2, 'gh_api.json'), 'w'))
P.probe(f2)
write(os.path.join(f2, 'resume.pdf'), b'%PDF-1.4 resume')
json.dump({'resume': {'file': 'resume.pdf', 'sha256': sha(os.path.join(f2, 'resume.pdf')), 'check': 'pass'},
           'letter': {'decision': 'not_accepted_by_form'}},
          open(os.path.join(f2, 'materials_manifest.json'), 'w'))
check('letter not required when there is no slot', M.check(f2) == [], str(M.check(f2)))

# 6. missing manifest / requirements are reported, never guessed
f3 = folder()
check('no manifest reported', M.check(f3) and 'materials_manifest.json missing' in M.check(f3)[0], str(M.check(f3)))
write(os.path.join(f3, 'materials_manifest.json'), '{}')
check('no requirements reported', any('requirements.json missing' in p for p in M.check(f3)), str(M.check(f3)))

print('fails', len(fails))
for x in fails:
    print(' FAIL', x)
sys.exit(1 if fails else 0)
