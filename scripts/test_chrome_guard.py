"""runner/chrome_guard.enabled_others (JSA-227, Joey 2026-11-06 「只留 Claude，其余都停用」): DeepSeek cases from
scripts/test_cases/chrome_guard_spec.md (rule 13); disagreements judged in chrome_guard_verdicts.json. Prints `N/M ok`."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import chrome_guard  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'chrome_guard_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'chrome_guard_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
ok = bad = 0
for c in cases:
    g = [list(x) for x in chrome_guard.enabled_others(c['args']['settings'])]
    if g == [list(x) for x in c['expect']]:
        ok += 1
    elif c['name'] in verdicts:
        ok += 1; print('VERDICT', c['name'], '—', verdicts[c['name']])
    else:
        bad += 1; print('FAIL', c['name'], '| want', c['expect'], '| got', g)
# the live 11-06 profile shape: iCloud Passwords enabled → listed; after Joey's 「只留 Claude」 → clean
live = {'pejdijmoenmkgeppbflobdenhhabjlaj': {'manifest': {'name': 'iCloud 密码'}, 'location': 1, 'disable_reasons': []},
        'fcoeoabgfenejglbffodgkkbkcdhcgfn': {'manifest': {'name': 'Claude'}, 'location': 1, 'disable_reasons': []},
        'jkombkminlpobclgklikapogaamdfknh': {'manifest': {'name': 'Job agent — Lever fill'}, 'location': 4, 'disable_reasons': [],
                                             'path': '/Users/x/job-search-agent/skills/auto-apply/lever_fill/extension'}}
c1 = chrome_guard.enabled_others(live) == [('pejdijmoenmkgeppbflobdenhhabjlaj', 'iCloud 密码')]
live['pejdijmoenmkgeppbflobdenhhabjlaj']['disable_reasons'] = [1]
c2 = chrome_guard.enabled_others(live) == []
for n, cond in [('live: iCloud Passwords enabled is listed', c1), ('live: after disabling, clean', c2)]:
    ok += cond; bad += (not cond); print(('ok   ' if cond else 'FAIL ') + n)
print(f"{ok}/{len(cases) + 2} ok")
sys.exit(1 if bad else 0)
