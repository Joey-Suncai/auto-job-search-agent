#!/usr/bin/env python3
"""Harness for scripts/learn/replay.py (JSA-188, rule 13): DeepSeek cases from test_cases/replay_spec.md run through the
real `replay.py --check` with a fake answer-rules module (so only the replay logic is under test, not the rules);
Claude's verdicts in test_cases/replay_verdicts.json."""
import json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'learn'))
import replay as RP  # noqa: E402

FAKE = """const m = JSON.parse(require('fs').readFileSync(process.env.REPLAY_FAKE_MAP, 'utf8'));
module.exports = { answerFor: f => { const a = m[f.l]; return a ? Object.assign({ label: f.l, rule: 'qa:1' }, a, a.rule ? { rule: 'qa:1', orig: a.rule } : {}) : { status: 'unknown', label: f.l }; } };
"""


def run(c):
    d = tempfile.mkdtemp(prefix='replay_t_')
    os.makedirs(os.path.join(d, 'fields'))
    with open(os.path.join(d, 'fields', 'a.jsonl'), 'w') as o:
        for q in c.get('corpus') or []:
            o.write(json.dumps({'run_id': f"{q['folder']}@legacy", 'folder': q['folder'], 'question': q['question'],
                                'type': q.get('type') or 'radio', 'options': [], 'at': '2026-11-01T00:00:00'}) + '\n')
    if not c.get('corpus'):
        os.remove(os.path.join(d, 'fields', 'a.jsonl'))
    with open(os.path.join(d, 'results.jsonl'), 'w') as o:
        for f in c.get('submitted') or []:
            o.write(json.dumps({'folder': f, 'status': 'submitted', 'at': '2026-11-01T00:00:00'}) + '\n')
    folder_of = {q['question']: q['folder'] for q in c.get('corpus') or []}
    key = lambda question: RP.fkey(f"{folder_of.get(question, 'x')}@legacy", question)
    os.makedirs(os.path.join(d, 'replay'))
    if c.get('baseline') is not None:
        json.dump({key(q): {'status': v.get('status'), 'value': v.get('value') if v.get('status') == 'ok' else '', 'rule': ''}
                   for q, v in c['baseline'].items()}, open(os.path.join(d, 'replay', 'baseline.json'), 'w'))
    with open(os.path.join(d, 'replay', 'reasons.jsonl'), 'w') as o:
        for r in c.get('reasons') or []:
            nw = (c.get('now') or {}).get(r['question']) or {}
            st = nw.get('status', 'ok') if RP.norm_value(nw.get('value') if nw.get('status') == 'ok' else '') == RP.norm_value(r.get('value')) else 'ok'
            o.write(json.dumps({'key': key(r['question']), 'status': st, 'value': r.get('value'), 'reason': 't',
                                **({'kind': 'canon'} if r.get('kind') == 'known_issue' else {})}) + '\n')
    mp = os.path.join(d, 'fake_map.json'); json.dump(c.get('now') or {}, open(mp, 'w'))
    rules = os.path.join(d, 'fake_rules.js'); open(rules, 'w').write(FAKE)
    p = subprocess.run([sys.executable, os.path.join(HERE, 'learn', 'replay.py'), '--data', d, '--rules', rules, '--check'],
                       capture_output=True, text=True, env=dict(os.environ, REPLAY_FAKE_MAP=mp), timeout=120)
    m = re.search(r'changed since baseline: (\d+)', p.stdout)
    return p.returncode, int(m.group(1)) if m else 0, p.stdout + p.stderr


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'replay_cases.json'), encoding='utf-8'))
    vp = os.path.join(HERE, 'test_cases', 'replay_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        code, n, out = run(c)
        diff = {}
        if code != c.get('expect_exit'):
            diff['exit'] = (code, c.get('expect_exit'))
        if 'expect_changed' in c and n != c['expect_changed']:
            diff['changed'] = (n, c['expect_changed'])
        if diff and c['name'] not in verdicts:
            bad += 1; print('DISAGREE', c['name'], diff, '|', out.strip().splitlines()[-1][:160] if out.strip() else '')
    print(f'{len(cases)} DeepSeek cases · disagreements without a verdict: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
