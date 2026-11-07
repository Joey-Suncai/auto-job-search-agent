#!/usr/bin/env python3
"""Offline tests for materials_gate.py (JSA-002 slices 1 + 2).  Run: python3 test/t_materials_gate.py

No network, no browser, no DeepSeek: temp folders and JSON only.
"""
import hashlib, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HERE)
sys.path.insert(0, RUNNER)
import materials_gate

fails = 0


def ok(name, cond, detail=''):
    global fails
    if cond:
        print('ok  ', name)
    else:
        fails += 1
        print('FAIL', name, '|', detail)


def folder():
    return tempfile.mkdtemp(prefix='mg_')


def write(f, name, data):
    p = os.path.join(f, name)
    if isinstance(data, (dict, list)):
        json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    else:
        open(p, 'wb').write(data if isinstance(data, bytes) else data.encode())
    return p


def sha(f, name):
    return hashlib.sha256(open(os.path.join(f, name), 'rb').read()).hexdigest()


quiet = lambda m: None

# 1. an empty folder: a manifest problem, not a crash
g = materials_gate.run_gate(folder(), quiet, 'warn')
ok('empty folder reports the missing manifest', (not g['ok']) and g['problems'] and
   'materials_manifest' in g['problems'][0], g)

# 2. resume required and present with a matching sha: clean
f = folder()
write(f, 'resume.pdf', b'%PDF-1.4 test')
write(f, 'requirements.json', {'requirements': [{'kind': 'resume', 'required': True, 'evidence': 'Resume/CV'}]})
write(f, 'materials_manifest.json', {'resume': {'file': 'resume.pdf', 'sha256': sha(f, 'resume.pdf'), 'check': 'pass'}})
g = materials_gate.run_gate(f, quiet, 'warn')
ok('complete folder is ok', g['ok'] and g['problems'] == [], g)

# 3. the file changed after the manifest was written
write(f, 'resume.pdf', b'%PDF-1.4 changed')
g = materials_gate.run_gate(f, quiet, 'warn')
ok('sha mismatch is named', any('sha mismatch' in p for p in g['problems']), g)

# 4. the form requires a cover letter the manifest never generated
f = folder()
write(f, 'resume.pdf', b'x')
write(f, 'materials_manifest.json', {'resume': {'file': 'resume.pdf', 'sha256': sha(f, 'resume.pdf'), 'check': 'pass'},
                                     'letter': {'decision': 'not_needed'}})
write(f, 'requirements.json', {'requirements': [{'kind': 'resume', 'required': True},
                                                {'kind': 'cover_letter', 'required': True, 'evidence': 'Cover Letter'}]})
g = materials_gate.run_gate(f, quiet, 'warn')
ok('required cover letter is a problem', any('cover_letter' in p for p in g['problems']), g)

# 5. a corrupt manifest is a readable problem, not an exception
f = folder()
write(f, 'materials_manifest.json', '{not json')
write(f, 'requirements.json', {'requirements': []})
g = materials_gate.run_gate(f, quiet, 'warn')
ok('corrupt manifest -> readable problem', (not g['ok']) and any('unavailable' in p for p in g['problems']), g)

# 6. mode off: no check at all
g = materials_gate.run_gate(folder(), quiet, 'off')
ok('off skips the check', g['ok'] and g['problems'] == [] and g['mode'] == 'off', g)

# 7. an unknown mode falls back to the default, block (never silently off)
g = materials_gate.run_gate(folder(), quiet, 'nonsense')
ok('unknown mode falls back to block', g['mode'] == 'block' and not g['ok'], g)
ok('default mode is block', materials_gate.DEFAULT_MODE == 'block')

# 8. mode block reports the same problems (the caller decides to stop)
g = materials_gate.run_gate(folder(), quiet, 'block')
ok('block reports problems', (not g['ok']) and g['mode'] == 'block', g)

# ---------------- slice 2: prepare, decide routing, Workday page check


def complete(f, reqs):
    write(f, 'resume.pdf', b'%PDF-1.4 r')
    write(f, 'materials_manifest.json', {'resume': {'file': 'resume.pdf', 'sha256': sha(f, 'resume.pdf'), 'check': 'pass'},
                                         'letter': {'decision': 'not_requested'}})
    if reqs is not None:
        write(f, 'requirements.json', {'requirements': reqs})


RESUME = {'kind': 'resume', 'required': True, 'evidence': 'Resume/CV (input_file)'}

# 9. Greenhouse: requirements.json is written offline from gh_api.json, then the gate passes
f = folder(); complete(f, None)
write(f, 'gh_api.json', {'questions': [{'label': 'Resume/CV', 'required': True, 'fields': [{'name': 'resume', 'type': 'input_file'}]}]})
g = materials_gate.run_gate(f, quiet, 'block')
ok('gh_api.json -> requirements.json written', os.path.exists(os.path.join(f, 'requirements.json')))
ok('gh_api.json -> gate ok', g['ok'], g)

