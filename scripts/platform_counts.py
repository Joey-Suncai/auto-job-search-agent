#!/usr/bin/env python3
"""Count the job store by application platform (JSA-113): rows, 可投, 可投 A/B, internships vs new grad.
Read only — never writes the store. Spec: scripts/test_cases/platform_counts_spec.md (tests: scripts/test_platform_counts.py).

    python3 scripts/platform_counts.py                 # markdown table, every matched platform
    python3 scripts/platform_counts.py --min 10 --json # platforms with ≥ 10 rows, as JSON
    python3 scripts/platform_counts.py --store <jobs.jsonl>
"""
import argparse, json, os, re, sys
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
DEFAULT_STORE = jpaths.data('store', 'jobs.jsonl')

SUFFIXES = [
    ('workable', ['workable.com']), ('jazzhr', ['applytojob.com', 'jazzhr.com']), ('adp', ['adp.com']),
    ('ukg', ['ultipro.com', 'ukg.net']), ('rippling', ['rippling.com', 'rippling-ats.com']),
    ('dayforce', ['dayforcehcm.com']), ('paycom', ['paycomonline.net', 'paycom.com']), ('taleo', ['taleo.net']),
    ('paylocity', ['paylocity.com']), ('eightfold', ['eightfold.ai']), ('avature', ['avature.net']),
    ('yello', ['yello.co']), ('jobvite', ['jobvite.com']), ('clearcompany', ['clearcompany.com']),
    ('breezy', ['breezy.hr']), ('jibe', ['jibeapply.com']), ('bamboohr', ['bamboohr.com']),
    ('smartrecruiters', ['smartrecruiters.com']), ('icims', ['icims.com']), ('oracle', ['oraclecloud.com']),
    ('successfactors', ['successfactors.com', 'successfactors.eu', 'sapsf.com']), ('greenhouse', ['greenhouse.io']),
    ('tiktok', ['lifeattiktok.com', 'careers.tiktok.com']), ('bytedance', ['joinbytedance.com', 'jobs.bytedance.com']),
    ('workday', ['myworkdayjobs.com', 'myworkdaysite.com']), ('ashby', ['ashbyhq.com']), ('lever', ['lever.co']),
]
CERTIFIED = {'greenhouse', 'workday', 'ashby', 'lever'}            # scorecard bars met (JSA-050)
HAS_RUNNER = {'oracle', 'smartrecruiters', 'workable', 'successfactors'}   # submit path, not yet certified
DRY_RUN = {'icims', 'jibe', 'tiktok'}                               # run_icims.py dry-run (JSA-093) · run_tiktok.py: Joey presses Submit
SF_PATH = re.compile(r'/job/[^/]+/\d{8,12}/?', re.I)                # SuccessFactors RMK job page (JSA-170)
AB = ('A', 'B')


def platform_of(url):
    if not url or not isinstance(url, str):
        return None
    try:
        host = (urlparse(url.strip()).hostname or '').lower().strip('.')
    except ValueError:
        return None
    if not host:
        return None
    for name, sufs in SUFFIXES:
        if any(host == s or host.endswith('.' + s) for s in sufs):
            return name
    return _sf_own_domain(url, host)


def _sf_own_domain(url, host):
    """SuccessFactors career sites on the company's own host (JSA-170): ?ats=successf… or /job/<slug>/<8-12 digits>."""
    if host == 'builtin.com' or host.endswith('.builtin.com'):
        return None
    try:
        u = urlparse(url.strip())
    except ValueError:
        return None
    if any(v.lower().startswith('successf') for v in parse_qs(u.query).get('ats', [])):
        return 'successfactors'
    return 'successfactors' if SF_PATH.fullmatch(u.path) else None


def row_platform(row):
    return platform_of(row.get('ats_url') or '') or platform_of(row.get('url') or '')


def runner_status(platform):
    """Pure (tested). Platform name (or None) → the dashboard's Runner value (JSA-177): 'ready' = certified runner,
    'testing' = a runner that is not certified yet (submit path or dry-run only), 'none' = known platform without a
    runner, 'unknown' = no platform found."""
    if not platform:
        return 'unknown'
    if platform in CERTIFIED:
        return 'ready'
    if platform in HAS_RUNNER or platform in DRY_RUN:
        return 'testing'
    return 'none'


def runner_fields(row):
    """{'platform': name or '', 'runner': runner_status(...)} for one store row (the dashboard adds these at build time;
    the store is never written)."""
    p = row_platform(row)
    return {'platform': p or '', 'runner': runner_status(p)}


def summarize(rows):
    out = {}
    for r in rows:
        p = row_platform(r)
        if p is None:
            continue
        c = out.setdefault(p, {'rows': 0, 'ok': 0, 'ok_ab': 0, 'ok_intern': 0, 'ok_newgrad': 0, 'ab_any': 0})
        tier, level = r.get('tier') or '', r.get('level') or ''
        c['rows'] += 1
        if tier in AB or (tier == 'Blocked' and (r.get('tier_orig') or '') in AB):
            c['ab_any'] += 1
        if (r.get('elig') or '') == '可投':
            c['ok'] += 1
            c['ok_ab'] += tier in AB
            if level == 'Internship':
                c['ok_intern'] += 1
            elif level:
                c['ok_newgrad'] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', default=DEFAULT_STORE); ap.add_argument('--min', type=int, default=0)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.store, encoding='utf-8') if l.strip()]
    s = {k: v for k, v in summarize(rows).items() if v['rows'] >= a.min}
    order = sorted(s, key=lambda k: (-s[k]['ok_ab'], -s[k]['ok'], -s[k]['rows']))
    if a.json:
        json.dump({k: s[k] for k in order}, sys.stdout, ensure_ascii=False, indent=1); print(); return
    print(f'{len(rows)} rows in {a.store}\n')
    print('| platform | status | rows | 可投 | 可投 A/B | 可投 intern | 可投 new grad | A/B any elig |')
    print('|---|---|---:|---:|---:|---:|---:|---:|')
    for k in order:
        c = s[k]
        st = {'ready': 'certified', 'none': 'none'}.get(runner_status(k)) or ('runner' if k in HAS_RUNNER else 'dry-run')
        print(f"| {k} | {st} | {c['rows']} | {c['ok']} | {c['ok_ab']} | {c['ok_intern']} | {c['ok_newgrad']} | {c['ab_any']} |")


if __name__ == '__main__':
    main()
