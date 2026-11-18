#!/usr/bin/env python3
"""The audit's shared counting (ADR-0011 step 5, JSA-342): the parts of the certification scorecard that the Sunday audit
(`scripts/audit_sample.py --run`, a routine of the using system) needs, kept in the product so the routine does not depend
on the development tools. The development repo's platform scorecard imports these from here.

    platform(line)                  results.jsonl line → ATS name
    window_folders(results, recert) {platform: folders whose first submit is in the (re-)certification window}
    audit_gate(items, window, …)    the independent-audit bar for one platform
    load(root, since)               results, emails, folder → job id, DeepSeek cost, wrong answers, confirmation shots
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)

NONCRIT = 0.95            # non-critical answers right ≥ 95 % (Joey 2026-11-05)
AUDIT_FORMS = 10          # JSA-258 (Joey 2026-11-09): ≥ 10 audited forms in the window, 0 waiting, critical wrong 0
CERT_SINCE = '2026-10-31T19:00'   # Joey 2026-10-31 「从这次重新算」: certification counts folders first run from here
FOLDER = re.compile(r'^\d{4}-\d{2}-\d{2}_')


def platform(line):
    u = (line.get('url') or '').lower()
    for key, name in (('greenhouse', 'greenhouse'), ('myworkday', 'workday'), ('lever.co', 'lever'), ('ashbyhq', 'ashby')):
        if key in u:
            return name
    return line.get('ats') or 'other'


def jsonl(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()] if os.path.exists(p) else []


def window_folders(results, recert=None):
    """Pure (tested). {platform: sorted folders whose FIRST submitted line is in the window}: every submitted folder of
    `results` (already cut to the certification window by load(since=…)), or for a platform in `recert` only those
    submitted at/after its 'since' — the forms the audit bar counts (JSA-258). The platform is the folder's first line's."""
    first, head = {}, {}
    for r in sorted((r for r in results if FOLDER.match(r.get('folder') or '')), key=lambda r: r.get('at') or ''):
        head.setdefault(r['folder'], r)
        if r.get('status') == 'submitted' and r['folder'] not in first:
            first[r['folder']] = r
    out = {}
    for f, r in first.items():
        name = platform(head[f])
        rc = (recert or {}).get(name)
        if not rc or str(r.get('at') or '')[:19] >= str(rc.get('since') or '')[:19]:
            out.setdefault(name, []).append(f)
    return {k: sorted(v) for k, v in out.items()}


def audit_gate(items, window, need=AUDIT_FORMS, noncrit=NONCRIT, keep_covered=False):
    """Pure (tested). The independent-audit bar for ONE platform. items = that platform's audit items ({folder, judged,
    check, cls}); window = the folders that count. Only items whose folder is in the window count. An item is wrong when
    judged 'wrong'; right when judged 'right', or check 'right' with no judgment; otherwise pending. cls 'critical' or
    anything else (= non-critical). A wrong item with `covered` (the current rules answer it right, JSA-260) is neither
    wrong nor right — unless keep_covered — and adds to "covered" (key present only when > 0).
    → {forms, pending, critical_wrong, noncrit_right, noncrit_wrong, noncrit_accuracy, ok}."""
    win = set(window or ())
    mine = [it for it in items or () if it.get('folder') in win]
    g = dict(forms=len({it['folder'] for it in mine}), pending=0, critical_wrong=0, noncrit_right=0, noncrit_wrong=0)
    for it in mine:
        st = it.get('judged') or ('right' if it.get('check') == 'right' else None)
        crit = it.get('cls') == 'critical'
        if st == 'wrong' and it.get('covered') and not keep_covered:
            g['covered'] = g.get('covered', 0) + 1
        elif st not in ('right', 'wrong'):
            g['pending'] += 1
        elif st == 'wrong':
            g['critical_wrong' if crit else 'noncrit_wrong'] += 1
        elif not crit:
            g['noncrit_right'] += 1
    n = g['noncrit_right'] + g['noncrit_wrong']
    g['noncrit_accuracy'] = round(g['noncrit_right'] / n, 4) if n else None
    g['ok'] = (g['forms'] >= need and g['pending'] == 0 and g['critical_wrong'] == 0
               and (g['noncrit_accuracy'] is None or g['noncrit_accuracy'] >= noncrit))
    return g


def ds_costs(apps):
    out = {}
    for p in glob.glob(os.path.join(apps, '*', 'ds_usage.md')):
        tot = sum(float(m) for m in re.findall(r'est\. cost=\$([\d.]+)', open(p, encoding='utf-8').read()))
        out[os.path.basename(os.path.dirname(p))] = tot
    return out


def load(root=ROOT, since=None):
    sys.path.insert(0, os.path.join(root, 'scripts', 'store'))
    import sync_results
    D = jpaths.data if root == ROOT else (lambda *p: os.path.join(root, 'data', *p))           # a test passes its own root  paths-ok
    A = jpaths.apps if root == ROOT else (lambda *p: os.path.join(root, 'applications', *p))   # paths-ok
    results = jsonl(D('runner', 'results.jsonl'))
    if since:                                    # a folder counts only when its FIRST run is on/after `since`
        first = {}
        for r in results:
            first[r['folder']] = min(first.get(r['folder'], '9'), r.get('at') or '')
        results = [r for r in results if first[r['folder']] >= since]
    return (results, jsonl(D('store', 'emails.jsonl')), sync_results.folder_job_ids(),
            ds_costs(A()), jsonl(D('runner', 'wrong_answers.jsonl')),
            frozenset(os.path.basename(os.path.dirname(p)) for p in glob.glob(A('*', 'submitted_confirmation.*'))))
