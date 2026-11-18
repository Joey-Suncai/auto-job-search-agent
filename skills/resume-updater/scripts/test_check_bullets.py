#!/usr/bin/env python3
"""DeepSeek-written cases for check_bullets (scripts/test_cases/check_bullets_cases.json) and direction_master.check
(scripts/test_cases/master_check_cases.json) — JSA-250, rule 13. Disagreements need a verdict in
scripts/test_cases/<name>_verdicts.json.    python3 skills/resume-updater/scripts/test_check_bullets.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import check_bullets as CB  # noqa: E402
import direction_master as DM  # noqa: E402

TC = os.path.join(REPO, 'scripts', 'test_cases')
BULLET_KINDS = [('opener', 'opener:'), ('verb', 'verb:'), ('why', 'why:'), ('problem', 'problem:'), ('causal', 'causal:'), ('length', 'length:'), ('banned', 'banned'),
                ('too_many_bullets', 'bullets >'), ('repeated_opener', 'context opener'), ('repeated_verb', ' opens '),
                ('shape_dominant', 'shape "'), ('few_shapes', 'sentence shape(s)'), ('outcome_first', 'outcome_first')]
MASTER_KINDS = [('not_resume_entry', 'not a resume entry'), ('entries_missing', 'entries missing'), ('too_many', 'bullets >'),
                ('no_fact_ids', 'no fact ids'), ('unknown_fact', 'unknown fact id'), ('wrong_entry', 'belongs to'),
                ('off_resume', 'kept off the resume'), ('not_bullet', 'not a resume bullet'), ('summary_number', 'summary: number'),
                ('summary_never', 'summary: never-phrase'), ('summary_length', 'characters > 320'),
                ('number', 'is not a current number'), ('never', 'never-phrase'), ('pair', '" needs "'),
                ('star_missing', 'star_missing'), ('skill_not_true', 'confirmed NOT used'), ('skill_unknown', "is not in skills.true"),
                ('bold_too_many', 'bold_too_many'), ('bold_missing', 'bold_missing'), ('bold_unknown', 'bold_unknown'),
                ('opener', 'opener:'), ('verb', 'verb:'), ('why', 'why:'), ('problem', 'problem:'), ('causal', 'causal:'), ('length', 'length:'), ('banned', 'banned'),
                ('repeated_opener', 'context opener'), ('repeated_verb', ' opens '), ('shape_dominant', 'shape "'),
                ('few_shapes', 'sentence shape(s)'), ('outcome_first', 'outcome_first')]


def kinds(errs, table):
    out = set()
    for e in errs:
        for k, mark in table:
            if mark in e:
                if k == 'never' and e.startswith('summary:'):
                    continue
                out.add(k)
                break
    return out


def run_set(name, fn):
    cases = json.load(open(os.path.join(TC, f'{name}_cases.json'), encoding='utf-8'))
    import glob
    for extra in sorted(glob.glob(os.path.join(TC, f'{name}_*_cases.json'))):   # added rule sets (lang, star, …)
        cases += json.load(open(extra, encoding='utf-8'))
    vp = os.path.join(TC, f'{name}_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = fn(c)
        except Exception as ex:
            got = {f'crash:{type(ex).__name__}:{ex}'}
        want = set(c.get('expect_kinds') or [])
        if got == want:
            print('PASS ', name, c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', name, c['name'], '— judged:', v['why'][:100]); continue
        bad += 1
        print('DIFF ', name, c['name'], '| want', sorted(want), '| got', sorted(got), '|', c.get('why', '')[:110])
    print(f'{name}: {len(cases)} cases, {bad} unresolved')
    return bad


def bullet_case(c):
    if c['fn'] == 'shape':
        got = CB.shape(c['text'])
        return set() if got == c.get('expect_shape') else {f'shape:{got}'}
    if c['fn'] == 'bullet':
        return kinds(CB.check_bullet(c['text']), BULLET_KINDS)
    return kinds(CB.check_master(c['master']), BULLET_KINDS)


def master_case(c):
    return kinds(DM.check(c['master'], c['facts'], 'x'), MASTER_KINDS)


def main():
    bad = run_set('check_bullets', bullet_case) + run_set('master_check', master_case)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
