#!/usr/bin/env python3
"""Harness (rule 13) for the Greenhouse extra file slots and the after-submit outcome (JSA-209, Viking 10-31):
materials_probe.slot_kind, run.file_slots / missing_file_slots / after_submit, against the DeepSeek cases written from
test_cases/gh_file_slots_spec.md. Every disagreement needs a verdict in test_cases/gh_file_slots_verdicts.json.
Also: the Viking gh_api fixture (sanitized from the saved file) → requirements.json classifies the supplement slot
as a required extra other_file, and prep_batch.joey_files lists it."""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUNNER); sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts'))
import materials_probe, run as R, prep_batch  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'gh_file_slots_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'gh_file_slots_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}


def folder_with(files, answers):
    d = tempfile.mkdtemp(prefix='ghslots_')
    for f in files or []:
        p = os.path.join(d, f)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(b'%PDF-1.4 fixture')
    if answers is not None:
        json.dump(answers, open(os.path.join(d, 'answers.json'), 'w'))
    return d


def got_of(c):
    fn = c['fn']
    if fn == 'slot_kind':
        return materials_probe.slot_kind(c['slot_name'], c['label'])
    if fn == 'after_submit':
        return R.after_submit(c['confirmed'], c['code_page'], c['before'], c['after'])
    d = folder_with(c.get('files'), c.get('answers'))
    try:
        if fn == 'file_slots':
            return [{k: s[k] for k in ('key', 'kind', 'required', 'file')} for s in R.file_slots(c['plan'], d, 'Transcript.pdf')]
        if fn == 'missing_file_slots':
            return [s['key'] for s in R.missing_file_slots(c['plan'], d, 'Transcript.pdf')]
    finally:
        shutil.rmtree(d, ignore_errors=True)
    raise ValueError(fn)


def norm(fn, x):
    if fn == 'file_slots':
        return [{k: s.get(k) for k in ('key', 'kind', 'required', 'file')} for s in x]
    return x


bad = 0
for c in cases:
    got = got_of(c)
    if norm(c['fn'], got) != norm(c['fn'], c['expect']) and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])

# the Viking posting (sanitized: only the two file questions of the saved gh_api.json)
VIKING = {'questions': [
    {'label': 'Resume/CV', 'required': True, 'fields': [{'name': 'resume', 'type': 'input_file'}, {'name': 'resume_text', 'type': 'textarea'}]},
    {'label': 'Cover Letter', 'required': False, 'fields': [{'name': 'cover_letter', 'type': 'input_file'}]},
    {'label': 'This role requires a brief research supplement describing a relevant project you recently completed. Please '
              'upload your resume and brief research supplement — as a single PDF. Merge both documents into one file, with '
              'your resume first and the supplement second.', 'required': True,
     'fields': [{'name': 'question_20063878004', 'type': 'input_file'}]}]}
d = tempfile.mkdtemp(prefix='ghviking_')
try:
    json.dump(VIKING, open(os.path.join(d, 'gh_api.json'), 'w'))
    _, data = materials_probe.probe(d)
    byname = {r['selector']: r for r in data['requirements']}
    checks = [
        (byname['resume']['kind'] == 'resume' and byname['resume']['slot'] == 'standard', 'resume = standard resume slot'),
        (byname['cover_letter']['kind'] == 'cover_letter' and byname['cover_letter']['required'] is False, 'cover letter optional'),
        (byname['question_20063878004']['kind'] == 'other_file' and byname['question_20063878004']['slot'] == 'extra'
         and byname['question_20063878004']['required'] is True, 'supplement = required extra other_file'),
        (data.get('version') == 2, 'requirements version 2'),
        ([f['key'] for f in prep_batch.joey_files(data['requirements'], d)] == ['question_20063878004'], 'prep lists the slot for Joey'),
    ]
    open(os.path.join(d, 'Viking_resume_and_supplement.pdf'), 'wb').write(b'%PDF-1.4')
    json.dump({'question_20063878004': 'Viking_resume_and_supplement.pdf'}, open(os.path.join(d, 'answers.json'), 'w'))
    checks.append((prep_batch.joey_files(data['requirements'], d) == [], 'a file named in answers.json satisfies the slot'))
    for ok, what in checks:
        if not ok:
            bad += 1; print('FAIL viking:', what)
finally:
    shutil.rmtree(d, ignore_errors=True)

print(f'{len(cases)} cases + Viking fixture · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
