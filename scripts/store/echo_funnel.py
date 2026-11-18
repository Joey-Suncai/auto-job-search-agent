#!/usr/bin/env python3
"""Echo funnel (JSA-360): interviews and assessments per 100 applications, split by track / tier / platform / résumé version /
referral / days to the first echo. Read-only derived data: tracker + e-mails + jobs, nothing is written to the data home.

The e-mail table is the event source (a company's Interview / Assessment e-mail is one echo, its date is the echo date; an
OA or HireVue is an Assessment). A Confirmation receipt is not an echo; an echo dated before the application is ignored.
Applications counted: those with an `applied_on` on or after `since` whose status is not Shortlisted / Archived.
A cell with fewer than MIN_N applications shows counts only, no per-100 figure.

    python3 scripts/store/echo_funnel.py [--since 2026-10-28]       # print the tables
"""
import glob, json, os, re, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
sys.path.insert(0, HERE)

SINCE = '2026-10-28'
MIN_N = 20
NOT_APPLIED = ('Shortlisted', 'Archived', '', None)
PLATFORMS = [('Workday', r'myworkday|workday'), ('Greenhouse', r'greenhouse'), ('Lever', r'lever\.co'), ('Ashby', r'ashbyhq'),
             ('iCIMS', r'icims'), ('SmartRecruiters', r'smartrecruiters'), ('Oracle', r'oraclecloud|taleo')]
def resume_version(files):
    """The résumé version named in a folder's file names ('' when none) — one rule, in sync_results."""
    import sync_results
    return sync_results.resume_version(files)


def platform_of(url):
    u = (url or '').lower()
    return next((n for n, rx in PLATFORMS if re.search(rx, u)), 'Other' if u else 'Unknown')


def _days(a, b):
    try:
        return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days
    except (ValueError, TypeError):
        return None


def _bucket(d):
    return '0–2' if d <= 2 else '3–6' if d <= 6 else '7–13' if d <= 13 else '14+'


def records(apps, emails, jobs, resumes=None):
    """Pure (tested). One record per application that was really sent (applied_on set, not Shortlisted / Archived):
    {job_id, on, track, tier, platform, resume, referral, interview, assessment, bucket} where bucket = days to the first echo
    ('' when none). The dashboard page filters these by its start date and counts them (dims below), so the date can be
    changed without a rebuild."""
    jobs_by = {j.get('id'): j for j in jobs or []}
    resumes = resumes or {}
    echoes = {}
    for e in emails or []:
        if e.get('type') in ('Interview', 'Assessment') and e.get('job_id') and e.get('date'):
            echoes.setdefault(e['job_id'], []).append((e['date'][:10], e['type']))
    out = []
    for a in apps or []:
        on = (a.get('applied_on') or '')[:10]
        if a.get('status') in NOT_APPLIED or not on:
            continue
        jid = a.get('job_id')
        ev = [(d, t) for d, t in echoes.get(jid, []) if d >= on]
        j = jobs_by.get(jid, {})
        out.append({'job_id': jid, 'on': on, 'track': j.get('track') or 'Unknown', 'tier': j.get('tier') or 'Unknown',
                    'platform': platform_of(j.get('url') or a.get('url')),
                    'resume': a.get('resume_version') or resumes.get(jid) or 'Unknown',
                    'referral': a.get('referral_status') or 'Unknown', 'declined': int(a.get('status') == 'Declined by Joey'),   # JSA-406
                    'interview': int(any(t == 'Interview' for _, t in ev)), 'assessment': int(any(t == 'Assessment' for _, t in ev)),
                    'bucket': _bucket(max(0, _days(on, min(d for d, _ in ev)) or 0)) if ev else ''})
    return out


DIMS = (('track', 'track'), ('tier', 'tier'), ('platform', 'platform'), ('resume', 'resume'), ('referral', 'referral'),
        ('first echo (days)', 'bucket'))


def group(recs, since=SINCE):
    """Pure (tested; the page's JS does the same counting). Records on or after `since` → {'total', 'rows'}."""
    cells = {}
    total = {'dim': 'total', 'value': 'All', 'apps': 0, 'interviews': 0, 'assessments': 0}

    def add(c, r):
        c['apps'] += 1; c['interviews'] += r['interview']; c['assessments'] += r['assessment']
    for r in recs:
        if r['on'] < since:
            continue
        add(total, r)
        for dim, key in DIMS:
            if r.get(key):                                    # the days bucket exists only for applications with an echo
                add(cells.setdefault((dim, r[key]), {'dim': dim, 'value': r[key], 'apps': 0, 'interviews': 0, 'assessments': 0}), r)
    for c in [total] + list(cells.values()):
        for k, key in (('per100_interview', 'interviews'), ('per100_assessment', 'assessments')):
            c[k] = round(100.0 * c[key] / c['apps'], 1) if c['apps'] >= MIN_N and not c['dim'].startswith('first echo') else None
    order = {d: i for i, (d, _) in enumerate(DIMS)}
    rows = sorted(cells.values(), key=lambda c: (order[c['dim']], -c['apps'], str(c['value'])))
    return {'since': since, 'min_n': MIN_N, 'total': total, 'rows': rows}


def funnel(apps, emails, jobs, since=SINCE, resumes=None):
    """Pure (tested). records() then group()."""
    return group(records(apps, emails, jobs, resumes), since)


# ----------------------------------------------------------------------------- data home
def _jsonl(p):
    out = []
    try:
        for line in open(p, encoding='utf-8'):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def build_records():
    import paths as jpaths
    import sync_results
    apps = _jsonl(jpaths.data('store', 'applications.jsonl'))
    emails = _jsonl(jpaths.data('store', 'emails.jsonl'))
    jobs = _jsonl(jpaths.data('store', 'jobs.jsonl'))
    resumes = {}
    try:
        for folder, jid in sync_results.folder_job_ids().items():
            v = resume_version(os.listdir(jpaths.apps(folder)))
            if v:
                resumes.setdefault(jid, v)
    except Exception:
        pass
    return records(apps, emails, jobs, resumes)


def build(since=SINCE):
    return group(build_records(), since)


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--since', default=SINCE)
    r = build(ap.parse_args().since)
    t = r['total']
    print(f"Echo funnel since {r['since']}: {t['apps']} applications · {t['interviews']} interview · {t['assessments']} assessment")
    for c in r['rows']:
        p = lambda x: '—' if x is None else f'{x}'
        print(f"  {c['dim']:<18} {str(c['value']):<16} apps {c['apps']:>4}  interview {c['interviews']:>3} ({p(c['per100_interview'])}/100)  assessment {c['assessments']:>3} ({p(c['per100_assessment'])}/100)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
