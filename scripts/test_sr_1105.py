#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sr_1105_cases.json, spec sr_1105_spec.md) against
run_smartrecruiters.apply_url (form URL with the company identifier in the API's case — SEVWYNVER / Winsupply1 2026-11-05) and
answer_rules.js through rules_bridge.js (DOB-for-minors box left empty, certify radio, work WITHOUT sponsorship, "if not
type N/A"). The rules run on the live profile without its qa table (a saved answer must not hide a rule). Verdicts in
sr_1105_verdicts.json.
    python3 scripts/test_sr_1105.py"""
import json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUN)
import run_smartrecruiters as R  # noqa: E402


def loose_parse(url):
    """The cases use short made-up ids / uuids ("98765", "uuid-2") that parse_posting rightly refuses (≥ 6 digits, a
    36-character uuid — its own cases are smartrecruiters_cases.json); this check is about apply_url, so such a URL is
    split the same way without the length checks."""
    m = re.match(r'^https?://jobs\.smartrecruiters\.com/oneclick-ui/company/([\w.-]+)/publication/([\w-]+)', url, re.I)
    if m:
        return {'company': m.group(1), 'uuid': m.group(2).lower()}
    m = re.match(r'^https?://jobs\.smartrecruiters\.com/([\w.-]+)/(\d+)', url, re.I)
    return {'company': m.group(1), 'id': m.group(2)} if m else None


def form_url(a):
    p = R.parse_posting(a['store_url']) or loose_parse(a['store_url'])
    if not p:
        return None
    api = a['api']
    def fetch(_u):
        if api == 'ERROR':
            raise OSError('lookup failed')
        return api
    try:
        return R.apply_url(p, fetch)
    except Exception:
        return 'RAISES'


def profile_without_qa():
    f = subprocess.run(['node', '-e', "process.stdout.write(require(process.argv[1]).__file)", os.path.abspath(os.path.join(HERE, '..', 'config', 'profile.js'))],
                       capture_output=True, text=True).stdout
    p = json.load(open(f, encoding='utf-8')); p.pop('qa', None)
    t = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8'); json.dump(p, t); t.close()
    return t.name


def answers(cases):
    qs = [{'key': str(i), 'label': c['args']['label'], 'type': c['args']['type'], 'options': c['args'].get('options') or []}
          for i, c in enumerate(cases) if c['fn'] == 'answer']
    prof = profile_without_qa()
    try:
        r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))],
                           input=json.dumps(qs), capture_output=True, text=True, env=dict(os.environ, JSA_PROFILE=prof))
    finally:
        os.unlink(prof)
    return json.loads(r.stdout)


def check(c, a):
    e = c['expect']
    if 'leave' in e:
        return a.get('status') == 'ok' and bool(a.get('leave')) and not a.get('value')
    if 'not_rule' in e:
        return a.get('rule') != e['not_rule']
    return a.get('status') == 'ok' and not a.get('leave') and str(a.get('value')) == e['value']


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sr_1105_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sr_1105_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    ans = answers(cases)
    bad = 0
    for i, c in enumerate(cases):
        if c['fn'] == 'form_url':
            got = form_url(c['args']); ok = got == c['expect']
        else:
            got = ans.get(str(i)) or {}; ok = check(c, got)
            got = {k: got.get(k) for k in ('status', 'rule', 'value', 'leave', 'why') if got.get(k) not in (None, '')}
        if ok:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', json.dumps(got)[:300], 'want', json.dumps(c['expect'])[:300])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
