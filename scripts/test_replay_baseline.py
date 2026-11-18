#!/usr/bin/env python3
"""Harness for JSA-351 (rule 13): the replay baseline grows by audit, reasons must cite a source, a saved answer (qa_add)
stamps only the questions it changed.

1. DeepSeek cases from test_cases/replay_baseline_spec.md run through the real `replay.py` (and qa_add's own replay
   call, `qa_add.replay_args`) with a fake answer-rules module, so only the replay logic is under test; Claude's verdicts
   in test_cases/replay_baseline_verdicts.json.
2. A real example from the data home (the 2026-11-16 baseline review: one qa_add stamped all 424 pending changes): the
   real corpus and baseline, the last qa entry of the real profile removed and added back, one unrelated submitted answer
   made pending — the entry's reason must reach only the keys its answer changed, never the pending one. Skipped when
   the test home has no fields corpus (an open-source checkout)."""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'learn')); sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import replay as RP  # noqa: E402
import qa_add as QA  # noqa: E402
import paths as jpaths  # noqa: E402

REPLAY = os.path.join(HERE, 'learn', 'replay.py')
# the answer map comes from JSA_PROFILE when that file is a fake one ({"fake": …}: the rules "before" the qa entry), else
# from REPLAY_FAKE_MAP ("now"); "Date signed" answers through the today's-date rule
FAKE = """const fs = require('fs');
let m = JSON.parse(fs.readFileSync(process.env.REPLAY_FAKE_MAP, 'utf8'));
try { const p = JSON.parse(fs.readFileSync(process.env.JSA_PROFILE, 'utf8')); if (p.fake) m = p.fake; } catch (e) {}
module.exports = { answerFor: f => { const a = m[f.l]; const rule = /date signed/i.test(f.l) ? 'signature_date' : 'qa:1';
  return a ? Object.assign({ label: f.l }, a, { rule }) : { status: 'unknown', label: f.l, rule }; } };
"""


def nv(a):
    a = a or {}
    return {'status': a.get('status') or 'ok', 'value': RP.norm_value(a.get('value')) if (a.get('status') or 'ok') == 'ok' else ''}


def run(c):
    d = tempfile.mkdtemp(prefix='replay_b_')
    try:
        os.makedirs(os.path.join(d, 'fields')); os.makedirs(os.path.join(d, 'replay')); os.makedirs(os.path.join(d, 'audit'))
        folder_of = {q['question']: q['folder'] for q in c.get('corpus') or []}
        key = lambda q: RP.fkey(f"{folder_of.get(q, 'x')}@legacy", q)
        rule = lambda q: 'signature_date' if re.search(r'date signed', q, re.I) else 'qa:1'
        with open(os.path.join(d, 'fields', 'a.jsonl'), 'w') as o:
            for q in c.get('corpus') or []:
                o.write(json.dumps({'run_id': f"{q['folder']}@legacy", 'folder': q['folder'], 'question': q['question'], 'type': 'text',
                                    'options': [], 'page': q.get('filled') or '', 'at': '2026-11-01T00:00:00'}) + '\n')
        with open(os.path.join(d, 'results.jsonl'), 'w') as o:
            for f in c.get('submitted') or []:
                o.write(json.dumps({'folder': f, 'status': 'submitted', 'at': '2026-11-01T00:00:00'}) + '\n')
        with open(os.path.join(d, 'audit', 'items.jsonl'), 'w') as o:
            for x in c.get('audit') or []:
                o.write(json.dumps({'folder': x['folder'], 'question': 'q', 'key': 'abc123def456', 'check': x.get('check'), 'judged': x.get('judged')}) + '\n')
        bl = {key(q): dict(nv(v), rule=rule(q)) for q, v in (c.get('baseline') or {}).items()}
        if not bl:          # an empty baseline would be written from the current answers: hold one unrelated entry instead
            bl = {'0000000000000000': {'status': 'ok', 'value': 'x', 'rule': ''}}
        json.dump(bl, open(os.path.join(d, 'replay', 'baseline.json'), 'w'))
        now = c.get('now') or {}
        with open(os.path.join(d, 'replay', 'reasons.jsonl'), 'w') as o:
            for r in c.get('reasons') or []:
                cur = nv(now.get(r['question']))
                st = cur['status'] if cur['value'] == RP.norm_value(r.get('value')) else 'ok'
                o.write(json.dumps({'key': key(r['question']), 'status': st, 'value': RP.norm_value(r.get('value')), 'reason': r.get('text') or ''}) + '\n')
        mp = os.path.join(d, 'now.json'); json.dump(now, open(mp, 'w'))
        rules = os.path.join(d, 'fake_rules.js'); open(rules, 'w').write(FAKE)
        env = dict(os.environ, REPLAY_FAKE_MAP=mp); env.pop('JSA_PROFILE', None)
        base = [sys.executable, REPLAY, '--data', d, '--rules', rules]
        got = {}
        if c.get('record_reason'):
            got['record_exit'] = subprocess.run(base + ['--reason', c['record_reason']], capture_output=True, text=True, env=env, timeout=120).returncode
        if c.get('qa'):
            old = os.path.join(d, 'old_profile.json'); json.dump({'fake': c['qa'].get('before') or {}}, open(old, 'w'))
            text = c['qa'].get('reason') or 'qa#1 (2026-11-16): Joey 2026-11-16 (test)'
            args = QA.replay_args({'q': 'x'}, 1, old)
            args[args.index('--reason') + 1] = text
            subprocess.run(base + args, capture_output=True, text=True, env=env, timeout=120)
            inv = {key(q): q for q in folder_of}
            got['reasoned'] = sorted(inv.get(json.loads(l)['key'], '?') for l in open(os.path.join(d, 'replay', 'reasons.jsonl'))
                                     if json.loads(l).get('reason') == text)
        p = subprocess.run(base + ['--check'], capture_output=True, text=True, env=env, timeout=120)
        out = p.stdout + p.stderr
        got['exit'] = p.returncode
        m = re.search(r'merged after audit now: (\d+)', out); got['merged'] = int(m.group(1)) if m else None
        m = re.search(r'new, not in baseline: (\d+)', out); got['new'] = int(m.group(1)) if m else None
        return got, out
    finally:
        shutil.rmtree(d, ignore_errors=True)


