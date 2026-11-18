#!/usr/bin/env python3
"""Measure: does claude-sonnet-5-5 read job mail as well as claude-opus-5-5? (JSA-255, Joey 2026-11-08)

    ~/.job-agent-venv/bin/python scripts/daily/compare_reader.py --days 14 [--max 150]

Read-only: fetches mail from Gmail the same way email_check.py does (IMAP, readonly), keeps the messages the daily run
would send to Claude (same recall rules as email_check.apply_mail), and reads each one with BOTH models through
claude_reader.Reader (same system prompt, schema, effort "medium", same tracker block). Nothing is written to the store.
Opus is the reference. Per message it compares: is_job_related, type, job_id, deadline, whether an action is needed.
Output: data home data/runner/daily/reader_compare_<date>.md (agreement table, every disagreement with both reasons)
and .jsonl (both verdicts per message), plus token use and cost per model.
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'config'))
sys.path.insert(0, os.path.join(REPO, 'scripts', 'store'))
import paths  # noqa: E402
import email_check as EC  # noqa: E402
import claude_reader as CR  # noqa: E402

MODELS = {'opus': 'claude-opus-5-5', 'sonnet': 'claude-sonnet-5-5'}
PRICE = {'opus': (4.0, 20.0, 0.20), 'sonnet': (2.0, 10.0, 0.20)}   # $ / MTok: input, output, cache read
FIELDS = ['is_job_related', 'type', 'job_id', 'deadline', 'action']


def candidates(msgs, apps):
    """The messages email_check.apply_mail would hand to the Claude reader."""
    out = []
    for m in msgs:
        kind = EC.classify(m['subject'], m['body'])
        if kind is None:
            continue
        ats = bool(EC.ATS.search(m['sender']))
        a = EC.match(apps, m['sender'], m['subject'], m['body'])
        if m.get('bulk') and kind not in ('Rejection', 'Confirmation') and not ats and not a:
            continue
        if a or ats or EC.JOBWORDS.search(m['subject'] + ' ' + m['body'][:4000]):
            out.append(m)
    return out


def view(v):
    return {'is_job_related': bool(v.get('is_job_related')), 'type': v.get('type'), 'job_id': v.get('job_id') or '',
            'deadline': v.get('deadline') or '', 'action': bool((v.get('action_needed') or '').strip())}


def cost(k, u):
    pi, po, pc = PRICE[k]
    return (u['input'] * pi + u['output'] * po + u['cache_read'] * pc) / 1e6


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--days', type=int, default=14)
    ap.add_argument('--max', type=int, default=150)
    a = ap.parse_args(argv)
    import store
    apps = store.load('applications')
    msgs = EC.fetch(a.days)
    cand = candidates(msgs, apps)[:a.max]
    print(f'{len(msgs)} messages in {a.days} days → {len(cand)} the daily run would give Claude')
    readers = {}
    for k in MODELS:
        readers[k] = CR.Reader(apps)
    rows = []
    for i, m in enumerate(cand, 1):
        out = {'id': m['id'], 'date': m['date'], 'subject': m['subject'][:120], 'sender': m['sender'][:80]}
        for k, model in MODELS.items():
            CR.MODEL = model
            try:
                out[k] = readers[k].read(m)
            except Exception as e:
                out[k] = {'error': f'{type(e).__name__}: {str(e)[:160]}'}
        rows.append(out)
        if i % 10 == 0:
            print(f'  {i}/{len(cand)}')
    CR.MODEL = MODELS['opus']
    ok = [r for r in rows if 'error' not in r['opus'] and 'error' not in r['sonnet']]
    agree = {f: sum(view(r['opus'])[f] == view(r['sonnet'])[f] for r in ok) for f in FIELDS}
    full = sum(all(view(r['opus'])[f] == view(r['sonnet'])[f] for f in FIELDS) for r in ok)
    # the fields that change the tracker: type + job_id on job mail
    job = [r for r in ok if view(r['opus'])['is_job_related'] or view(r['sonnet'])['is_job_related']]
    tracker = sum(view(r['opus'])['type'] == view(r['sonnet'])['type'] and view(r['opus'])['job_id'] == view(r['sonnet'])['job_id'] for r in job)
    day = datetime.date.today().isoformat()
    base = paths.data('runner', 'daily', f'reader_compare_{day}')
    with open(base + '.jsonl', 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    n = len(ok)
    L = [f'# Mail reader: Sonnet 5.5 vs Opus 5.5 ({day})', '',
         f'{len(msgs)} messages from the last {a.days} days; {len(cand)} would go to Claude; {n} read by both '
         f'({len(rows) - n} errors). Opus = reference. Same prompt, schema, effort medium.', '',
         '| Field | Agree |', '| --- | --- |']
    L += [f'| {f} | {agree[f]} / {n} ({agree[f] / n:.0%}) |' for f in FIELDS] if n else []
    if n:
        L += [f'| **all five fields** | {full} / {n} ({full / n:.0%}) |',
              f'| **tracker effect (type + job_id) on job mail** | {tracker} / {len(job)} ({tracker / max(1, len(job)):.0%}) |']
    L += ['', '| Model | Calls | Input | Cache read | Output | Cost | Per message |', '| --- | --- | --- | --- | --- | --- | --- |']
    for k in MODELS:
        u = readers[k].usage
        c = cost(k, u)
        L.append(f"| {MODELS[k]} | {u['calls']} | {u['input']:,} | {u['cache_read']:,} | {u['output']:,} | ${c:.3f} | ${c / max(1, u['calls']):.4f} |")
    L += ['', '## Disagreements', '']
    for r in ok:
        o, s = view(r['opus']), view(r['sonnet'])
        diff = [f for f in FIELDS if o[f] != s[f]]
        if diff:
            L.append(f"- **{r['subject']}** ({r['date']}) — " + '; '.join(f'{f}: Opus `{o[f]}` / Sonnet `{s[f]}`' for f in diff))
            L.append(f"  - Opus: {r['opus'].get('reason', '')[:200]}")
            L.append(f"  - Sonnet: {r['sonnet'].get('reason', '')[:200]}")
    for r in rows:
        if r not in ok:
            L.append(f"- error on {r['subject']}: opus {r['opus'].get('error', 'ok')} · sonnet {r['sonnet'].get('error', 'ok')}")
    open(base + '.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L[:16]))
    print(f'report → {base}.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
