#!/usr/bin/env python3
"""JSA-400 acceptance: a golden set through the real model path (learn_triage.triage: fact read twice). The REAL set (60 candidates from the 11-17 card,
notes redacted, categories labelled by the developing session, disputed ones ruled by Claude) lives in the data home (data/learn/triage_golden.json) — real
questions and notes never go into this repo; the repo holds a small fictional fixture (scripts/test_cases/learn_triage_golden.json) that is the default
when the data-home file is absent.
Reports overall accuracy, the precision of 'fact', and the merge-error rate against the labelled groups. Bars (design): accuracy ≥ 85 %,
fact precision ≥ 95 %, merge errors ≤ 5 %.   Live DeepSeek calls (a few cents):  python3 scripts/learn/learn_triage_eval.py [--json out.json]"""
import json, os, sys, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import learn_triage as TR  # noqa: E402
import learn as L  # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..', '..', 'config'))
import paths as jpaths  # noqa: E402


def score(gold, res, groups):
    """Pure (tested). accuracy, fact precision / recall, merge precision and missed merges."""
    exp = {g['id']: g['expected'] for g in gold}
    acc = sum(1 for i in exp if res[i]['category'] == exp[i]) / len(exp)
    pf = [i for i in exp if res[i]['category'] == 'fact']
    fact_prec = sum(1 for i in pf if exp[i] == 'fact') / len(pf) if pf else None
    tf = [i for i in exp if exp[i] == 'fact']
    fact_rec = sum(1 for i in tf if res[i]['category'] == 'fact') / len(tf) if tf else None
    ok_pairs = {frozenset((g['id'], o)) for g in gold for o in g.get('accept_merge') or []}            # a merge Claude ruled defensible (recorded on the item)
    truth = {frozenset(p) for k, v in itertools.groupby(sorted((g['group'], g['id']) for g in gold if g.get('group')), key=lambda x: x[0]) for p in itertools.combinations([x[1] for x in v], 2)}
    pred = {frozenset(p) for g in groups for p in itertools.combinations(g, 2)}
    cat = lambda i: exp[i]
    wrong = sum(1 for pr in pred - truth - ok_pairs if len({cat(i) for i in pr}) > 1)       # a merge of different categories corrupts the ledger
    loose = len(pred - truth - ok_pairs) - wrong                                          # same category, not the labelled same problem: reported, tolerated
    return {'accuracy': round(acc, 3), 'fact_precision': fact_prec, 'fact_recall': fact_rec, 'predicted_fact': len(pf),
            'merge_pairs_predicted': len(pred), 'merge_errors': wrong, 'merge_error_rate': round(wrong / len(pred), 3) if pred else 0.0, 'merge_loose_same_category': loose,
            'merges_missed': len(truth - pred), 'merges_expected': len(truth)}


def main():
    real = jpaths.data('learn', 'triage_golden.json')
    path = sys.argv[sys.argv.index('--golden') + 1] if '--golden' in sys.argv else (real if os.path.exists(real) else os.path.join(HERE, '..', 'test_cases', 'learn_triage_golden.json'))
    gold = json.load(open(path)); print('golden set:', path, len(gold), 'items')
    usage = {}
    try: index = L.fact_index(json.load(open(jpaths.config('profile.json'), encoding='utf-8')))     # key names only, as in the daily run
    except Exception: index = []
    res, groups = TR.triage([{'id': g['id'], 'material': g['material']} for g in gold], lambda s, u, t=0.0: TR.ask_model(s, u, t, usage), {}, None, index)
    r = score(gold, res, groups)
    r['usage'] = usage
    r['wrong'] = [{'id': g['id'], 'key': g['key'][:70], 'expected': g['expected'], 'got': res[g['id']]['category'], 'reason': res[g['id']].get('reason', ''), 'evidence': res[g['id']]['evidence'][:60]}
                  for g in gold if res[g['id']]['category'] != g['expected']]
    print(json.dumps(r, ensure_ascii=False, indent=1))
    if '--json' in sys.argv: json.dump({'result': r, 'res': res, 'groups': groups}, open(sys.argv[sys.argv.index('--json') + 1], 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