# 10. Workday: a missing requirements.json is seeded with the resume
f = folder(); complete(f, None)
g = materials_gate.run_gate(f, quiet, 'block', ats='workday')
reqs = json.load(open(os.path.join(f, 'requirements.json')))['requirements']
ok('workday seed = resume only', [r['kind'] for r in reqs] == ['resume'] and g['ok'], g)

# 11. no gh_api, not Workday: requirements missing is a setup stop, not a decision
f = folder(); complete(f, None)
g = materials_gate.run_gate(f, quiet, 'block')
ok('missing requirements -> setup stop', (not g['ok']) and g['decisions'][0]['source'] == 'setup', g)

# 12. a required cover letter we did not write -> decide.py; no model -> pause_for_joey, logged
f = folder(); complete(f, [RESUME, {'kind': 'cover_letter', 'required': True, 'evidence': 'Cover Letter (input_file)'}])
g = materials_gate.run_gate(f, quiet, 'block')
ok('required letter -> blocked', not g['ok'], g)
ok('no model -> pause_for_joey', g['decisions'][0]['action'] == 'pause_for_joey', g)
ok('decision is logged in decisions.jsonl', os.path.exists(os.path.join(f, 'decisions.jsonl')))
ok('next step is written for the queue', g['next'] and 'Joey' in g['next'][0], g)

# 13. the model says generate_material -> still blocked, next step = run ds_materials.py
f = folder(); complete(f, [RESUME, {'kind': 'cover_letter', 'required': True, 'evidence': 'Cover Letter (input_file)'}])
g = materials_gate.run_gate(f, quiet, 'block', ask=lambda m, s: {'action': 'generate_material', 'reason': 'mock'})
ok('generate_material -> blocked with ds_materials next step', (not g['ok']) and 'ds_materials' in g['next'][0], g)

# 14. an optional transcript: skip_if_optional lets the run go on
f = folder(); complete(f, [RESUME, {'kind': 'transcript', 'required': True, 'evidence': 'Transcript (optional)'}])
os.remove(os.path.join(f, 'requirements.json'))
write(f, 'requirements.json', {'requirements': [RESUME, {'kind': 'other_file', 'required': True, 'evidence': 'x'}]})
g = materials_gate.run_gate(f, quiet, 'block', ask=lambda m, s: {'action': 'skip_if_optional', 'reason': 'mock'})
ok('skip_if_optional on a required field is refused -> blocked', not g['ok'], g)
f = folder(); complete(f, [RESUME])
items = [{'kind': 'transcript', 'required': False, 'type': 'missing', 'msg': 'transcript optional', 'evidence': 'x'}]
okk, dec, nxt = materials_gate.resolve(f, items, quiet, ask=lambda m, s: {'action': 'skip_if_optional', 'reason': 'mock'})
ok('skip_if_optional on an optional item -> go on', okk and dec[0]['action'] == 'skip_if_optional', dec)

# 15. the same event is decided once (a re-rendered page cannot trigger a second model call)
f = folder(); complete(f, [RESUME, {'kind': 'cover_letter', 'required': True, 'evidence': 'Cover Letter'}])
calls = []
ask = lambda m, s: calls.append(1) or {'action': 'pause_for_joey', 'reason': 'mock'}
materials_gate.run_gate(f, quiet, 'block', ask=ask); materials_gate.run_gate(f, quiet, 'block', ask=ask)
ok('same event decided once (cached)', len(calls) == 1, calls)


class Page:
    def __init__(self, slots): self.slots = slots
    def evaluate(self, js): return self.slots


# 16. Workday page check: a lone resume slot is not new
f = folder(); complete(f, [RESUME])
ok('page with the resume slot only -> nothing new',
   materials_gate.page_check(f, Page([{'label': 'Resume/CV Upload a file', 'id': 'file-upload-input-ref'}]), 'My Experience', quiet) is None)
ok('page with one generic file slot -> nothing new (runner uploads the resume there)',
   materials_gate.page_check(f, Page([{'label': 'Upload a file or drag and drop here', 'id': 'x'}]), 'My Experience', quiet) is None)

# 17. a cover-letter slot appears on a later page -> requirement added, decided, blocked
pg = materials_gate.page_check(f, Page([{'label': 'Resume', 'id': 'a'}, {'label': 'Cover Letter (required)', 'id': 'b'}]), 'Application Questions', quiet)
reqs = json.load(open(os.path.join(f, 'requirements.json')))['requirements']
ok('new cover letter slot -> added to requirements.json', any(r['kind'] == 'cover_letter' and r.get('page') == 'Application Questions' for r in reqs), reqs)
ok('new cover letter slot -> blocked via decide', pg is not None and not pg['ok'] and pg['decisions'], pg)
ok('same page again -> not added twice', materials_gate.page_check(
   f, Page([{'label': 'Resume', 'id': 'a'}, {'label': 'Cover Letter (required)', 'id': 'b'}]), 'Application Questions', quiet) is None)
ok('page check off -> None', materials_gate.page_check(f, Page([{'label': 'Transcript', 'id': 'c'}]), 'X', quiet, mode='off') is None)

print()
print('fails %d' % fails)
sys.exit(1 if fails else 0)
