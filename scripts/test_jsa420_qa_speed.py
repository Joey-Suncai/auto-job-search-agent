#!/usr/bin/env python3
"""JSA-420: DeepSeek-written cases (scripts/test_cases/jsa420_qa_speed_cases.json, from jsa420_qa_speed_spec.md) for
 - qa_add.ProfileLock: qa_add runs started at the same moment lose no answer (real processes, one temp profile);
 - qa_add.changed_numbers / batch_reason_n: the entries a batch's replay reason cites.
Plus: the lock excludes a second holder until released; --no-replay skips the replay; --batch survives a raising item; atomic write.
    python3 scripts/test_jsa420_qa_speed.py"""
import json, os, subprocess, sys, tempfile, threading, time
HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts')
sys.path.insert(0, SC)
import qa_add  # noqa: E402

BASE = os.path.join(HERE, '..', 'config', 'profile.example.json')
CASES = json.load(open(os.path.join(HERE, 'test_cases', 'jsa420_qa_speed_cases.json'), encoding='utf-8'))
bad = 0


def fail(msg):
    global bad
    bad += 1
    print('FAIL', msg)


def new_profile(td):
    prof = json.load(open(BASE, encoding='utf-8')); prof['qa'] = []
    p = os.path.join(td, 'profile.json')
    json.dump(prof, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return p


def concurrent(case):
    with tempfile.TemporaryDirectory() as td:
        p = new_profile(td)
        env = dict(os.environ, JSA_PROFILE=p)
        procs = [subprocess.Popen([sys.executable, os.path.join(SC, 'qa_add.py'), '--q', q, '--yes', '--source', 'test', '--no-commit', '--no-replay'],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env) for q in case['questions']]
        outs = [pr.communicate()[0] for pr in procs]
        got = json.load(open(p, encoding='utf-8'))['qa']                 # still valid JSON
        want = {qa_add.norm(q) for q in case['questions']}
        have = {qa_add.norm(e['q']) for e in got}
        if len(got) != case['expect']['saved'] or have != want:
            fail(f"{case['name']}: saved {len(got)} (want {case['expect']['saved']}); missing {want - have}\n" + '\n'.join(outs))


def numbers(case):
    got = qa_add.changed_numbers(case['before'], case['after'])
    txt = qa_add.batch_reason_n(case['expect_changed'])
    if got != case['expect_changed'] or txt != case['expect_text'] or qa_add.batch_reason_n(got) != case['expect_text']:
        fail(f"{case['name']}: changed {got} (want {case['expect_changed']}), text {txt!r} (want {case['expect_text']!r})")


for c in CASES:
    (concurrent if c['kind'] == 'concurrent' else numbers)(c)

# the lock really excludes: a second holder waits until the first releases
with tempfile.TemporaryDirectory() as td:
    p = new_profile(td)
    a = qa_add.ProfileLock(p).acquire()
    got = []
    def second():
        with qa_add.ProfileLock(p):
            got.append(time.time())
    th = threading.Thread(target=second); th.start(); time.sleep(0.4)
    if got:
        fail('second holder got the lock while the first held it')
    t0 = time.time(); a.release(); th.join(5)
    if not got or got[0] < t0 - 0.05:
        fail('second holder did not get the lock after release')
    # a lock file left by a dead process never blocks
    open(p + '.lock', 'a').close()
    with qa_add.ProfileLock(p):
        pass

# --no-replay: no replay line, "deferred" said; without it the replay is attempted (replay.py exists in the repo)
with tempfile.TemporaryDirectory() as td:
    p = new_profile(td)
    r = subprocess.run([sys.executable, os.path.join(SC, 'qa_add.py'), '--q', 'Typing speed?', '--text', '60', '--source', 'test', '--no-commit', '--no-replay'],
                       capture_output=True, text=True, env=dict(os.environ, JSA_PROFILE=p))
    if r.returncode or 'qa_add: replay' in r.stdout:
        fail('--no-replay still replayed or failed: ' + r.stdout + r.stderr)

# --batch: an item that raises (argparse SystemExit: yes + text) or has a value starting with "-" never stops the others;
# the exit code is 1, the saved ones stay, the profile is valid JSON and no lock / temp file is left behind
with tempfile.TemporaryDirectory() as td:
    p = new_profile(td)
    items = [{'q': 'Typing speed?', 'text': '-5', 'source': 'test'},
             {'q': 'Raises?', 'yes': True, 'text': 'x', 'source': 'test'},
             {'q': 'Forklift certificate?', 'yes': False, 'source': 'test'}]
    bf = os.path.join(td, 'b.json'); json.dump(items, open(bf, 'w'))
    r = subprocess.run([sys.executable, os.path.join(SC, 'qa_add.py'), '--batch', bf, '--no-commit'], capture_output=True, text=True, env=dict(os.environ, JSA_PROFILE=p))
    qa = json.load(open(p, encoding='utf-8'))['qa']
    if r.returncode != 1 or [e['q'] for e in qa] != ['Typing speed?', 'Forklift certificate?'] or qa[0].get('text') != '-5' or 'batch — 2 saved, 1 not saved' not in r.stdout:
        fail(f'--batch with a raising item: rc {r.returncode}, saved {[e["q"] for e in qa]}\n{r.stdout}{r.stderr}')
    left = [f for f in os.listdir(td) if '.tmp' in f]
    if left:
        fail(f'temp files left: {left}')

# live path (the profile IS the data home's): an item run by a batch (lock=…) never releases the batch's lock, a single run does
import shutil
with tempfile.TemporaryDirectory() as td:
    home = os.path.join(td, 'home'); os.makedirs(os.path.join(home, 'config')); os.makedirs(os.path.join(home, 'data'))
    prof = os.path.join(home, 'config', 'profile.json')
    shutil.copy(os.path.join(HERE, '..', 'config', 'fixtures', 'f1_student', 'profile.json'), prof)
    pj = json.load(open(prof, encoding='utf-8')); pj['qa'] = []; json.dump(pj, open(prof, 'w'), indent=1)
    os.environ['JSA_HOME'] = home
    try:
        lk = qa_add.ProfileLock(prof).acquire()
        rc = qa_add.main(qa_add.batch_argv({'q': 'Typing speed?', 'text': '60', 'source': 'test'}, prof), lock=lk)
        if rc != 0 or lk.fd is None:
            fail(f'a live item run with lock=… released the batch lock (rc {rc}, fd {lk.fd})')
        lk.release()
        rc = qa_add.main(['--profile', prof, '--q=Forklift certificate?', '--yes', '--source=test', '--no-commit', '--no-replay'])
        if rc != 0 or len(json.load(open(prof, encoding='utf-8'))['qa']) != 2:
            fail(f'live single run failed (rc {rc})')
        with qa_add.ProfileLock(prof):                                  # a single run left the lock free
            pass
    finally:
        del os.environ['JSA_HOME']

# the profile is replaced atomically: a reader polling during many writes never sees invalid JSON
with tempfile.TemporaryDirectory() as td:
    p = new_profile(td); stop = []; badread = []
    def reader():
        while not stop:
            try:
                json.load(open(p, encoding='utf-8'))
            except ValueError as ex:
                badread.append(str(ex)); return
    th = threading.Thread(target=reader); th.start()
    big = json.load(open(p, encoding='utf-8'))
    for i in range(300):
        big['qa'] = [{'q': f'q{k}', 'yes': True} for k in range(200)]
        qa_add.write_atomic(p, json.dumps(big, indent=1))
    stop.append(1); th.join(5)
    if badread:
        fail('reader saw a half-written profile: ' + badread[0])

print('test_jsa420_qa_speed:', 'FAIL' if bad else f'ok ({len(CASES)} cases + lock / no-replay / batch / atomic-write checks)')
sys.exit(1 if bad else 0)
