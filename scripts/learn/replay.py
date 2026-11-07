#!/usr/bin/env python3
"""Form replay — regression test of the answer rules on every form we have ever read (JSA-188).

Re-answers every stored form question (the fields corpus `data/runner/fields/*.jsonl`: one line per field, written by
runner_common since JSA-187, older runs converted by convert_fields.py) OFFLINE with the current answer rules
(skills/auto-apply/scripts/answer_rules.js through runner/rules_bridge.js — the runners' own path) and the current profile,
and compares each answer with the accepted baseline:

  * an answer that changed on a form that was SUBMITTED needs a recorded reason (`--reason`), otherwise --check fails
    — changing what a sent application said is never silent;
  * an answer that changed on a form that was not submitted is listed (information);
  * a high-stakes answer (canon.py: work authorization, sponsorship, degree, EEO …) that the rules now give and that
    contradicts his facts fails --check, submitted or not.

    python3 scripts/learn/replay.py                    # report: what changed since the baseline (exit 0)
    python3 scripts/learn/replay.py --check            # exit 1 = a submitted answer changed without a reason, or a canon
                                                       #          mismatch appeared; exit 0 = fine; exit 0 + "skip" = no corpus
    python3 scripts/learn/replay.py --reason "why" [--keys k1,k2]   # accept the current changes (all, or these keys) with a reason
    python3 scripts/learn/replay.py --update-baseline  # accept everything as it is now (first run, or after reasons)

Data (the data home): data/runner/replay/baseline.json · reasons.jsonl · last.md (the latest report).
The pre-commit hook runs --check when answer_rules.js, rules_bridge.js or config/{profile,canonical}.json are staged.
"""
import argparse, glob, hashlib, json, os, subprocess, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RUNNER = os.path.join(ROOT, 'skills', 'auto-apply', 'runner')
sys.path.insert(0, os.path.join(ROOT, 'config')); sys.path.insert(0, RUNNER)
import paths as jpaths  # noqa: E402
import canon  # noqa: E402

RULES = os.path.join(ROOT, 'skills', 'auto-apply', 'scripts', 'answer_rules.js')
NO_ANSWER_TYPES = {'file'}


# ----------------------------------------------------------------------------- pure helpers (tested)
def fkey(run_id, question):
    """Pure. The stable id of one field of one run."""
    return hashlib.sha1(f'{run_id}|{question}'.encode('utf-8')).hexdigest()[:16]


