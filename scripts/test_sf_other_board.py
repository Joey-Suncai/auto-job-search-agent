"""SuccessFactors: the "specify" box after a source list answered "Job Boards-Other (specify name below)" gets the board's
name — the job's own board, else the configured default (LinkedIn) — never "N/A" (Newell 2026-11-05, JSA-205).
DeepSeek wrote the cases from scripts/test_cases/sf_other_board_spec.md (rule 13); disagreements judged in
sf_other_board_verdicts.json. Tests run_successfactors.other_board (pure). Prints `N/M ok`; exit 1 on an unjudged failure."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_successfactors as R  # noqa: E402


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_other_board_cases.json'), encoding='utf-8'))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_other_board_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    ok = bad = 0
    for c in cases:
        a = c['args']
        got = R.other_board(a.get('picked'), a.get('job') or {}, a.get('defaults') if 'defaults' in a else ['LinkedIn', 'Indeed'])   # the spec's standard default
        e = c['expect']
        if (got is None) if e.get('none') else (got == e.get('board')):
            ok += 1
        elif c['name'] in verdicts:
            ok += 1; print('VERDICT', c['name'], '—', verdicts[c['name']][:160])
        else:
            bad += 1; print('FAIL', c['name'], '| want', e, '| got', repr(got), '|', a)
    print(f"{ok}/{len(cases)} ok")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
