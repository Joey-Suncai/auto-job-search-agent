#!/usr/bin/env python3
"""JSA-420: qa_add --batch saves many answers in one go (one replay + one commit instead of one per answer — the first Ashby batch
waited ~30 s per answer for the replay). Offline: a temp profile (so no replay / commit runs), real qa_add.py as a subprocess.
    python3 scripts/test_jsa420_qa_batch.py"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
SC = os.path.join(ROOT, 'skills', 'auto-apply', 'scripts')
sys.path.insert(0, SC)
import qa_add as QA  # noqa: E402
bad = 0


def case(name, got, want):
    global bad
    if got != want:
        bad += 1; print(f'DISAGREE {name}: got {got!r}, want {want!r}')


def val(av, flag):
    return next(x.split('=', 1)[1] for x in av if x.startswith(flag + '='))


# batch_argv: pure (--flag=value: a value may start with "-")
av = QA.batch_argv({'q': 'Git?', 'yes': True, 'source': 'Joey 2026-11-17'}, '/p.json')
case('argv yes', ('--yes' in av, '--no-replay' in av, '--no-commit' in av, val(av, '--q')), (True, True, True, 'Git?'))
ab = QA.batch_argv({'q': 'Where?', 'pick': ['/chicago/i'], 'box': 'Chicago, IL'}, 'p')
case('argv pick+box', (val(ab, '--box'), val(ab, '--pick')), ('Chicago, IL', '/chicago/i'))
case('argv no', '--no' in QA.batch_argv({'q': 'x', 'yes': False}, 'p'), True)
case('argv extend', sum(x.startswith('--extend-entry=') for x in QA.batch_argv({'extend_entry': 3, 'q': 'w', 'box': '0'}, 'p')), 1)
try:
    QA.batch_argv({'yes': True}, 'p'); case('item without q', 'no error', 'ValueError')
except ValueError:
    pass

# end to end on a temp profile: 3 good items + 1 that cannot be saved (empty answer) → 3 saved, exit 1, ONE summary
BASE = json.load(open(os.path.join(ROOT, 'config', 'profile.example.json'), encoding='utf-8'))
td = tempfile.mkdtemp(prefix='jsa420_')
prof = os.path.join(td, 'profile.json')
json.dump(dict(BASE, qa=[]), open(prof, 'w'), indent=1)
items = [
    {'q': 'Did you attend a fall career fair this year?', 'yes': False, 'source': 'Joey 2026-11-17 (batch)'},
    {'q': 'Are you comfortable using Git/GitHub for version control?', 'yes': True, 'source': 'Joey 2026-11-17 (batch)'},
    {'q': 'Where do you want to work, in what city?', 'pick': ['/chicago/i'], 'box': 'Chicago, Illinois, United States', 'source': 'Joey 2026-11-17 (batch)'},
    {'q': 'Broken item', 'source': 'x'},
]
bf = os.path.join(td, 'batch.json'); json.dump(items, open(bf, 'w'))
r = subprocess.run([sys.executable, os.path.join(SC, 'qa_add.py'), '--profile', prof, '--batch', bf], capture_output=True, text=True, timeout=120)
case('exit 1 when one item fails', r.returncode, 1)
case('summary', 'batch — 3 saved, 1 not saved' in r.stdout, True)
qa = json.load(open(prof))['qa']
case('three entries saved', len(qa), 3)
case('box kept', qa[2].get('box'), 'Chicago, Illinois, United States')
json.dump(items[:3], open(bf, 'w'))
json.dump(dict(BASE, qa=[]), open(prof, 'w'), indent=1)
r = subprocess.run([sys.executable, os.path.join(SC, 'qa_add.py'), '--profile', prof, '--batch', bf], capture_output=True, text=True, timeout=120)
case('all good → exit 0', r.returncode, 0)
r = subprocess.run([sys.executable, os.path.join(SC, 'qa_add.py'), '--profile', prof, '--batch', os.path.join(td, 'nope.json')], capture_output=True, text=True)
case('missing file → exit 1', r.returncode, 1)
print('JSA-420 qa batch:', 'ALL PASS' if not bad else f'{bad} disagreements')
sys.exit(1 if bad else 0)