def norm_value(v):
    """Pure. An answer value as one comparable string ('' for none; lists joined with ' | ')."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'Yes' if v else 'No'
    if isinstance(v, (list, tuple)):
        return ' | '.join(norm_value(x) for x in v)
    return ' '.join(str(v).split())


def answer_of(a):
    """Pure. answerFor result → {'status', 'value', 'rule'}; anything not 'ok' has value ''."""
    a = a or {}
    st = a.get('status') or 'unknown'
    return {'status': st, 'value': norm_value(a.get('value')) if st == 'ok' else '', 'rule': a.get('rule') or ''}


def diff(baseline, current):
    """Pure. Keys whose answer (status or value) differs from the baseline; a key new to the baseline is not a change."""
    out = []
    for k, now in current.items():
        old = baseline.get(k)
        if old is not None and (old.get('status'), old.get('value')) != (now.get('status'), now.get('value')):
            out.append(k)
    return sorted(out)


def needs_reason(changed, meta, reasons, current):
    """Pure. Changed keys on submitted forms with no reason recorded for exactly the current answer."""
    out = []
    for k in changed:
        if not meta.get(k, {}).get('submitted'):
            continue
        r = reasons.get(k)
        if not r or (r.get('status'), r.get('value')) != (current[k].get('status'), current[k].get('value')):
            out.append(k)
    return out


def canon_problems(current, meta, known=None):
    """Pure-ish (canon.audit). Keys whose CURRENT rule answer is a high-stakes value that contradicts the facts — minus the
    ones accepted as known (`known` = {key: reason line with kind 'canon'} for exactly the current value)."""
    bad = []
    for k, a in current.items():
        if a.get('status') != 'ok':
            continue
        kn = (known or {}).get(k)
        if kn and kn.get('kind') == 'canon' and kn.get('value') == a.get('value'):
            continue
        m = meta.get(k) or {}
        hard = canon.audit([{'label': m.get('question', ''), 'value': a.get('value'), 'type': m.get('type', ''),
                             'required': True}], m.get('tenant'))
        if hard:
            bad.append((k, hard[0]['key'], hard[0]['reason']))
    return bad


# ----------------------------------------------------------------------------- corpus
def submitted_runs(results_path):
    """{folder: set(at)} for results lines with status submitted (a legacy run counts when its folder was submitted)."""
    out = {}
    try:
        for line in open(results_path, encoding='utf-8'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get('status') == 'submitted' and d.get('folder'):
                out.setdefault(d['folder'], set()).add(d.get('at'))
    except OSError:
        pass
    return out


def company_of(folder):
    for n in ('job.json', 'wd_job.json', 'plan.json'):
        p = jpaths.apps(folder, n)
        try:
            c = json.load(open(p, encoding='utf-8')).get('company')
            if c:
                return c
        except (OSError, ValueError):
            pass
    return ''


def load_corpus(fields_dir, results_path):
    """(forms, meta): forms = [{id, company, fields:[{key,label,type,options}]}]; meta = {key: {...field line, submitted}}.
    One entry per (run, question) — the last line wins."""
    subs = submitted_runs(results_path)
    meta = {}
    for p in sorted(glob.glob(os.path.join(fields_dir, '*.jsonl'))):
        for line in open(p, encoding='utf-8'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            q = d.get('question') or ''
            if not q or str(d.get('type') or '').lower() in NO_ANSWER_TYPES:
                continue
            k = fkey(d.get('run_id', ''), q)
            folder, at = d.get('folder') or '', d.get('at')
            sub = folder in subs and (str(d.get('run_id', '')).endswith('@legacy') or at in subs[folder])
            meta[k] = dict(d, submitted=bool(sub))
    forms = {}
    for k, d in meta.items():
        f = forms.setdefault(d.get('run_id', ''), {'id': d.get('run_id', ''), 'company': None, 'folder': d.get('folder'), 'fields': []})
        f['fields'].append({'key': k, 'label': d['question'], 'type': d.get('type') or 'text', 'options': d.get('options') or []})
    for f in forms.values():
        f['company'] = company_of(f['folder']) if f['folder'] else ''
        f.pop('folder', None)
    return list(forms.values()), meta


def answer_all(forms, rules=RULES):
    """Run the rules on every form in one node process → {key: {'status','value','rule'}}."""
    r = subprocess.run(['node', os.path.join(HERE, 'replay_bridge.js'), rules], input=json.dumps({'forms': forms}),
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise SystemExit(f'replay: node failed: {(r.stderr or r.stdout)[:400]}')
    raw = json.loads(r.stdout or '{}')
    out = {}
    for f in forms:
        got = raw.get(f['id']) or {}
        for fld in f['fields']:
            out[fld['key']] = answer_of(got.get(fld['key']))
    return out


# ----------------------------------------------------------------------------- main
def load_reasons(p):
    out = {}
    try:
        for line in open(p, encoding='utf-8'):
            try:
                d = json.loads(line)
                out[d['key']] = d
            except (ValueError, KeyError):
                continue
    except OSError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true'); ap.add_argument('--update-baseline', action='store_true')
    ap.add_argument('--reason'); ap.add_argument('--keys'); ap.add_argument('--rules', default=RULES)
    ap.add_argument('--accept-canon', action='store_true', help='with --reason [--keys]: accept current canon mismatches as known (an open backlog row)')
    ap.add_argument('--data', help='runner data dir (default: the data home data/runner)')
    a = ap.parse_args()
    data = a.data or os.environ.get('CX_DATA') or jpaths.data('runner')
    fdir, rdir = os.path.join(data, 'fields'), os.path.join(data, 'replay')
    if not glob.glob(os.path.join(fdir, '*.jsonl')):
        print('replay: skip — no fields corpus (data/runner/fields/*.jsonl) in this data home'); return 0
    os.makedirs(rdir, exist_ok=True)
    bp, rp = os.path.join(rdir, 'baseline.json'), os.path.join(rdir, 'reasons.jsonl')
    forms, meta = load_corpus(fdir, os.path.join(data, 'results.jsonl'))
    current = answer_all(forms, a.rules)
    baseline = json.load(open(bp, encoding='utf-8')) if os.path.exists(bp) else {}
    if not baseline or a.update_baseline:
        json.dump(current, open(bp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0, sort_keys=True)
        print(f'replay: baseline {"written" if not baseline else "updated"} — {len(current)} answers on {len(forms)} forms')
        if not a.check:
            return 0
        baseline = current
    reasons = load_reasons(rp)
    changed = diff(baseline, current)
    if a.reason:
        pick = set((a.keys or '').split(',')) - {''} or set(changed)
        with open(rp, 'a', encoding='utf-8') as o:
            for k in sorted(pick & set(changed)):
                o.write(json.dumps({'key': k, 'status': current[k]['status'], 'value': current[k]['value'], 'reason': a.reason,
                                    'at': datetime.now().astimezone().isoformat(timespec='seconds'),
                                    'question': meta[k]['question'][:160], 'folder': meta[k].get('folder')}, ensure_ascii=False) + '\n')
        reasons = load_reasons(rp)
        print(f'replay: reason recorded for {len(pick & set(changed))} change(s)')
    if a.accept_canon and a.reason:
        pick = set((a.keys or '').split(',')) - {''} or {k for k, _, _ in canon_problems(current, meta, reasons)}
        with open(rp, 'a', encoding='utf-8') as o:
            for k in sorted(pick):
                o.write(json.dumps({'key': k, 'kind': 'canon', 'status': current[k]['status'], 'value': current[k]['value'],
                                    'reason': a.reason, 'at': datetime.now().astimezone().isoformat(timespec='seconds'),
                                    'question': meta[k]['question'][:160], 'folder': meta[k].get('folder')}, ensure_ascii=False) + '\n')
        reasons = load_reasons(rp)
        print(f'replay: {len(pick)} canon mismatch(es) accepted as known')
    missing = needs_reason(changed, meta, reasons, current)        # any recorded decision for exactly this answer counts
    cbad = canon_problems(current, meta, reasons)
    n_sub = sum(1 for k in changed if meta[k].get('submitted'))
    lines = [f'# Form replay — {datetime.now().astimezone().isoformat(timespec="seconds")}', '',
             f'{len(forms)} forms · {len(current)} answers · changed since baseline: {len(changed)} '
             f'(on submitted forms: {n_sub}, without a reason: {len(missing)}) · canon mismatches in the rule answers: {len(cbad)}', '']
    def row(k):
        m, b, c = meta[k], baseline.get(k, {}), current[k]
        return (f"- {'**SUBMITTED** ' if m.get('submitted') else ''}{m.get('folder')} · {m['question'][:90]!r}: "
                f"{b.get('status')}:{b.get('value')!r} → {c['status']}:{c['value']!r} ({c.get('rule')}) [{k}]")
    if missing:
        lines += ['## Submitted answers changed without a reason', ''] + [row(k) for k in missing] + ['']
    if cbad:
        lines += ['## Rule answers that contradict his facts (canon)', ''] + \
                 [f"- {meta[k].get('folder')} · {meta[k]['question'][:90]!r} = {current[k]['value']!r} — {key}: {why} [{k}]" for k, key, why in cbad] + ['']
    rest = [k for k in changed if k not in missing]
    if rest:
        lines += ['## Other changes', ''] + [row(k) for k in rest[:300]] + ([f'- … {len(rest) - 300} more'] if len(rest) > 300 else []) + ['']
    open(os.path.join(rdir, 'last.md'), 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines[:3]) if not (missing or cbad) else '\n'.join(lines[:60]))
    print(f'replay: report {os.path.join(rdir, "last.md")}')
    if a.check and (missing or cbad):
        print('replay: FAIL — record a reason (--reason "…") for each submitted change, fix the rule, or --update-baseline after review')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
