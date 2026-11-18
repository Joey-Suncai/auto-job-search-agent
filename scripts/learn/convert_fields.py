#!/usr/bin/env python3
"""Old per-runner field records → the unified fields.jsonl corpus (JSA-187; input of the form replay, JSA-188).

Since JSA-187 every runner on runner_common writes `data/runner/fields/<YYYY-MM>.jsonl` itself. Runs before that left their
fields in three per-runner shapes; this converts them once (and again whenever it is run — the output is rebuilt):

  form_check.json  run_form (Lever / Ashby) and the newer runners: `fields` / `sections[].fields` / `steps[].fields`
  wd_log.json      Workday: `pages[].fields` {label, answer, value, status, source}; when a submit-from-Review run left
                   only the Review page there, wd_answered.json {"<section>||<label>": value} (source wd_answered:<section>)
  plan.json        Greenhouse: `fields` {label, answer, status} + verify.json (pass, bad) for what the page held

Reads every application folder in the data home and every `data/runner/dryrun/<ats>/<run>/`; writes
`data/runner/fields/legacy.jsonl` (one line per field, run_id "<folder>@legacy"). Read-only on the folders.

    python3 scripts/learn/convert_fields.py [--home <data home>] [--out <file>]
"""
import argparse, glob, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
import paths as jpaths  # noqa: E402
import runner_common as RC  # noqa: E402
import canon  # noqa: E402


def wd_field(f, failed=frozenset()):
    """Pure (tested, JSA-320). One wd_log.json field with the value the page held AFTER the fill as `page`.
    New logs (from 2026-11-11) carry `page` (the read-back) and `before`: kept as they are. Older logs kept only
    `value`, read before the fill (often the résumé parse: UIUC GPA 3.85 where 3.60 was typed). For those, a field the
    runner filled (status 'ok') and that is not in the log's `failed` list passed the runner's read-back check, so the
    page held the answer: page = answer, and `value` is kept as `before`. Any other field keeps `value` as its page."""
    if 'before' in f or 'page' in f:
        return f
    out = dict(f)
    if f.get('status') == 'ok' and (f.get('section'), f.get('label')) not in failed and isinstance(f.get('answer'), str):
        out['before'], out['page'] = f.get('value'), f['answer']
    return out


def rows_of(folder):
    """Pure-ish (tested). (ats, url, rows) of one run folder from its old records, or None when it has none."""
    fc, wd, pl = (os.path.join(folder, n) for n in ('form_check.json', 'wd_log.json', 'plan.json'))
    try:
        if os.path.exists(fc):
            d = json.load(open(fc, encoding='utf-8'))
            rows = RC.field_rows(d)
            if rows:
                return d.get('ats'), d.get('posting') or d.get('url') or '', rows
        if os.path.exists(wd):
            d = json.load(open(wd, encoding='utf-8'))
            failed = {(x.get('section'), x.get('label')) for x in d.get('failed') or [] if isinstance(x, dict)}
            flat = [wd_field(f, failed) for p in d.get('pages') or [] for f in p.get('fields') or []]
            rows = RC.field_rows({'fields': flat})
            if rows:
                return 'workday', d.get('url') or '', rows
            wa = os.path.join(folder, 'wd_answered.json')        # a submit-from-Review run rewrites wd_log.json with the Review
            if os.path.exists(wa):                               # page only; the filled answers survive here ("<section>||<label>")
                ans = json.load(open(wa, encoding='utf-8'))
                flat = [{'label': k.split('||', 1)[-1], 'want': v, 'page': v, 'ok': True,
                         'source': 'wd_answered' + (':' + k.split('||', 1)[0] if '||' in k and k.split('||', 1)[0] else '')}
                        for k, v in (ans.items() if isinstance(ans, dict) else []) if str(v or '').strip()]
                rows = RC.field_rows({'fields': flat})
                if rows:
                    return 'workday', d.get('url') or '', rows
        if os.path.exists(pl):
            d = json.load(open(pl, encoding='utf-8'))
            v = {}
            if os.path.exists(os.path.join(folder, 'verify.json')):
                v = json.load(open(os.path.join(folder, 'verify.json'), encoding='utf-8'))
            bad = {str(b.get('label') if isinstance(b, dict) else b)[:120] for b in v.get('bad') or []}
            flat = []
            for f in d.get('fields') or []:
                lab = f.get('label') or ''
                ok = bool(v.get('pass')) and lab[:120] not in bad and f.get('status') == 'ok'
                flat.append({'label': lab, 'want': f.get('answer'), 'page': f.get('answer') if ok else None,
                             'source': f.get('source') or f.get('rule') or '', 'type': f.get('type') or '',
                             'required': f.get('required'), 'ok': ok, 'options': f.get('options') or []})
            rows = RC.field_rows({'fields': flat})
            if rows:
                return d.get('ats') or 'greenhouse', d.get('url') or '', rows
    except (OSError, ValueError):
        return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--home', help='data home (default: the configured one)'); ap.add_argument('--out')
    a = ap.parse_args()
    if a.home:
        os.environ['JSA_HOME'] = a.home
    runs = sorted(glob.glob(jpaths.apps('*', '')) + glob.glob(jpaths.data('runner', 'dryrun', '*', '*', '')))
    out = a.out or jpaths.data('runner', 'fields', 'legacy.jsonl')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ats_of = {}                                                  # folder → ats from the results ledger (form_check has none)
    try:
        for line in open(jpaths.data('runner', 'results.jsonl'), encoding='utf-8'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get('ats'):
                ats_of[d.get('folder')] = d['ats']
    except OSError:
        pass
    n_runs = n_fields = 0
    with open(out + '.tmp', 'w', encoding='utf-8') as o:
        for f in runs:
            got = rows_of(f)
            if not got:
                continue
            ats, url, rows = got
            name = os.path.basename(os.path.normpath(f))
            at = datetime.fromtimestamp(os.path.getmtime(f)).astimezone().isoformat(timespec='seconds')
            for line in RC.field_lines(rows, run_id=f'{name}@legacy', at=at, folder=name, ats=ats or ats_of.get(name) or '',
                                       tenant=canon.tenant_of(url), hard=[]):
                o.write(json.dumps(line, ensure_ascii=False) + '\n'); n_fields += 1
            n_runs += 1
    os.replace(out + '.tmp', out)
    print(f'{n_runs} runs · {n_fields} fields → {out}')


if __name__ == '__main__':
    main()
