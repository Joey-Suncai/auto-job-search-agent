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
    python3 scripts/learn/replay.py --reason "Joey 2026-11-16 …" [--keys k1,k2]   # accept the current changes (all, or these keys)
    python3 scripts/learn/replay.py --update-baseline  # accept everything as it is now (first run, or after reasons)
    python3 scripts/learn/replay.py --reason "qa#N …" --changed-from OLD_PROFILE   # only the keys whose answer differs
                                                       #   between the rules on OLD_PROFILE and now (qa_add, JSA-351)

The baseline grows by itself (JSA-351, ADR-0012): a SUBMITTED form with no baseline entries whose folder has a judged item
in the independent audit (data/runner/audit/items.jsonl: `check` or `judged`) is merged into the baseline — only that form.
A submitted form still outside the baseline is compared with what was filled on it and reported "new, not in baseline".
A reason counts only when it cites its source (cites_source: "Joey|user|decision YYYY-MM-DD", "audit:<key>", "qa#N",
and for a known canon issue its open row "JSA-NNN"); --reason refuses one that does not (exit 2).

Data (the data home): data/runner/replay/baseline.json · reasons.jsonl · last.md (the latest report).
The pre-commit hook runs --check when answer_rules.js, rules_bridge.js or config/{profile,canonical}.json are staged.
"""
import argparse, glob, hashlib, json, os, re, subprocess, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RUNNER = os.path.join(ROOT, 'skills', 'auto-apply', 'runner')
sys.path.insert(0, os.path.join(ROOT, 'config')); sys.path.insert(0, RUNNER)
import paths as jpaths  # noqa: E402
import canon  # noqa: E402

RULES = os.path.join(ROOT, 'skills', 'auto-apply', 'scripts', 'answer_rules.js')
NO_ANSWER_TYPES = {'file'}
TODAY_RULES = {'signature_date'}                 # the answer is the day of the run: only the status is compared (JSA-351)
SOURCE_RES = (re.compile(r'\b(?:joey|user|decision|decided)\b[^\n]{0,40}?\b20\d\d-\d\d-\d\d\b', re.I),
              re.compile(r'\baudit:[0-9a-f]{6,}\b', re.I), re.compile(r'\bqa#\d+\b', re.I))
CANON_SOURCE_RE = re.compile(r'\bJSA-\d+\b')     # a known canon issue cites its open backlog row


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


def same(a, b):
    """Pure. Two answers are the same: status and value — for a today's-date rule (signature date) the status only."""
    a, b = a or {}, b or {}
    if a.get('status') != b.get('status'):
        return False
    if a.get('rule') in TODAY_RULES and b.get('rule') in TODAY_RULES:
        return True
    return a.get('value') == b.get('value')


def diff(baseline, current):
    """Pure. Keys whose answer (status or value) differs from the baseline; a key new to the baseline is not a change."""
    return sorted(k for k, now in current.items() if baseline.get(k) is not None and not same(baseline[k], now))


def cites_source(text, kind=None):
    """Pure. Does a reason cite where it comes from — a dated decision of the user, an audit key, a qa entry number (and
    for a known canon issue, its open backlog row JSA-NNN)? (JSA-351, rule 13)"""
    t = str(text or '')
    return any(r.search(t) for r in SOURCE_RES) or (kind == 'canon' and bool(CANON_SOURCE_RE.search(t)))


def changed_between(before, after, keys=None):
    """Pure. Keys (of `keys`, default all of after) whose answer differs between two replays — what one qa entry changed."""
    return sorted(k for k in (after if keys is None else keys) if k in after and not same(before.get(k), after[k]))


