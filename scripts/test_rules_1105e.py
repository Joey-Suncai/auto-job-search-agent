"""Five answer-rule fixes of 2026-11-05 (JSA-205 saved answer over a rule that does not fit a text box, JSA-210 references
never get his own contact facts, JSA-175 OPT named only as an example, JSA-197 degree + major in one text box, JSA-198
combined major options). DeepSeek wrote the cases from scripts/test_cases/rules_1105e_spec.md (rule 13); disagreements
judged in rules_1105e_verdicts.json; rules_1105f_* = the OPT-as-example wording (Goldman Oracle 11-05). Runs answer_rules.js through rules_bridge.js (the runners' path) on the loaded
profile with the spec's facts laid over it: its qa table replaced by the spec's two saved answers, education and the
field-of-study order as the spec says. Prints `N/M ok`; exit 1 on an unjudged failure."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
RULES = os.path.abspath(os.path.join(RUN, '..', 'scripts', 'answer_rules.js'))
QA = [{'q': 'rank your preferred work locations (Huntersville)', 'match': '/rank your preferred work locations.*huntersville|huntersville.*rank your preferred work locations/i',
       'text': 'Huntersville, NC (USA)', 'source': 'spec'},
      {'q': 'What is your preferred shift?', 'text': 'Day shift', 'source': 'spec'}]
EDU = [{'school': 'University of Chicago', 'level': 'master', 'degree': 'M.S. Applied Data Science', 'degree_full': 'Master of Science',
        'major': 'Applied Data Science', 'start': '2026-09', 'end': '2027-12', 'current': True},
       {'school': 'University of Illinois Urbana-Champaign', 'level': 'bachelor', 'degree': 'B.A. Economics', 'degree_full': 'Bachelor of Arts',
        'major': 'Economics', 'start': '2024-08', 'end': '2026-05'}]
DISC = ['/^data science$/i', '/^applied data science$/i', '/^data analytics$/i', '/^computer science$/i', '/^information systems?$/i', '/^statistics$/i', '/^other$/i']
OWN = ['alex.doe@example.com', '555-010-2030', 'Alex']


def profile():
    f = subprocess.run(['node', '-e', "process.stdout.write(require(process.argv[1]).__file)", os.path.join(HERE, '..', 'config', 'profile.js')],
                       capture_output=True, text=True).stdout
    p = json.load(open(f, encoding='utf-8'))
    p['qa'] = QA; p['education'] = EDU
    p['answers']['discipline'] = dict(p['answers'].get('discipline') or {}, pick=DISC)
    p['answers'].pop('references', None)                           # spec: no references on file
    return p


def answers(cases):
    t = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8'); json.dump(profile(), t); t.close()
    qs = [{'key': str(i), 'label': c['args']['label'], 'type': c['args']['type'], 'options': c['args'].get('options') or []} for i, c in enumerate(cases)]
    try:
        r = subprocess.run(['node', os.path.join(RUN, 'rules_bridge.js'), RULES], input=json.dumps({'fields': qs, 'company': 'Acme'}),
                           capture_output=True, text=True, env=dict(os.environ, JSA_PROFILE=t.name))
    finally:
        os.unlink(t.name)
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    return json.loads(r.stdout)


def good(e, a):
    ok = a.get('status') == 'ok'
    if e.get('ask'):
        return not ok
    if e.get('not_ask'):
        return ok or a.get('rule') != 'references'                 # "never ask because of references"
    if 'not_value_contains' in e:
        v = str(a.get('value') or '') if ok else ''
        return all(x.lower() not in v.lower() for x in [e['not_value_contains']] + OWN)
    return ok and str(a.get('value')) == e['value']


def main():
    bad_all = 0
    for name in ('rules_1105e', 'rules_1105f'):                   # 1105f: OPT only as an example vs. "are you ON OPT" (Goldman Oracle 11-05)
        cases = json.load(open(os.path.join(HERE, 'test_cases', name + '_cases.json'), encoding='utf-8'))
        cases = cases['cases'] if isinstance(cases, dict) else cases
        vp = os.path.join(HERE, 'test_cases', name + '_verdicts.json')
        verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
        res = answers(cases)
        ok = bad = 0
        for i, c in enumerate(cases):
            a = res[str(i)]
            if good(c['expect'], a):
                ok += 1
            elif c['name'] in verdicts:
                ok += 1; print('VERDICT', name, c['name'], '—', verdicts[c['name']][:160])
            else:
                bad += 1; print('FAIL', name, c['name'], '| want', c['expect'], '| got', a.get('status'), repr(a.get('value')), a.get('rule'), a.get('why', ''), '|', c['args']['label'][:160], c['args'].get('options'))
        print(f"{name}: {ok}/{len(cases)} ok")
        bad_all += bad
    sys.exit(1 if bad_all else 0)


if __name__ == '__main__':
    main()
