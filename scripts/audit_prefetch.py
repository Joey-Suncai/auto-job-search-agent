#!/usr/bin/env python3
"""Weekly spot check of the form prefetch's suggested answers (JSA-240; docs: the form-prefetch spec's "Weekly" line).

Every morning sheet's DeepSeek suggestions are appended to data/forms/suggestions.jsonl (form_prefetch.py, one line per
suggested question). Once a week this compares each suggestion with the answer Joey actually saved for that question
(config/profile.json qa, found the way the runners find it: answer_rules through qa_add.check, entries whose source names the
prefetch / Joey). Every disagreement is listed in data/forms/audit_<date>.md — each becomes a rule or a corrected fact
(development work); the agreement rate is the number to watch.

    python3 scripts/audit_prefetch.py --run [--days 7]      # compare, write audit_<date>.md, print one line
Pure functions (tested: scripts/test_jsa240_prefetch_audit.py): norm, verdict, audit."""
import argparse, json, os, re, sys
from datetime import date, datetime, timedelta
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', str(s or '').lower())).strip()


def pick_option(answer, options):
    """The first option whose normalised text equals the normalised answer, else the first one starting with it, else None."""
    a = norm(answer)
    if not a:
        return None
    for o in options or []:
        if norm(o) == a:
            return o
    for o in options or []:
        if norm(o).startswith(a):
            return o
    return None


def verdict(suggestion, joey, options=()):
    """Pure (tested). 'open' (no saved answer) | 'asked' (the suggestion declined: ASK / empty) | 'agree' | 'disagree'."""
    j = (joey or '').strip() if isinstance(joey, str) else joey
    if j in (None, ''):
        return 'open'
    s = (suggestion or '').strip()
    if not s or s.upper() == 'ASK':
        return 'asked'
    if norm(s) == norm(j):
        return 'agree'
    if options:
        a, b = pick_option(s, options), pick_option(j, options)
        if a is not None and a == b:
            return 'agree'
    return 'disagree'


def audit(rows):
    """Pure (tested). [{question, suggestion, joey, options, fact, sheet}] → counts, agreement, the disagreeing rows. A question that
    appears more than once (lower-cased, spaces collapsed) counts once: the last row wins."""
    last = {}
    for r in rows:
        last[re.sub(r'\s+', ' ', str(r.get('question') or '').lower()).strip()] = r
    counts = {'agree': 0, 'disagree': 0, 'asked': 0, 'open': 0}
    bad = []
    for r in last.values():
        v = verdict(r.get('suggestion'), r.get('joey'), r.get('options') or [])
        counts[v] += 1
        if v == 'disagree':
            bad.append({k: r.get(k) for k in ('question', 'suggestion', 'joey', 'fact')})
    n = counts['agree'] + counts['disagree']
    return dict(counts, agreement=round(counts['agree'] / n, 3) if n else None, disagreeing=bad)


def joey_answers(rows):
    """Impure: for every suggestion row, the answer the saved qa table gives today (value + source), or None."""
    import paths as jp
    sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'scripts'))
    import qa_add
    prof = jp.config('profile.json')
    qa = json.load(open(prof, encoding='utf-8')).get('qa') or []
    out = []
    for r in rows:
        try:
            shapes = r.get('option_sets') or [r.get('options') or []]
            got = qa_add.check_shapes(r['question'], shapes, prof)       # the lists the forms showed, not their union
        except Exception as ex:                                          # one bad row never loses the report
            print(f"prefetch audit: {r['question'][:60]!r} skipped ({type(ex).__name__})"); out.append(dict(r, joey=None, joey_source=None)); continue
        m = re.match(r'qa:(\d+)$', str(got.get('rule') or ''))
        e = qa[int(m.group(1)) - 1] if m else None
        ok = got.get('status') == 'ok' and e and r.get('date', '') <= str(e.get('added') or '')    # his answer came after the sheet
        out.append(dict(r, joey=got.get('value') if ok else None, joey_source=(e or {}).get('source') if ok else None))
    return out


def run(days=7, today=None):
    import paths as jp
    today = today or date.today()
    src = jp.data('forms', 'suggestions.jsonl')
    if not os.path.exists(src):
        print('prefetch audit: no suggestions logged yet'); return 0
    since = (today - timedelta(days=days)).isoformat()
    rows = []
    for l in open(src, encoding='utf-8'):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get('date', '') >= since and r.get('question'):
            rows.append(r)
    rows = joey_answers(rows)
    res = audit([r for r in rows if not r.get('derived')])                 # a derived block is accepted in one click: its "agreement" is by construction
    dv = audit([r for r in rows if r.get('derived')])
    md = [f'# Prefetch suggestions vs Joey — {today.isoformat()} (last {days} days)', '',
          f"agree {res['agree']} · disagree {res['disagree']} · asked (suggestion declined) {res['asked']} · open {res['open']} · "
          f"agreement {res['agreement'] if res['agreement'] is not None else 'n/a'} (own answers; derived block apart: agree {dv['agree']}, "
          f"disagree {dv['disagree']}). 'open' = no saved answer resolves for the question through the rules today.", '']
    if res['disagreeing']:
        md += ['## Disagreements — each becomes a rule or a corrected fact', '']
        md += [f"- {d['question'][:200]}\n  suggested **{d['suggestion']}** (fact {d['fact']}) · Joey **{d['joey']}**" for d in res['disagreeing'] + dv['disagreeing']]
    open(jp.data('forms', f'audit_{today.isoformat()}.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print(f"prefetch audit: agree {res['agree']} · disagree {res['disagree']} · asked {res['asked']} · open {res['open']} · agreement {res['agreement']}")
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--run', action='store_true'); ap.add_argument('--days', type=int, default=7)
    a = ap.parse_args()
    sys.exit(run(a.days) if a.run else ap.print_help())
