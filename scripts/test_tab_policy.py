"""runner/tab_policy.keep_open (Joey 2026-11-05 「以后干跑结束也要把标签关掉」): DeepSeek cases from
scripts/test_cases/tab_policy_spec.md (rule 13); disagreements judged in tab_policy_verdicts.json. Prints `N/M ok`."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import tab_policy  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'tab_policy_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'tab_policy_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
ok = bad = 0
for c in cases:
    g = tab_policy.keep_open(c['args'].get('status'), c['args'].get('keep_tab', False))
    if g == c['expect']:
        ok += 1
    elif c['name'] in verdicts:
        ok += 1; print('VERDICT', c['name'], '—', verdicts[c['name']])
    else:
        bad += 1; print('FAIL', c['name'], c['args'], 'want', c['expect'], 'got', g)
print(f"{ok}/{len(cases)} ok")
sys.exit(1 if bad else 0)
