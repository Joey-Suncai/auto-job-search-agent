#!/usr/bin/env python3
"""After-submit review, steps 7 of the apply self-optimization (JSA-192). The independent check itself is scripts/audit_sample.py (DeepSeek
checks every answer of a submitted form against Joey's facts, Claude / Joey judge the doubts, a confirmed wrong answer goes to
wrong_answers.jsonl); the daily gate now runs it for every newly submitted form (run_daily.post_submit). This script adds, from that
audit and the fields corpus:

  * QA PROPOSALS — a DeepSeek-triage answer (source ds_answers.json) that the audit verified right on >= 3 different forms, never wrong,
    for a question no qa entry / rule answers yet, becomes a proposal (data/runner/audit/qa_proposals.jsonl + .md). It only PROPOSES:
    nothing is written to config/profile.json — Joey confirms, then `qa_add.py` (the command is printed in the .md).
  * OVERDUE DOUBTS — audit items still waiting for a judgment 2+ days after the audit (the 48-hour promise to Joey).

    python3 scripts/learn/post_submit.py --run          # writes the two files, prints one line
Pure functions (tested: scripts/test_jsa192_post_submit.py): norm, proposals, overdue."""
import argparse, glob, json, os, re, shlex, sys
from datetime import date, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', str(s or '').lower()).strip()


def _verdict(it):
    """'right' | 'wrong' | 'pending' for one audit item."""
    j, c = it.get('judged'), it.get('check')
    if j in ('right', 'wrong'):
        return j
    if j in (None, ''):
        return c if c in ('right', 'wrong') else 'pending'
    return 'pending'


def proposals(lines, items, covered=(), min_n=3):
    """Pure (tested). See the spec in scripts/test_cases/jsa192_post_submit_spec.md."""
    verd = {}
    for it in items:
        v = _verdict(it)
        verd[(it.get('folder'), norm(it.get('question')))] = v
    cov = {norm(c) for c in covered}
    groups = {}
    for l in lines:
        if l.get('source') != 'ds_answers.json' or l.get('ok') is False:
            continue
        if str(l.get('page') or '').strip().lower() != str(l.get('planned') or '').strip().lower():
            continue
        k = (norm(l.get('question')), norm(l.get('planned')))
        g = groups.setdefault(k, {'first': l, 'folders': {}})
        g['folders'].setdefault(l.get('folder'), l)
    out = []
    for (q, a), g in groups.items():
        if q in cov:
            continue
        if any(verd.get((f, q)) == 'wrong' for f in g['folders']) or any(
                _verdict(it) == 'wrong' and norm(it.get('question')) == q and norm(it.get('answer')) == a for it in items):
            continue
        good = sorted(f for f in g['folders'] if verd.get((f, q)) == 'right')
        if len({_company(g['folders'][f]) for f in good}) < min_n:        # three roles at one company are one witness
            continue
        opts = next((x.get('options') for x in g['folders'].values() if x.get('options')), [])
        out.append({'question': g['first'].get('question'), 'answer': g['first'].get('planned'), 'options': opts or [], 'folders': good, 'n': len(good)})
    return sorted(out, key=lambda p: (-p['n'], str(p['question'])))


def _company(line):
    """The hiring company of a field line: its tenant, else the first word after the date in the folder name."""
    t = str(line.get('tenant') or '').strip().lower()
    if t:
        return t
    f = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', str(line.get('folder') or ''))
    return f.split('_')[0].lower()


def risky(question):
    """Pure. A question class never proposed as a saved answer: work authorization / record / EEO / contact (scripts/field_class.py)."""
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    from field_class import field_class
    cls, grp = field_class(question)
    return cls == 'critical' or grp in ('eeo', 'contact', 'work_auth', 'record')


def overdue(items, today, days=2):
    """Pure (tested). Pending audit items whose audited date is >= `days` days before today → [{folder, question}], oldest first."""
    t = datetime.strptime(str(today)[:10], '%Y-%m-%d')
    out = []
    for it in items:
        if _verdict(it) != 'pending' or not it.get('audited'):
            continue
        try:
            age = (t - datetime.strptime(str(it['audited'])[:10], '%Y-%m-%d')).days
        except ValueError:
            continue
        if age >= days:
            out.append((str(it['audited'])[:10], it.get('folder') or '', it.get('question') or ''))
    return [{'folder': f, 'question': q} for _, f, q in sorted(out)]


