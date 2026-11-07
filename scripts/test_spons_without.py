"""'Work WITHOUT sponsorship' questions (JSA-112, 2026-11-05): the profile's sponsorship answer flipped — the future
answer when the question covers the future, the now answer (internship on CPT) otherwise. DeepSeek wrote the cases from
scripts/test_cases/spons_without_spec.md (rule 13); disagreements are judged in spons_without_verdicts.json.
Runs the rules on the live profile with its qa table removed. Prints `N/M ok`; exit 1 on an unjudged failure."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_sr_1105 as T  # noqa: E402  (answers(): rules_bridge on the profile without qa)


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'spons_without_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'spons_without_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    res = T.answers([dict(c, fn='answer') for c in cases]); ans = [res[str(i)] for i in range(len(cases))]
    ok = bad = 0
    for c, a in zip(cases, ans):
        good = a.get('status') == 'ok' and str(a.get('value')) == c['expect']['value']
        if good:
            ok += 1
        elif c['name'] in verdicts:
            ok += 1; print('VERDICT', c['name'], '—', verdicts[c['name']])
        else:
            bad += 1; print('FAIL', c['name'], '| want', c['expect']['value'], '| got', a.get('value'), a.get('rule'), a.get('status'), '|', c['args']['label'])
    print(f"{ok}/{len(cases)} ok")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
