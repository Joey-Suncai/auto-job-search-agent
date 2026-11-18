#!/usr/bin/env python3
"""Daily skill-gap list: JD terms that keep coming up and that none of Joey's facts show (JSA-194, spec step 9).

Pure part (tested, scripts/test_skill_gap.py): `gap_list(records, today, days=14, min_folders=3, min_companies=2)`
over materials_score.json records ({folder, company, generated_at, gaps_not_true}) →
    [{term, folders: n, companies: n, share, examples: [folder…]}], most frequent first.
A term counts once per folder; only folders generated within `days` of `today`; a term needs ≥ min_folders folders AND
≥ min_companies different companies (one company posting the same JD ten times is not a trend). Terms are matched
case-insensitively; the shown spelling is the most frequent one.
The list asks, it never claims: "no fact shows X in N recent JDs — if you really did it, tell me (a fact, with the real scope);
otherwise nothing is added." joey_todo shows it as one row of kind 'skill-gap'.

    python3 scripts/store/skill_gap.py          # print the list; also writes data/runner/skill_gap.json
"""
import collections, json, os, sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'config'))


def _day(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def gap_list(records, today, days=14, min_folders=3, min_companies=2):
    t0 = _day(today)
    seen, spell, comp, ex = collections.defaultdict(set), collections.defaultdict(collections.Counter), collections.defaultdict(set), collections.defaultdict(list)
    total = 0
    for r in records or []:
        d = _day(r.get('generated_at')) or _day(str(r.get('folder') or '')[:10])
        if d is None or t0 is None or (t0 - d).days > days or (t0 - d).days < 0:
            continue
        total += 1
        for term in {(x or '').strip() for x in r.get('gaps_not_true') or []}:
            if not term:
                continue
            k = term.lower()
            if r['folder'] in seen[k]:
                continue
            seen[k].add(r['folder']); spell[k][term] += 1; comp[k].add((r.get('company') or r['folder']).lower()); ex[k].append(r['folder'])
    out = [{'term': spell[k].most_common(1)[0][0], 'folders': len(f), 'companies': len(comp[k]), 'share': round(len(f) / total, 3), 'examples': ex[k][:3]}
           for k, f in seen.items() if len(f) >= min_folders and len(comp[k]) >= min_companies]
    return sorted(out, key=lambda x: (-x['folders'], x['term'].lower()))


def todo_row(gaps, today):
    """The one joey_todo row for a non-empty list (None when empty)."""
    if not gaps:
        return None
    top = ', '.join(f"{g['term']} ({g['folders']})" for g in gaps[:8])
    return {'folder': 'skill-gap', 'job_id': '', 'n': len(gaps), 'sources': ['skill_gap'], 'at': str(today)[:10], 'url': '', 'kind': 'skill-gap',
            'msg': f'Recurring JD terms none of your facts show: {top}',
            'next': 'If you really did any of these, tell me what and how much (it becomes a fact); otherwise nothing is added — the resume never claims it',
            'age_days': None, 'deadline': '', 'days_left': None, 'overdue': False}


def load_records():
    import paths
    out, base = [], paths.apps()
    for f in sorted(os.listdir(base)):
        try:
            out.append(json.load(open(os.path.join(base, f, 'materials_score.json'), encoding='utf-8')))
        except (OSError, ValueError):
            pass
    return out


def build(today=None):
    today = today or date.today().isoformat()
    return gap_list(load_records(), today)


def main():
    import paths
    g = build()
    p = paths.data('runner', 'skill_gap.json')
    json.dump({'built': datetime.now().isoformat(timespec='seconds'), 'gaps': g}, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'skill_gap: {len(g)} recurring term(s) → {p}')
    for x in g[:15]:
        print(f"- {x['term']}: {x['folders']} folders, {x['companies']} companies")
    return 0


if __name__ == '__main__':
    sys.exit(main())