def deepseek_cases():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'replay_baseline_cases.json'), encoding='utf-8'))
    vp = os.path.join(HERE, 'test_cases', 'replay_baseline_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got, out = run(c)
        want = {'exit': c.get('expect_exit'), 'merged': c.get('expect_merged', 0), 'new': c.get('expect_new', 0)}
        if c.get('expect_record_exit') is not None:
            want['record_exit'] = c['expect_record_exit']
        if c.get('qa'):
            want['reasoned'] = sorted(c.get('expect_reasoned') or [])
        diff = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        if diff and c['name'] not in verdicts:
            bad += 1; print('DISAGREE', c['name'], diff, '|', out.strip().splitlines()[-1][:200] if out.strip() else '')
    print(f'{len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
    return bad


def pure_checks():
    bad = 0
    def ok(cond, what):
        nonlocal bad
        if not cond:
            bad += 1; print('FAIL', what)
    ok(RP.cites_source('qa_add 2026-11-16: Joey 2026-11-16 (prefetch) — Languages Spoken'), 'a dated Joey decision cites')
    ok(RP.cites_source('audit:77a76038a3c4 says right'), 'an audit key cites')
    ok(RP.cites_source(QA.qa_reason({'q': 'Languages Spoken', 'added': '2026-11-16', 'source': 'user'}, 7)), 'qa_reason cites qa#N')
    ok(not RP.cites_source('signature_date is the day the form is filled; a replay on a later day (11-12) gives that day'), 'no source')
    ok(not RP.cites_source('JSA-325 (open): current-employer rule'), 'a row id is no source for a change')
    ok(RP.cites_source('JSA-325 (open): current-employer rule', 'canon'), 'a row id is the source of a known canon issue')
    a = {'status': 'ok', 'value': '11/12/2026', 'rule': 'signature_date'}; b = dict(a, value='11/16/2026')
    ok(RP.same(a, b) and not RP.same(a, dict(b, status='unknown')), "today's date: status only")
    ok(RP.changed_between({'k': {'status': 'ok', 'value': 'A'}}, {'k': {'status': 'ok', 'value': 'B'}, 'j': {'status': 'ok', 'value': 'C'}}, ['k', 'j'])
       == ['j', 'k'], 'changed_between: a key with no before counts as changed')
    args = QA.replay_args({'q': 'Q', 'added': '2026-11-16', 'source': 'Joey 2026-11-16'}, 3, '/tmp/p.json')
    ok('--changed-from' in args and '--keys' not in args and args[args.index('--changed-from') + 1] == '/tmp/p.json', 'qa_add asks for its own keys')
    meta = {'a1': {'run_id': 'A', 'folder': 'A', 'submitted': True}, 'a2': {'run_id': 'A', 'folder': 'A', 'submitted': True},
            'b1': {'run_id': 'B', 'folder': 'B', 'submitted': True}, 'c1': {'run_id': 'C', 'folder': 'C', 'submitted': True}}
    cur = {k: {'status': 'ok', 'value': 'v', 'rule': 'r'} for k in meta}
    base0 = {'c1': {'status': 'ok', 'value': 'old', 'rule': 'r'}}
    nb, mg = RP.merge_audited(base0, cur, meta, {'A', 'C'})
    ok(mg == ['A'] and set(nb) == {'a1', 'a2', 'c1'} and nb['c1']['value'] == 'old', 'merge: only the audited form outside the baseline')
    ok(RP.merge_audited(nb, cur, meta, {'A', 'C'})[1] == [], 'merge: a second run merges nothing')
    print(f'pure checks: {bad} failed')
    return bad


def real_example():
    """The 2026-11-16 stamp (424 pending changes got one qa_add reason) on the real corpus: only the entry's own keys."""
    data = jpaths.data('runner')
    prof_p = os.environ.get('JSA_PROFILE') or jpaths.config('profile.json')
    if not (os.path.isdir(os.path.join(data, 'fields')) and os.path.exists(os.path.join(data, 'replay', 'baseline.json'))
            and os.path.exists(prof_p)):
        print('real example: skip — no fields corpus / baseline in this test home'); return 0
    prof = json.load(open(prof_p, encoding='utf-8'))
    qa = prof.get('qa') or []
    if not qa:
        print('real example: skip — no qa entries'); return 0
    d = tempfile.mkdtemp(prefix='replay_real_')
    try:
        for n in ('fields', 'results.jsonl'):
            s = os.path.join(data, n)
            (shutil.copytree if os.path.isdir(s) else shutil.copy)(s, os.path.join(d, n))
        os.makedirs(os.path.join(d, 'replay'))
        forms, meta = RP.load_corpus(os.path.join(d, 'fields'), os.path.join(d, 'results.jsonl'))
        old_p, new_p = os.path.join(d, 'old.json'), os.path.join(d, 'new.json')
        # the entry whose answer reaches the most submitted forms (the 11-16 "Languages Spoken" kind), from the last 8
        json.dump(prof, open(new_p, 'w'))
        after = RP.answer_all(forms, profile=new_p)
        best = None
        for i in range(len(qa) - 1, max(-1, len(qa) - 9), -1):
            json.dump(dict(prof, qa=qa[:i] + qa[i + 1:]), open(old_p, 'w'))
            ch = [k for k in RP.changed_between(RP.answer_all(forms, profile=old_p), after) if meta[k].get('submitted')]
            if ch and (best is None or len(ch) > len(best[1])):
                best = (i, ch)
        if not best:
            print('real example: skip — none of the last 8 qa entries changes a submitted answer'); return 0
        i, own = best
        json.dump(dict(prof, qa=qa[:i] + qa[i + 1:]), open(old_p, 'w'))
        before = RP.answer_all(forms, profile=old_p)
        base = dict(before)                                     # the baseline = the answers before the entry …
        other = next(k for k in sorted(before) if meta[k].get('submitted') and k not in own and before[k].get('status') == 'ok')
        base[other] = dict(before[other], value=before[other]['value'] + ' (old)')   # … plus one unrelated pending change
        json.dump(base, open(os.path.join(d, 'replay', 'baseline.json'), 'w'))
        env = dict(os.environ, JSA_PROFILE=new_p)
        keep = os.environ.get('JSA_PROFILE'); os.environ['JSA_PROFILE'] = new_p
        try:
            QA.replay_after(qa[i], i + 1, old_p, extra=['--data', d])       # qa_add's own call, as after a save
        finally:
            os.environ.pop('JSA_PROFILE') if keep is None else os.environ.__setitem__('JSA_PROFILE', keep)
        got = {json.loads(l)['key'] for l in open(os.path.join(d, 'replay', 'reasons.jsonl'))}
        chk = subprocess.run([sys.executable, REPLAY, '--data', d, '--check'], capture_output=True, text=True, env=env, timeout=900)
        bad = 0
        if got != set(own):
            bad += 1; print(f'FAIL real example: qa#{i + 1} reasoned {len(got)} keys, its own {len(own)}; extra {sorted(got - set(own))[:5]}')
        if other in got:
            bad += 1; print('FAIL real example: the unrelated pending change got the qa reason')
        if chk.returncode != 1 or other not in chk.stdout:
            bad += 1; print('FAIL real example: --check does not stop on the unrelated pending change', chk.stdout[-300:])
        print(f"real example: qa#{i + 1} {qa[i].get('q', '')[:50]!r} changes {len(own)} submitted answers; reasoned {len(got)}; "
              f"unrelated pending change still fails --check: {chk.returncode == 1} — {bad} failed")
        return bad
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(1 if (pure_checks() + deepseek_cases() + real_example()) else 0)
