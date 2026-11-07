"""SuccessFactors 2026-11-05 third round (JSA-092 types Z / AA / AB): source lists naming sites ("Job Board - Indeed"),
the "Data Privacy Consent Statement" link, zero-width characters in option text. DeepSeek wrote the cases from
scripts/test_cases/sf_1105c_spec.md (rule 13); disagreements judged in sf_1105c_verdicts.json. Prints `N/M ok`."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUN)
import run_successfactors as R  # noqa: E402
import job_board, canon  # noqa: E402

DEFAULTS = ['LinkedIn', 'Indeed']


def got(c):
    a = c['args']
    if c['fn'] == 'privacy_link':
        return R.privacy_link(a['text'])
    if c['fn'] == 'site_board':
        return any(R.SITE_BOARD.search(o) for o in a['options'])
    if c['fn'] == 'board_pick':
        return job_board.board_pick(a['options'], a.get('source'), a.get('url'), DEFAULTS)
    if c['fn'] == 'norm':
        return canon.norm(a['text'])


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_1105c_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_1105c_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    ok = bad = 0
    for c in cases:
        g = got(c)
        if g == c['expect']:
            ok += 1
        elif c['name'] in verdicts:
            ok += 1; print('VERDICT', c['name'], '—', verdicts[c['name']])
        else:
            bad += 1; print('FAIL', c['name'], c['fn'], c['args'], '| want', repr(c['expect']), '| got', repr(g))
    # the live cases (Acuity / Newell / Danfoss 11-05)
    acuity = ['Job Board - Glassdoor', 'Job Board - Indeed', 'Job Board - Other', 'LinkedIn', 'Company Website', 'Employee Referral']
    for name, cond in [('acuity simplify row → LinkedIn', job_board.board_pick(acuity, 'simplify', 'https://simplify.jobs/p/x', DEFAULTS) == 'LinkedIn'),
                       ('acuity list names sites', any(R.SITE_BOARD.search(o) for o in acuity)),
                       ('newell link', R.privacy_link('Review and Accept Data Privacy Consent Statement')),
                       ('danfoss veteran zero-width', canon.audit([{'label': 'Veteran Status', 'value': 'I am not a protected veteran​'}]) == [])]:
        ok += cond; bad += (not cond); print(('ok   ' if cond else 'FAIL ') + name)
    print(f"{ok}/{len(cases) + 4} ok")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
