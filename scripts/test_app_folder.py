"""Harness for skills/auto-apply/runner/app_folder.py (JSA-319, rule 13): DeepSeek cases in
test_cases/app_folder_cases.json (written from the spec, not the code). Each disagreement is judged by Claude, with the
verdicts in test_cases/app_folder_verdicts.json. There are also two replays of the 11-11 misses: Harwynpell (approved ML
answer in an unsubmitted folder, a new batch on a later date) and Morpellkel (a submitted folder, a re-submit; the
Application Date answer is not carried)."""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import app_folder as AF  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'app_folder_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'app_folder_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}


def build(existing):
    root = tempfile.mkdtemp()
    subm = set()
    for f in existing:
        p = os.path.join(root, f['name'])
        os.makedirs(p, exist_ok=True)
        if f.get('id_file'):
            json.dump({'id': f.get('id')}, open(os.path.join(p, f['id_file']), 'w'))
        for fn, body in (f.get('files') or {}).items():
            if fn == 'answers.json':
                json.dump(body, open(os.path.join(p, fn), 'w'))
            else:
                open(os.path.join(p, fn), 'w').write(body)
        if f.get('submitted'):
            subm.add(f['name'])
    return root, (lambda folder: os.path.basename(folder) in subm)


def run(c):
    root, submitted = build(c.get('existing') or [])
    before = {n: set(os.listdir(os.path.join(root, n))) for n in os.listdir(root)}
    k = c['call']
    got = AF.for_job(k['job_id'], k['date'], k['company'], k['title'], root, submitted, log=lambda *_: None)
    name = os.path.basename(got)
    carried = sorted(f for f in AF.CARRY if os.path.exists(os.path.join(got, f)) and f not in before.get(name, set()))
    aj = os.path.join(got, 'answers.json')
    out = {'folder': name, 'carried': carried, 'answers_json': json.load(open(aj)) if os.path.exists(aj) else None}
    shutil.rmtree(root)
    return out


bad = 0
for c in cases:
    got = run(c)
    exp = {'folder': c['expect']['folder'], 'carried': sorted(c['expect'].get('carried') or []), 'answers_json': c['expect'].get('answers_json')}
    if got != exp:
        if c['name'] in verdicts:
            print(f"judged  {c['name']} — {verdicts[c['name']][:90]}")
        else:
            bad += 1
            print(f"DISAGREE {c['name']} | got {json.dumps(got)} | expect {json.dumps(exp)}")

# replays of 2026-11-11
checks = []
r = run({'existing': [{'name': '2026-11-10_Harwynpell_Machine_Learning_Intern_Harwynpell_Data_Serv', 'id_file': 'job.json', 'id': 'J16060',
                       'submitted': False, 'files': {'open_answers.md': '## 162:_txtArea — What interests you most about Machine Learning?\nTesting …\n'}}],
         'call': {'job_id': 'J16060', 'date': '2026-11-11', 'company': 'Harwynpell', 'title': 'Machine Learning Intern (Harwynpell Data Services)'}})
checks.append(('Harwynpell: a new batch reuses the unsubmitted 11-10 folder (approved ML answer kept)', r['folder'].startswith('2026-11-10_Harwynpell')))
r = run({'existing': [{'name': '2026-11-11_Harwynpell_Machine_Learning_Intern_Harwynpell_Data_Serv', 'id_file': 'job.json', 'id': 'J16060', 'submitted': True},
                      {'name': '2026-11-10_Harwynpell_Machine_Learning_Intern_Harwynpell_Data_Serv', 'id_file': 'job.json', 'id': 'J16060', 'submitted': False}],
         'call': {'job_id': 'J16060', 'date': '2026-11-12', 'company': 'Harwynpell', 'title': 'Machine Learning Intern (Harwynpell Data Services)'}})
checks.append(('Harwynpell after the submit: the stale 11-10 dry-run folder is never reused', r['folder'].startswith('2026-11-12_Harwynpell')))
r = run({'existing': [{'name': '2026-11-10_Morpellkel_Data_Operations_Intern', 'id_file': 'job.json', 'id': 'J16166', 'submitted': True,
                       'files': {'answers.json': {'^Application\\ Date$': '11/10/2026', 'Why us?': 'Because …'}}}],
         'call': {'job_id': 'J16166', 'date': '2026-11-11', 'company': 'Morpellkel', 'title': 'Data Operations Intern'}})
checks.append(('Morpellkel: re-submit gets a new folder, the old date answer is not carried',
               r['folder'] == '2026-11-11_Morpellkel_Data_Operations_Intern' and r['answers_json'] == {'Why us?': 'Because …'}))
for n, ok in checks:
    print(('PASS  ' if ok else 'FAIL  ') + n)
bad += sum(1 for _, ok in checks if not ok)
print(f'{len(cases)} cases + {len(checks)} replays · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
