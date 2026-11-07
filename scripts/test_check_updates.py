#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/check_updates_cases.json) against check_updates.check().
Claude judges every disagreement and records the verdict in scripts/test_cases/check_updates_verdicts.json
(case name → "code" = the check was wrong and was fixed / "case" = the case misread the spec, with the reason).
A disagreement without a verdict fails the run.    python3 scripts/test_check_updates.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_updates as C  # noqa: E402

TAGS = [(1, 'BACKLOG:'), (2, 'answer_rules.js'), (3, 'eligibility_rules'), (4, 'runner code'), (5, 'submitted'),
        (6, 'LaunchAgent'), (7, 'session log'), (8, 'config/profile.json')]


def rules_of(msgs):
    return sorted({n for m in msgs for n, t in TAGS if t in m})


def table(st):
    return '\n'.join(f'| {k} | P1 | runner | x | lead | {v} | a | r |' for k, v in st.items())


def run(case):
    results_old, results_new, apps, fmap = [], [], [], {}
    for i, r in enumerate(case.get('results_new_submitted') or []):
        results_new.append({'folder': r['folder'], 'status': 'submitted', 'at': f'2026-10-31T00:00:{i:02d}'})
        if r.get('job_id'):
            fmap[r['folder']] = r['job_id']
            if r.get('in_tracker'): apps.append({'job_id': r['job_id']})
    results_new += [{'folder': f'other{i}', 'status': 'unconfirmed'} for i in range(int(case.get('results_other_new_lines') or 0))]
    texts_new = {'BACKLOG.md': table(case.get('backlog_after') or {}), 'data/runner/results.jsonl': '\n'.join(map(json.dumps, results_new)),
                 'data/store/applications.jsonl': '\n'.join(map(json.dumps, apps)) if 'data/store/applications.jsonl' in case['staged'] else ''}
    texts_old = {'BACKLOG.md': table(case.get('backlog_before') or {}), 'data/runner/results.jsonl': '\n'.join(map(json.dumps, results_old)),
                 'data/store/applications.jsonl': '\n'.join(map(json.dumps, apps))}
    return C.check(case['staged'], lambda p: texts_new.get(p, ''), lambda p: texts_old.get(p, ''), '2026-10-31', fmap,
                   bool(case.get('session_log_today_exists')))


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'check_updates_cases.json')))
    pp = os.path.join(HERE, 'test_cases', 'check_updates_profile_cases.json')   # rule 8 (JSA-077)
    cases += json.load(open(pp)) if os.path.exists(pp) else []
    vp = os.path.join(HERE, 'test_cases', 'check_updates_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        E, W = run(c)
        got = ('block' if E else 'pass', rules_of(E), rules_of(W))
        want = (c['expect'], sorted(int(x) for x in c.get('expect_errors') or []), sorted(int(x) for x in c.get('expect_notes') or []))
        if got == want:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '— judged: case misreads the spec:', v['why'][:110]); continue
        bad += 1
        print('DIFF ', c['name'], '| want', want, '| got', got, '|', (E + W)[:2])
    print(f'{len(cases)} cases, {bad} unresolved')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