def run(today=None):
    import paths as jp
    today = today or date.today().isoformat()
    d = jp.data('runner', 'audit')
    jl = lambda p: [x for l in (open(p, encoding='utf-8') if os.path.exists(p) else []) for x in [_load(l)] if x]
    items = jl(os.path.join(d, 'items.jsonl'))
    lines = [x for p in glob.glob(jp.data('runner', 'fields', '*.jsonl')) for x in jl(p)]
    ds = [l for l in lines if l.get('source') == 'ds_answers.json']
    shown = {}                                                          # normalised question → (original text, option lists seen)
    for l in ds:
        e = shown.setdefault(norm(l.get('question')), (l.get('question'), []))
        if l.get('options') and l['options'] not in e[1]:
            e[1].append(l['options'])
    covered = _covered(shown)
    props = [p for p in proposals(lines, items, covered) if not risky(p['question'])]
    od = overdue(items, today)
    os.makedirs(d, exist_ok=True)
    pj = os.path.join(d, 'qa_proposals.jsonl')
    prev = {norm(x.get('question')) + '|' + norm(x.get('answer')): x for x in jl(pj)}           # state carries over (declined / added stay)
    new = []
    with open(pj, 'w', encoding='utf-8') as f:
        for p in props:
            k = norm(p['question']) + '|' + norm(p['answer'])
            old = prev.get(k)
            rec = dict(p, status=(old or {}).get('status', 'open'), first_seen=(old or {}).get('first_seen', today))
            if not old:
                new.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        for k, old in prev.items():                                     # a decided proposal stays on record even when it drops out
            if old.get('status') in ('declined', 'added') and k not in {norm(p['question']) + '|' + norm(p['answer']) for p in props}:
                f.write(json.dumps(old, ensure_ascii=False) + '\n')
    open_props = [json.loads(l) for l in open(pj, encoding='utf-8') if json.loads(l).get('status') == 'open']
    md = [f'# After-submit review — {today} (JSA-192)', '',
          f'{len(open_props)} open qa proposal(s) (a DeepSeek-triage answer the audit verified right on >= 3 different companies; nothing is saved until Joey confirms; '
          f'set "status": "declined" in qa_proposals.jsonl to stop it coming back) · {len(od)} audit doubt(s) waiting > 2 days', '']
    for p in open_props:
        args = ['--q', p['question'], '--text', p['answer'], '--source', f'Joey {today} (proposal, JSA-192)']
        for lst in ([p['options']] if p['options'] else []):
            args += ['--options-json', json.dumps(lst, ensure_ascii=False)]
        md.append(f"- **{p['question'][:160]}** → `{p['answer']}` ({p['n']} forms)\n  `python3 skills/auto-apply/scripts/qa_add.py {' '.join(shlex.quote(a) for a in args)}`")
    if od:
        md += ['', '## Doubts waiting for a judgment (`audit_sample.py --judge <key> right|wrong`)', ''] + [f"- {x['folder']} · {x['question'][:140]}" for x in od]
    open(os.path.join(d, 'qa_proposals.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print(f'post-submit review: {len(open_props)} open qa proposal(s) ({len(new)} new) · {len(od)} doubt(s) overdue → {os.path.join(d, "qa_proposals.md")}')
    return 0


def _load(l):
    try:
        return json.loads(l)
    except ValueError:
        return None


def _covered(shown):
    """Impure: the normalised questions the rules / qa table already answer — asked as the forms showed them (original text, every option
    list seen, else a text box). A check that cannot run covers nothing is NOT assumed: the failure is printed and the question counts as covered
    (a proposal is only ever made when the rules were really asked)."""
    sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'scripts'))
    import paths as jp
    import qa_add
    prof = jp.config('profile.json')
    out = []
    for q, (orig, lists) in shown.items():
        try:
            if (qa_add.check_shapes(orig, lists or [[]], prof) or {}).get('status') == 'ok':
                out.append(q)
        except Exception as e:
            print(f'post-submit review: rules check failed for {orig[:50]!r} ({type(e).__name__}) — not proposed'); out.append(q)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    sys.exit(run() if a.run else ap.print_help())