def audited_folders(items_path):
    """Folders with at least one judged item in the independent audit (items.jsonl: a `check` or `judged` value)."""
    out = set()
    try:
        for line in open(items_path, encoding='utf-8'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get('folder') and (d.get('check') or d.get('judged')):
                out.add(d['folder'])
    except OSError:
        pass
    return out


def outside_baseline(meta, baseline):
    """Pure. {run_id: [keys]} of SUBMITTED forms none of whose questions is in the baseline."""
    runs = {}
    for k, m in meta.items():
        if m.get('submitted'):
            runs.setdefault(m.get('run_id', ''), []).append(k)
    return {r: sorted(ks) for r, ks in runs.items() if not any(k in baseline for k in ks)}


def merge_audited(baseline, current, meta, audited):
    """Pure. Merge each submitted form outside the baseline whose folder was audited — that form's keys only, at the
    current answer → (new baseline, [run_ids merged])."""
    out, merged = dict(baseline), []
    for r, ks in sorted(outside_baseline(meta, baseline).items()):
        if meta[ks[0]].get('folder') in audited:
            out.update({k: current[k] for k in ks if k in current})
            merged.append(r)
    return out, merged


def filled_of(m):
    """Pure. The answer that was filled on the form for one corpus line (what the page showed, else what was planned)."""
    return norm_value(m.get('page') if m.get('page') not in (None, '') else m.get('planned'))


def new_form_diffs(keys, current, meta):
    """Pure. Keys of a form outside the baseline whose current rule answer (status ok) differs from what was filled."""
    return [k for k in keys if current.get(k, {}).get('status') == 'ok' and filled_of(meta[k])
            and current[k].get('rule') not in TODAY_RULES and current[k]['value'].lower() != filled_of(meta[k]).lower()]


def needs_reason(changed, meta, reasons, current):
    """Pure. Changed keys on submitted forms with no reason recorded for exactly the current answer."""
    out = []
    for k in changed:
        if not meta.get(k, {}).get('submitted'):
            continue
        r = reasons.get(k)
        if not r or not cites_source(r.get('reason'), r.get('kind')) or \
                (r.get('status'), r.get('value')) != (current[k].get('status'), current[k].get('value')):
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
        if kn and kn.get('kind') == 'canon' and kn.get('value') == a.get('value') and cites_source(kn.get('canon_reason', kn.get('reason')), 'canon'):
            continue
        m = meta.get(k) or {}
        hard = canon.audit([{'label': m.get('question', ''), 'value': a.get('value'), 'type': m.get('type', ''),
                             'required': True, 'options': m.get('options') or []}], m.get('tenant'))   # options: "Other" from a list without his schools (JSA-321)
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


def answer_all(forms, rules=RULES, profile=None):
    """Run the rules on every form in one node process → {key: {'status','value','rule'}}; `profile` = answer with that
    profile.json instead of the data home's (JSA_PROFILE)."""
    env = dict(os.environ, **({'JSA_PROFILE': os.path.abspath(profile)} if profile else {}))
    r = subprocess.run(['node', os.path.join(HERE, 'replay_bridge.js'), rules], input=json.dumps({'forms': forms}),
                       capture_output=True, text=True, timeout=600, env=env)
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
                prev = out.get(d['key'])          # a later plain reason for the same answer keeps its canon acceptance (JSA-293: qa_add's line erased JSA-281's)
                if prev and prev.get('kind') == 'canon' and d.get('kind') != 'canon' and \
                        (prev.get('status'), prev.get('value')) == (d.get('status'), d.get('value')):
                    d = dict(d, kind='canon', canon_reason=prev.get('canon_reason', prev.get('reason')))
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
    ap.add_argument('--changed-from', metavar='PROFILE', help='with --reason: only the keys whose answer differs between the '
                    'rules on this profile.json and now, on submitted forms (qa_add: the answers one new entry changed)')
    a = ap.parse_args()
    if a.reason and not cites_source(a.reason, 'canon' if a.accept_canon else None):
        print('replay: reason NOT recorded — cite its source: "Joey YYYY-MM-DD …" (his decision), "audit:<key>", "qa#N"'
              + (' or the open row "JSA-NNN"' if a.accept_canon else '')); return 2
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
    baseline, merged = merge_audited(baseline, current, meta, audited_folders(os.path.join(data, 'audit', 'items.jsonl')))
    if merged:                                                    # JSA-351: an audited submitted form joins the baseline, only it
        json.dump(baseline, open(bp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0, sort_keys=True)
    reasons = load_reasons(rp)
    changed = diff(baseline, current)
    if a.reason and not (a.accept_canon and not cites_source(a.reason)):   # a row id alone accepts canon issues, not changes
        if a.changed_from:                                        # JSA-351: never stamp the changes this answer did not make
            before = answer_all(forms, a.rules, a.changed_from)
            pick = set(changed_between(before, current, [k for k in changed if meta[k].get('submitted')]))
            if a.keys is not None:
                pick &= set(a.keys.split(','))
        elif a.keys is not None:
            pick = set(a.keys.split(',')) - {''}
        else:
            pick = set(changed)
        with open(rp, 'a', encoding='utf-8') as o:
            for k in sorted(pick & set(changed)):
                o.write(json.dumps({'key': k, 'status': current[k]['status'], 'value': current[k]['value'], 'reason': a.reason,
                                    'at': datetime.now().astimezone().isoformat(timespec='seconds'),
                                    'question': meta[k]['question'][:160], 'folder': meta[k].get('folder')}, ensure_ascii=False) + '\n')
        reasons = load_reasons(rp)
        print(f'replay: reason recorded for {len(pick & set(changed))} change(s)')
    if a.accept_canon and a.reason:
        pick = (set(a.keys.split(',')) - {''}) if a.keys is not None else {k for k, _, _ in canon_problems(current, meta, reasons)}
        pick &= set(current)
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
    new = outside_baseline(meta, baseline)                       # JSA-351: submitted forms the baseline does not hold yet
    new_diff = {r: new_form_diffs(ks, current, meta) for r, ks in new.items()}
    n_subforms = len({m.get('run_id') for m in meta.values() if m.get('submitted')})
    lines = [f'# Form replay — {datetime.now().astimezone().isoformat(timespec="seconds")}', '',
             f'{len(forms)} forms · {len(current)} answers · changed since baseline: {len(changed)} '
             f'(on submitted forms: {n_sub}, without a reason: {len(missing)}) · canon mismatches in the rule answers: {len(cbad)}',
             f'submitted forms: {n_subforms} · in the baseline: {n_subforms - len(new)} (merged after audit now: {len(merged)}) · '
             f'new, not in baseline: {len(new)} (answers that differ from the filled form: {sum(map(len, new_diff.values()))})', '']
    def row(k):
        m, b, c = meta[k], baseline.get(k, {}), current[k]
        return (f"- {'**SUBMITTED** ' if m.get('submitted') else ''}{m.get('folder')} · {m['question'][:90]!r}: "
                f"{b.get('status')}:{b.get('value')!r} → {c['status']}:{c['value']!r} ({c.get('rule')}) [{k}]")
    if missing:
        lines += ['## Submitted answers changed without a reason', ''] + [row(k) for k in missing] + ['']
    if cbad:
        lines += ['## Rule answers that contradict his facts (canon)', ''] + \
                 [f"- {meta[k].get('folder')} · {meta[k]['question'][:90]!r} = {current[k]['value']!r} — {key}: {why} [{k}]" for k, key, why in cbad] + ['']
    if merged:                                                    # what the audit merge accepted where the rules now differ from the form
        by_run = {}
        for k, m in meta.items():
            by_run.setdefault(m.get('run_id'), []).append(k)
        lines += ['## Merged into the baseline after audit (current answers that differ from the filled form are listed)', '']
        for r in merged:
            dd = new_form_diffs(sorted(by_run.get(r, [])), current, meta)
            lines.append(f"- {meta[by_run[r][0]].get('folder')} — {len(by_run[r])} answers, {len(dd)} differ from the filled form")
            lines += [f"  - {meta[k]['question'][:90]!r}: filled {filled_of(meta[k])!r} → baseline {current[k]['value']!r} ({current[k].get('rule')}) [{k}]"
                      for k in dd[:20]]
        lines.append('')
    if new:
        lines += ['## New, not in baseline (submitted, not audited yet — compared with what was filled)', '']
        for r in sorted(new):
            lines.append(f"- {meta[new[r][0]].get('folder')} — {len(new[r])} answers, {len(new_diff[r])} differ from the filled form")
            lines += [f"  - {meta[k]['question'][:90]!r}: filled {filled_of(meta[k])!r} → now {current[k]['value']!r} ({current[k].get('rule')}) [{k}]"
                      for k in new_diff[r][:20]]
        lines.append('')
    rest = [k for k in changed if k not in missing]
    if rest:
        lines += ['## Other changes', ''] + [row(k) for k in rest[:300]] + ([f'- … {len(rest) - 300} more'] if len(rest) > 300 else []) + ['']
    open(os.path.join(rdir, 'last.md'), 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines[:4]) if not (missing or cbad) else '\n'.join(lines[:60]))
    print(f'replay: report {os.path.join(rdir, "last.md")}')
    if a.check and (missing or cbad):
        print('replay: FAIL — record a reason that cites its source (--reason "Joey YYYY-MM-DD … / audit:<key> / qa#N" --keys …) '
              'for each submitted change, fix the rule, or --update-baseline after review')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
