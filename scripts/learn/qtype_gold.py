#!/usr/bin/env python3
"""JSA-361: build the gold set for the question-type measurement (scripts/test_cases/qtype_gold.jsonl).

Reads the data home (read only):
  data/runner/wrong_answers.jsonl  — the 52 type-misread wrong answers labelled in scripts/test_cases/qtype_wrong_labels.json
  data/runner/audit/items.jsonl    — questions the independent audit judged right (check = right), by class
  data/runner/fields/*.jsonl       — the forms corpus: full question text, options, and which rule answered (source)
Right-answer items keep only questions whose answer came from an answer rule (source = rules:<id> or <id>), deduplicated
by question + options, at most --cap per rule, a fixed-seed sample of --n per class. The gold key is that rule.

No fact about the user is written: wrong items carry the labelled reading only; right items carry the rule key only —
their right answer (also a fact, even a bare yes / no) is looked up from the audit at scoring time (qtype_eval.load_answers,
local); ids are hashes, not folder names.

  python3 scripts/learn/qtype_gold.py [--n 300] [--cap 12] [--seed 361]
"""
import argparse, glob, hashlib, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'config'))
sys.path.insert(0, HERE)
import paths  # noqa: E402
import qtype_eval as Q  # noqa: E402

LABELS = os.path.join(ROOT, 'scripts', 'test_cases', 'qtype_wrong_labels.json')


def h(*parts):
    return hashlib.sha1('|'.join(parts).encode('utf-8')).hexdigest()[:12]


def rule_of(source):
    s = str(source or '')
    s = s[len('rules:'):] if s.startswith('rules:') else s
    k = s.split(':', 1)[0]
    return k if k in Q.KEYS else None


def build(n=300, cap=12, seed=361, exclude=None):
    """exclude = a gold set already built (the tuning set): a held-out set leaves out its folders and its questions and
    has no wrong-answer part (all 52 type-misread wrong answers are in the tuning set)."""
    run = paths.data('runner')
    corpus = {}
    for f in sorted(glob.glob(os.path.join(run, 'fields', '*.jsonl'))):
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            corpus.setdefault(r['folder'], []).append(r)
    audit = [json.loads(x) for x in open(os.path.join(run, 'audit', 'items.jsonl'), encoding='utf-8')]
    by_folder = {}
    for a in audit:
        by_folder.setdefault(a['folder'], []).append(a)

    def full(folder, q):
        """The longest corpus / audit record of this folder whose question starts like q (audit truncates)."""
        cands = [r for r in corpus.get(folder, []) + by_folder.get(folder, []) if str(r['question']).startswith(q[:60])]
        cands.sort(key=lambda r: (len(r.get('options') or []) > 0, len(r['question'])), reverse=True)
        return cands[0] if cands else None

    out = []
    held = exclude is not None
    if held:
        tune_ids = {g['id'] for g in exclude}
        tune_q = {g['question'] for g in exclude}
        tune_f = {a['folder'] for a in audit if Q.right_id(a['folder'], a['question']) in tune_ids}
    labels = {} if held else json.load(open(LABELS, encoding='utf-8'))['labels']
    seen = set()
    for line in open(os.path.join(run, 'wrong_answers.jsonl'), encoding='utf-8'):
        w = json.loads(line)
        k = h(w['folder'], w['field'])
        if k not in labels or k in seen:
            continue
        seen.add(k)
        r = full(w['folder'], w['field']) or {}
        g = {x: labels[k][x] for x in ('keys', 'shape', 'subject', 'negated', 'degree', 'dim')}
        out.append({'id': 'w' + k, 'set': 'wrong', 'question': r.get('question') or w['field'], 'options': r.get('options') or [],
                    'type': r.get('type') or '', 'cls': w.get('class') or '', 'gold': g})

    src = {}
    for folder, rs in corpus.items():
        for r in rs:
            src.setdefault((folder, r['question']), r)
    pool = {'critical': {}, 'non-critical': {}}
    for a in audit:
        if a.get('check') != 'right' or a.get('cls') not in pool:
            continue
        if held and a['question'] in tune_q:
            continue
        c = src.get((a['folder'], a['question']))
        key = rule_of(c and c.get('source'))
        if not key:
            continue
        opts = (c.get('options') or a.get('options') or [])
        uq = (a['question'], tuple(map(str, opts)))
        if uq in pool[a['cls']]:
            continue
        pool[a['cls']][uq] = {'id': Q.right_id(a['folder'], a['question']), 'question': a['question'], 'options': list(opts),
                              'type': c.get('type') or a.get('type') or '', 'cls': a['cls'],
                              'gold': {'key': key}}
    rnd = random.Random(seed)
    for cls, name in (('critical', 'right_critical'), ('non-critical', 'right_noncritical')):
        items = sorted(pool[cls].values(), key=lambda x: x['id'])
        rnd.shuffle(items)
        per, pick = {}, []
        for it in items:
            k = it['gold']['key']
            if per.get(k, 0) >= cap:
                continue
            per[k] = per.get(k, 0) + 1
            pick.append(dict(it, set=name))
            if len(pick) >= n:
                break
        out += pick
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--cap', type=int, default=12)
    ap.add_argument('--seed', type=int, default=361)
    ap.add_argument('--out', default=None)
    ap.add_argument('--holdout', action='store_true', help='build the held-out set (scripts/test_cases/qtype_holdout.jsonl): '
                    'no folder or question of the tuning set; never tune the list on it')
    a = ap.parse_args(argv)
    if a.holdout:
        tune = [json.loads(x) for x in open(Q.GOLD, encoding='utf-8')]
        gold = build(a.n, a.cap, a.seed + 1, exclude=tune)
        a.out = a.out or Q.HOLDOUT
    else:
        gold = build(a.n, a.cap, a.seed)
        a.out = a.out or Q.GOLD
    with open(a.out, 'w', encoding='utf-8') as fh:
        for g in gold:
            fh.write(json.dumps(g, ensure_ascii=False) + '\n')
    c = {}
    for g in gold:
        c[g['set']] = c.get(g['set'], 0) + 1
    print(json.dumps(c), '→', a.out)


if __name__ == '__main__':
    sys.exit(main())
