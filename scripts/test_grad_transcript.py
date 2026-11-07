"""Graduate-transcript slots (JSA-216, Joey 2026-11-05 「研究生成绩单目前还没有，那这种问题的岗位就先跳过去」) and the secondary
e-mail rule (contact.secondary_email, Joey 2026-11-05). DeepSeek wrote the cases from
scripts/test_cases/grad_transcript_spec.md (rule 13); disagreements judged in grad_transcript_verdicts.json. Prints `N/M ok`."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts'))
import materials_probe  # noqa: E402

RULES = os.path.join(HERE, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js')
JS = ("const {answerFor}=require(process.argv[1]); const P=require(process.argv[2]); const q=JSON.parse(require('fs').readFileSync(0,'utf8'));"
      "process.stdout.write(JSON.stringify(q.map(l=>{const a=answerFor({l,t:'text',o:[]},{company:'Acme'});"
      "const c=P.contact||{}; return a.value===c.secondary_email?'secondary':a.value===c.email?'main':String(a.value)})))")


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'grad_transcript_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'grad_transcript_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    em = [c for c in cases if c['fn'] == 'email']
    prof = os.path.join(HERE, '..', 'config', 'profile.js')
    r = subprocess.run(['node', '-e', JS, RULES, prof], input=json.dumps([c['args']['label'] for c in em]), capture_output=True, text=True)
    got_em = dict(zip([c['name'] for c in em], json.loads(r.stdout or '[]')))
    ok = bad = 0
    for c in cases:
        g = materials_probe.slot_kind('question_1', c['args']['label']) if c['fn'] == 'slot_kind' else got_em.get(c['name'])
        if g == c['expect']:
            ok += 1
        elif c['name'] in verdicts:
            ok += 1; print('VERDICT', c['name'], '—', verdicts[c['name']])
        else:
            bad += 1; print('FAIL', c['name'], '| want', c['expect'], '| got', g, '|', c['args']['label'])
    print(f"{ok}/{len(cases)} ok")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
