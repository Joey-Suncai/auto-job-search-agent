#!/usr/bin/env python3
"""JSA-355 acceptance replay (live, calls Claude Haiku; not part of test_all): every critical wrong answer the audit found
(data/runner/wrong_answers.jsonl) is fed to final_review as the page cell it was; the review must stop it.
    python3 scripts/final_review_replay.py [--out report.json]      cost ~ a few cents; sends questions + facts to Anthropic (Joey 11-16: ok)"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner')); sys.path.insert(0, os.path.join(ROOT, 'config'))
import final_review as FR, paths  # noqa: E402

rows = []
for l in open(paths.data('runner', 'wrong_answers.jsonl'), encoding='utf-8'):
    r = json.loads(l)
    if r.get('class') != 'critical':
        continue
    m = re.match(r"answered '(.*?)'(?: —| \()", r['note']) or re.match(r"picked the '(.*?)' option", r['note'])
    rows.append({'label': r['field'], 'value': m.group(1) if m else '', 'type': 'text', 'folder': r['folder']})
out, caught = [], 0
facts = FR._facts()
for i in range(0, len(rows), 12):
    chunk = rows[i:i + 12]
    probs = FR.problems(chunk, mode='block', facts=facts, cache_path=None, log_path=None)
    for r in chunk:
        hit = [p for p in probs if r['label'][:60] in p]
        caught += bool(hit)
        out.append({'folder': r['folder'], 'label': r['label'][:80], 'value': r['value'], 'caught': bool(hit), 'verdict': hit[0][:200] if hit else ''})
    if any('unavailable' in p for p in probs):
        print('API problem:', [p for p in probs if 'unavailable' in p][0]); sys.exit(2)
print('caught %d / %d' % (caught, len(rows)))
for o in out:
    if not o['caught']:
        print('MISSED', o['folder'][:40], '|', o['label'], '|', o['value'])
if '--out' in sys.argv:
    json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'), indent=1, ensure_ascii=False)
