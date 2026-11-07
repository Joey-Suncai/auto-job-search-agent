#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/ats_search_cases.json + _b … _f, from ats_search_spec.md) against the pure
steps of skills/job-hunt-pipeline/scripts/ats_search.py and resolve_careers.decide (JSA-112). Claude judges every
disagreement in ats_search_verdicts.json ("code" = fixed / "case" = the case misread the spec, with the reason).
    python3 scripts/test_ats_search.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import ats_search as AS  # noqa: E402
import resolve_careers as RC  # noqa: E402


def norm(x):
    return json.loads(json.dumps(x))                       # tuples → lists


def offline(*a, **k):
    raise AssertionError('postings_offline made a request')


def run(c):
    f, a = c['fn'], c['args']
    if f == 'root_domain':
        return AS.root_domain(a['host'])
    if f == 'career_hosts':
        return AS.career_hosts(a['site'])
    if f == 'clean_ident':
        return AS.clean_ident(a['system'], a['ident'])
    if f == 'with_site':
        return norm(AS.with_site([tuple(x) for x in a['systems']], a['site']))
    if f == 'parse_icims':
        return AS.parse_icims(a['page'], a['host'])
    if f == 'parse_rmk':
        return AS.parse_rmk(a['page'], a['base'])
    if f == 'parse_phenom':
        return AS.parse_phenom(a['page'])
    if f == 'parse_oracle':
        return AS.parse_oracle(a['d'], a['host'], a['site'])
    if f == 'parse_taleo':
        return AS.parse_taleo(a['d'], a['host'], a['cs'])
    if f == 'parse_jazz':
        return AS.parse_jazz(a['page'], a['host'])
    if f == 'parse_jobvite':
        return AS.parse_jobvite(a['page'], a['slug'])
    if f == 'parse_rss':
        return AS.parse_rss(a['xml'])
    if f == 'postings_offline':
        real, AS.fetch = AS.fetch, offline
        try:
            return AS.postings(a['system'], a['ident'], a.get('query', ''))
        finally:
            AS.fetch = real
    if f == 'backoff':
        return AS.backoff(a['attempt'], a.get('retry_after'))
    if f == 'is_blocked':
        return AS.is_blocked(a['status'], a['body'])
    if f == 'parse_sitemal':
        return AS.parse_sitemal(a['xml'])
    if f == 'jobvite_range':
        r = AS.jobvite_range(a['page'])
        return list(r) if r else None
    if f == 'parse_avature':
        return AS.parse_avature(a['page'])
    if f == 'ukg_load_url':
        return AS.ukg_load_url(a['page'], a['host'], a['tenant'])
    if f == 'detect_ats':
        six = ('adp', 'paycom', 'paylocity', 'dayforce', 'brassring', 'clearcompany')
        return [list(x) for x in RC.detect_ats(a['text']) if x[0] in six]
    if f == 'parse_adp':
        return AS.parse_adp(a['d'], a['host'], a['cid'], a['ccid'])
    if f == 'paycom_config':
        r = AS.paycom_config(a['page'])
        return list(r) if r else None
    if f == 'parse_paylocity':
        return AS.parse_paylocity(a['page'])
    if f == 'parse_dayforce':
        return AS.parse_dayforce(a['d'], a['tenant'], a['board'])
    if f == 'brassring_session':
        r = AS.brassring_session(a['page'])
        return list(r) if r else None
    if f == 'parse_brassring':
        return AS.parse_brassring(a['d'])
    if f == 'clearcompany_site_id':
        return AS.clearcompany_site_id(a['page'])
    if f == 'parse_clearcompany':
        return AS.parse_clearcompany(a['d'])
    if f == 'detect_ats_e':
        return [list(x) for x in RC.detect_ats(a['text']) if x[0] in ('dover', 'paycom', 'taleo', 'successfactors')]
    if f == 'tbe_ident':
        return AS.tbe_ident(a['ident'])
    if f == 'site_hosts':
        return AS.site_hosts(a['ident'], a['site'])
    if f == 'parse_tbe':
        return AS.parse_tbe(a['page'])
    if f == 'parse_dover':
        return AS.parse_dover(a['d'], a['name'])
    if f == 'rmk_site':
        return norm(RC.rmk_site(a['url'], a['page']))
    if f == 'live_offline':
        real, AS.fetch = AS.fetch, offline
        try:
            return AS.live(a['system'], a['ident'])
        finally:
            AS.fetch = real
    if f == 'inventory_hints':
        import ats_inventory
        def key(s_, i):
            return f'{s_}:{i}'
        hints = [(s_, tuple(i.split('/')) if s_ == 'workday' else i) for s_, i in a['hints']]
        live = {key(s_, i) for s_, i in a['live']}
        stub = {'lookup': (ats_inventory, 'lookup', lambda c: hints),
                'wd': (RC, 'wd_search_text', lambda t, q: ['x'] if key('workday', '/'.join(t)) in live else []),
                'board': (RC, 'board_postings', lambda s_, i: ['x'] if key(s_, i) in live else []),
                'live': (AS, 'live', lambda s_, i: key(s_, i) in live),
                'fetch': (RC, 'fetch', offline)}
        saved = {k: getattr(m, n) for k, (m, n, _) in stub.items()}
        for m, n, fn in stub.values():
            setattr(m, n, fn)
        try:
            return [[s_, '/'.join(i) if isinstance(i, tuple) else i] for s_, i in RC.inventory_hints(a['company'])]
        finally:
            for k, (m, n, _) in stub.items():
                setattr(m, n, saved[k])
    if f == 'detect_ats_f':                               # JSA-137
        keep = ('tiktok', 'bytedance', 'cornerstone', 'gem', 'pageup', 'personio', 'recruiterbox', 'softgarden', 'join', 'keka',
                'gupy', 'hrmos', 'herp', 'beisen', 'moka', 'darwinbox', 'eightfold', 'avature', 'ultipro')
        return sorted([list(x) for x in RC.detect_ats(a['text']) if x[0] in keep])
    if f == 'page_systems':
        return norm(RC.page_systems(a['url'], a['page']))
    if f == 'big_tech':
        return norm(RC.big_tech(a['company']))
    if f == 'csod_session':
        return list(AS.csod_session(a['page']))
    if f in ('throne_location',):
        return AS.throne_location(a['item'])
    if f == 'schema_location':
        return AS.schema_location(a['loc'])
    if f in ('join_company_id', 'keka_identifier', 'beisen_portal'):
        return getattr(AS, f)(a['page'])
    if f in ('parse_throne', 'parse_csod', 'parse_gem', 'parse_pageup', 'parse_personio', 'parse_recruiterbox', 'parse_softgarden',
             'parse_join', 'parse_keka', 'parse_gupy', 'parse_hrmos', 'parse_herp', 'parse_beisen'):
        return getattr(AS, f)(**a)
    if f == 'match_posting':
        r = RC.match_posting(a['title'], a.get('location', ''), [tuple(p) for p in a['postings']])
        return r[2] if r else None
    if f == 'decide':
        P = a.get('postings') or {}
        def po(system, ident, title):
            if system not in RC.SEARCHABLE and system not in AS.SYSTEMS:
                raise AssertionError(f'searched {system}')
            return [tuple(p) for p in P.get(f'{system}:{ident}', [])]
        r = RC.decide(a['row'], [tuple(s) for s in a['systems']], po)
        return {k: v for k, v in r.items() if k in ('code', 'system', 'ats_url')}
    raise ValueError(f)


def main():
    cases = [c for f in ('ats_search_cases.json', 'ats_search_b_cases.json', 'ats_search_c_cases.json',
                        'ats_search_d_cases.json', 'ats_search_e_cases.json',
                        'ats_search_f_cases.json')
             for c in json.load(open(os.path.join(HERE, 'test_cases', f)))]
    vp = os.path.join(HERE, 'test_cases', 'ats_search_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = run(c)
        except Exception as e:
            got = f'crash {type(e).__name__}: {e}'
        want = c['expect']
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
