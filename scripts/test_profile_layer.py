#!/usr/bin/env python3
"""Harness for the profile layer (rule 13, JSA-077): config/jsa_profile.py (resolve / data_file / get) and answer_rules.js
answering from a profile. DeepSeek cases in test_cases/profile_layer_cases.json, verdicts in profile_layer_verdicts.json."""
import importlib.util, json, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD = os.path.join(ROOT, 'config', 'jsa_profile.py')
RULES = os.path.join(ROOT, 'skills', 'auto-apply', 'scripts', 'answer_rules.js')
cases = json.load(open(os.path.join(HERE, 'test_cases', 'profile_layer_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'profile_layer_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}


def fresh(d):
    shutil.copy(MOD, os.path.join(d, 'jsa_profile.py'))
    spec = importlib.util.spec_from_file_location('jp_%d' % id(d), os.path.join(d, 'jsa_profile.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def run(c):
    d = tempfile.mkdtemp(); env0 = dict(os.environ)
    try:
        os.environ.pop('JSA_PROFILE', None)
        if c['fn'] == 'resolve':
            if c.get('user'): open(os.path.join(d, 'profile.json'), 'w').write('{"who": "user"}')
            if c.get('example'): open(os.path.join(d, 'profile.example.json'), 'w').write('{"who": "example"}')
            if c.get('env'):
                p = os.path.join(d, 'envdir', c['env']); os.makedirs(os.path.dirname(p))
                if c.get('env_exists'): open(p, 'w').write('{"who": "env"}')
                os.environ['JSA_PROFILE'] = p
            try:
                return fresh(d).load()['who']
            except FileNotFoundError:
                return 'error'
        if c['fn'] == 'data_file':
            n = c['name']; stem, ext = os.path.splitext(n)
            if c.get('user'): open(os.path.join(d, n), 'w').write('x')
            if c.get('env_value'): os.environ['JSA_TEST_ENV'] = c['env_value']
            got = fresh(d).data_file(n, 'JSA_TEST_ENV' if c.get('env_value') else None)
            os.environ.pop('JSA_TEST_ENV', None)
            return 'env' if c.get('env_value') and got == c['env_value'] else 'user' if got == os.path.join(d, n) else \
                'example' if got == os.path.join(d, stem + '.example' + ext) else got
        if c['fn'] == 'get':
            json.dump(c['profile'], open(os.path.join(d, 'profile.json'), 'w'))
            m = fresh(d)
            return m.get(c['key'], c['default']) if 'default' in c else m.get(c['key'])
        prof = {'answers': c['answers'], 'work_auth': {'restricted': c.get('restricted', False)}}
        pp = os.path.join(d, 'p.json'); json.dump(prof, open(pp, 'w'))
        js = ("const {answerFor}=require(%s);const a=answerFor({l:%s,o:%s});"
              "process.stdout.write(JSON.stringify({s:a.status,v:a.value===undefined?null:a.value}))") % (
                  json.dumps(RULES), json.dumps(c['label']), json.dumps(c.get('options') or []))
        r = subprocess.run(['node', '-e', js], capture_output=True, text=True, env=dict(os.environ, JSA_PROFILE=pp))
        if r.returncode: return 'node error: ' + r.stderr[-200:]
        o = json.loads(r.stdout); st = 'ok' if o['s'] == 'ok' else 'unknown' if o['s'] == 'unknown' else o['s']
        return [st, o['v'] if st == 'ok' else None]
    finally:
        os.environ.clear(); os.environ.update(env0); shutil.rmtree(d, ignore_errors=True)


bad = 0
for c in cases:
    got = run(c)
    exp = [c['expect_status'], c.get('expect_value')] if c['fn'] == 'answer' else c['expect']
    if got != exp and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['fn'], c['name'], '| got', got, '| expect', exp)
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
