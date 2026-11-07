#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/resolve_careers_cases.json + _b … _n, from resolve_careers_spec.md) against
the pure steps of skills/job-hunt-pipeline/scripts/resolve_careers.py (JSA-055 / JSA-091). Claude judges every
disagreement in resolve_careers_verdicts.json ("code" = fixed / "case" = the case misread the spec, with the reason).
    python3 scripts/test_resolve_careers.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import resolve_careers as RC  # noqa: E402


def norm(x):
    return json.loads(json.dumps(x))                       # tuples → lists


def run(c):
    f, a = c['fn'], c['args']
    if f == 'detect_ats':
        t = a['text']
        if a.get('pad'):                                   # resolve_careers_n: a long run built by the harness
            t = t.replace('{PAD}', a['pad'][0] * int(a['pad'][1]))
        return norm(RC.detect_ats(t))
    if f == 'names_company':
        return RC.names_company(a['page'], a['company'], a.get('final_url') or '')
    if f == 'is_challenge':
        return RC.is_challenge(a['status'], a['page'])
    if f == 'norm_title':
        return RC.norm_title(a['t'])
    if f == 'city_of':
        return RC.city_of(a['location'])
    if f == 'match_posting':
        r = RC.match_posting(a['title'], a.get('location', ''), [tuple(p) for p in a['postings']])
        return r[2] if r else None
    if f == 'domain_candidates':
        return RC.domain_candidates(a['company'])
    if f == 'board_guesses':
        return norm(RC.board_guesses(a['company']))
    if f == 'same_name':
        return RC.same_name(a['a'], a['b'])
    if f == 'pick_lookup':
        return RC.pick_lookup(a['company'], a['suggestions'])
    if f == 'borrow_domains':
        return RC.borrow_domains(a['company'], a['jobs'])
    if f == 'script_srcs':
        return RC.script_srcs(a['page'], a['base'])
    if f == 'sitemap_career_urls':
        return RC.sitemap_career_urls(a['xml'])
    if f == 'title_companies':
        return RC.title_companies(a['title'], a['company'])
    if f == 'kind':
        return RC.kind(a['url'])
    if f == 'wd_queries':
        return RC.wd_queries(a['title'])
    if f == 'career_links':
        return RC.career_links(a['page'], a['base'])
    if f == 'wikidata_pick':
        return RC.wikidata_pick(a['company'], a['results'])
    if f == 'alias_domains':
        return RC.alias_domains(a['company'], a['table'])
    if f == 'looks_like_title':
        return RC.looks_like_title(a['company'])
    if f == 'paren_acronym':
        return RC.paren_acronym(a['company'])
    if f == 'foreign_host':
        return RC.foreign_host(a['host'])
    if f == 'inv_keys':
        import ats_inventory
        return ats_inventory.keys(a['name'])
    if f == 'inv_hint_of':
        import ats_inventory
        h = ats_inventory.hint_of(a['fname'], a['name'], a['url'])
        return norm(h) if h else None
    if f == 'inv_lookup':
        import ats_inventory, tempfile
        with tempfile.TemporaryDirectory() as d:
            for fn, text in a['files'].items():
                open(os.path.join(d, fn), 'w').write(text)
            return norm([(s_, i if isinstance(i, str) else '/'.join(i)) for s_, i in ats_inventory.lookup(a['company'], d)])
    if f == 'decide':
        P = a.get('postings') or {}
        def po(system, ident, title):
            key = f'{system}:{ident[1]}/{ident[2]}' if system == 'workday' else f'{system}:{ident}'
            return [tuple(p) for p in P.get(key, [])]
        systems = [(s, tuple(i) if isinstance(i, list) else i) for s, i in a['systems']]
        r = RC.decide(a['row'], systems, po)
        return {k: v for k, v in r.items() if k in ('code', 'system', 'ats_url')}
    if f == 'lead_word':
        return RC.lead_word(a['label'], a['ws'])
    if f == 'run_key':
        return RC.run_key(a['argv'])
    if f == 'systems_back':
        return [[sy, list(i) if isinstance(i, tuple) else i, 'tuple' if isinstance(i, tuple) else 'str']
                for sy, i in RC.systems_back(a['systems'])]
    if f == 'targets':
        return [j['id'] for j in RC.targets(a['jobs'])]
    if f == 'checkpoint':
        import tempfile
        path = None if a.get('no_path') else os.path.join(tempfile.mkdtemp(), 'r.json.part.jsonl')
        if path and a.get('file_lines') is not None:
            open(path, 'w').write(''.join(ln + '\n' for ln in a['file_lines']))
        ck = RC.Checkpoint(path, a['key'], a.get('fresh', False))
        for d in a.get('puts') or []:
            ck.put(d)
        return norm({'comp': {k: list(v) for k, v in ck.comp.items()}, 'render': {k: list(v) for k, v in ck.render.items()},
                     'rows': ck.rows, 'resumed': ck.resumed(),
                     'file_after': [json.loads(x) for x in open(path)] if path and os.path.exists(path) else None})
    raise ValueError(f)


def main():
    cases = [c for f in ('resolve_careers_cases.json', 'resolve_careers_b_cases.json', 'resolve_careers_c_cases.json',
                        'resolve_careers_d_cases.json', 'resolve_careers_e_cases.json',
                        'resolve_careers_f_cases.json', 'resolve_careers_g_cases.json',
                        'resolve_careers_h_cases.json', 'resolve_careers_i_cases.json', 'resolve_careers_j_cases.json',
                        'resolve_careers_k_cases.json', 'resolve_careers_l_cases.json',
                        'resolve_careers_m_cases.json', 'resolve_careers_n_cases.json')
             for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]
    vp = os.path.join(HERE, 'test_cases', 'resolve_careers_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = run(c)
        except Exception as e:
            got = f'crash {type(e).__name__}: {e}'
        want = c['expect']
        if isinstance(want, dict) and isinstance(got, dict) and 'system' not in want:
            got = {k: v for k, v in got.items() if k in want}
        if got == want:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1
        print('FAIL ', c['name'], f'got {got!r} want {want!r}')
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
