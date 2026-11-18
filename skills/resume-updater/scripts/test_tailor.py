#!/usr/bin/env python3
"""DeepSeek-written cases for truth_check.py and tailor.py (scripts/test_cases/{truth_check,tailor,tailor_alt}_cases.json) — JSA-251,
rule 13. Disagreements need a verdict in scripts/test_cases/<name>_verdicts.json.
    python3 skills/resume-updater/scripts/test_tailor.py"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import truth_check as TC  # noqa: E402
import tailor as TL  # noqa: E402

TCDIR = os.path.join(REPO, 'scripts', 'test_cases')
TT_KINDS = [('swap_not_variant', 'swap_not_variant'), ('new_sentence', 'new_sentence'), ('entry_moved', 'entry_moved'),
            ('fact_ids_changed', 'fact_ids_changed'), ('summary_changed', 'summary_changed'), ('headline_term', 'headline_term'),
            ('skill_added_untrue', 'skill_added_untrue'), ('core_dropped', 'core_dropped')]
TX_KINDS = [('pair', 'pair:'), ('never', 'never-phrase'), ('number', 'number '), ('banned', 'banned:')]


def kinds(errs, table):
    out = set()
    for e in errs:
        for k, mark in table:
            if mark in e:
                out.add(k)
                break
    return out


def _fb(f):
    f = dict(f or {})
    f.setdefault('entries', [])
    f.setdefault('facts', [])
    f.setdefault('skills', {'true': {}, 'not_true': []})
    f['skills'].setdefault('true', {})
    f['skills'].setdefault('not_true', [])
    f['entries'] = [dict({'kind': 'project'}, **e) for e in f['entries']]
    return f


def truth_case(c):
    if c['fn'] == 'variant':
        got = (TC.is_variant(c['a'], c['b']), TC.is_bullet_variant(c['a'], c['b']))
        want = (c['expect_variant'], c['expect_bullet_variant'])
        return set() if got == want else {f'variant:{got}'}, set()
    if c['fn'] == 'text':
        return kinds(TC.check_text(c['text'], _fb(c['facts']), c.get('jd') or '', c.get('profile') or ''), TX_KINDS), set(c.get('expect_kinds') or [])
    errs = TC.check_tailored(c['tailored'], c['approved'], _fb(c['facts']), None, c.get('title'))
    return kinds(errs, TT_KINDS), set(c.get('expect_kinds') or [])


def tailor_case(c):
    if c['fn'] == 'terms':
        got = [[x['term'], x['jd_spelling'], x['score']] for x in TL.jd_terms(c['jd'], c['role'], c.get('title') or '', c.get('n') or 12)]
        want = [[a, b, round(float(s), 4)] for a, b, s in c['expect']]
        return set() if got == want else {f'terms:{got}'}, set()
    if c['fn'] == 'parse':
        got = list(TL.parse_jd(c['text'], c.get('folder') or ''))
        return set() if got == list(c['expect']) else {f'parse:{got}'}, set()
    m = c['master']
    m.setdefault('reserve', [])
    t, terms, changes = TL.tailor(m, _fb(c['facts']), c['role'], c['jd'], c.get('title') or '')
    bad = set()
    if 'expect_swaps' in c and sorted([s['from'], s['to']] for s in t['swaps']) != sorted(map(list, c['expect_swaps'])):
        bad.add(f"swaps:{[[s['from'], s['to']] for s in t['swaps']]}")
    if 'expect_added' in c:
        added = sorted(re.findall(r'skill added: "([^"]+)"', '\n'.join(changes)))
        if added != sorted(c['expect_added']):
            bad.add(f'added:{added}')
    if c.get('expect_headline') is not None and c.get('title') and t.get('headline') != c['expect_headline']:
        bad.add(f"headline:{t.get('headline')}")
    for eid, txt in (c.get('expect_first_bullets') or {}).items():
        e = next((e for e in t['entries'] if e['entry_id'] == eid), None)
        if not e or e['bullets'][0]['text'] != txt:
            bad.add(f'first:{eid}')
    for eid, txts in (c.get('expect_bullets') or {}).items():
        e = next((e for e in t['entries'] if e['entry_id'] == eid), None)
        if not e or [b['text'] for b in e['bullets']] != txts:
            bad.add(f"bullets:{eid}:{[b['text'][:30] for b in e['bullets']] if e else None}")
    return bad, set()


def core_case(c):
    """tailor_core cases: core bullets in tailor (fn tailor) and in truth_check (fn tailored, only core_dropped / new_sentence)."""
    if c['fn'] == 'tailored':
        got, want = truth_case(c)
        return got & {'core_dropped', 'new_sentence'}, want
    return tailor_case(c)


def run_set(name, fn):
    cases = json.load(open(os.path.join(TCDIR, f'{name}_cases.json'), encoding='utf-8'))
    vp = os.path.join(TCDIR, f'{name}_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got, want = fn(c)
        except Exception as ex:
            got, want = {f'crash:{type(ex).__name__}:{ex}'}, set()
        if got == want:
            print('PASS ', name, c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', name, c['name'], '— judged:', v['why'][:100]); continue
        bad += 1
        print('DIFF ', name, c['name'], '| want', sorted(want), '| got', sorted(got)[:3], '|', c.get('why', '')[:120])
    print(f'{name}: {len(cases)} cases, {bad} unresolved')
    return bad


def main():
    bad = run_set('truth_check', truth_case) + run_set('tailor', tailor_case) + run_set('tailor_alt', tailor_case) + run_set('tailor_core', core_case)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
