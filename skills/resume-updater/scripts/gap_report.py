#!/usr/bin/env python3
"""Gap report: what a target direction asks for vs. what the candidate's facts can prove (JSA-253, ADR-0010).

    python3 gap_report.py --direction ai_pm          # → data home resume/<YYYY-MM>/gap_ai_pm.md
    python3 gap_report.py --all                       # every roles/<direction>.json
    python3 gap_report.py --direction ai_pm --stdout  # print instead of writing

Inputs: roles/<direction>.json (competency weights + keyword groups, from role_library.py), roles/lexicon.json
(gap_suggestion per competency) and the data home's config/facts.json (or --facts).

For every competency with weight ≥ --min-weight (default 0.03), in weight order, the evidence level is the first that holds:
- **proven / partial** — facts with resume_ok ≠ false list skills matching the competency's keyword groups; coverage =
                   covered keywords' df / all its keywords' df; ≥ 0.5 (--proven-share) = proven, else partial (the
                   report names the most-asked keywords still missing);
- **mentioned**  — no such fact, but a resume_ok fact's A or R text matches a keyword (the story touches it; the
                   resume can say it only in that fact's words);
- **listed only**— no fact, but a skill in facts.skills.true matches (it is on the skills line with no bullet behind it);
- **off resume** — only facts with resume_ok = false match (true, but kept off the resume by decision);
- **gap**        — nothing matches.
A skill / text matches a keyword group when any spelling of the group matches (role_library.matcher: case-insensitive,
whole token) or the skill equals a spelling (case-insensitive).
Then: the JD-frequent tools the candidate confirmed NOT having (facts.skills.not_true found among the direction's
keyword spellings, with the keyword's df). The report suggests only kinds of real experience (lexicon gap_suggestion),
never wording that claims them. Exit 0; 2 = a file is missing.
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL))
ROLES = os.path.join(SKILL, 'roles')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import paths  # noqa: E402  (generated role library: data home first, JSA-377)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'config'))
from role_library import matcher  # noqa: E402

LEVELS = ('proven', 'partial', 'mentioned', 'listed only', 'off resume', 'gap')


def group_hit(spellings, ms, s):
    s = str(s or '')
    return any(m.search(s) for m in ms) or s.strip().lower() in {x.lower() for x in spellings}


def true_skills(fb):
    out = []
    for v in ((fb.get('skills') or {}).get('true') or {}).values():
        out += list(v)
    return out


def assess(role, fb, min_weight=0.03, proven_share=0.5):
    """[{id, label, weight, df, level, coverage, facts, keywords, missing, top_terms}] in weight order.
    Keyword level: a keyword (group) is covered when a resume_ok fact lists a matching skill. coverage = sum of covered
    keywords' df / sum of all keywords' df (JD demand). Competency level: proven (coverage ≥ proven_share), partial
    (0 < coverage < proven_share), else mentioned / listed only / off resume / gap as in the module doc."""
    facts = fb.get('facts') or []
    on = [f for f in facts if f.get('resume_ok', True) is not False]
    off = [f for f in facts if f.get('resume_ok', True) is False]
    listed = true_skills(fb)
    uniq = lambda xs: list(dict.fromkeys(xs))
    rows = []
    for c in role.get('competencies') or []:
        if c.get('weight', 0) < min_weight:
            continue
        groups = []
        for k in c.get('keywords') or []:
            sp = [k['term']] + list(k.get('synonyms') or [])
            groups.append((k['term'], float(k.get('df') or 0), sp, [matcher(x) for x in sp]))

        def by_skills(pool):
            ids, kws = [], []
            for f in pool:
                for term, df, sp, ms in groups:
                    if any(group_hit(sp, ms, s) for s in f.get('skills') or []):
                        ids.append(f['id']); kws.append(term)
            return uniq(ids), uniq(kws)

        def by_text(pool):
            ids, kws = [], []
            for f in pool:
                txt = f"{f.get('A') or ''} {f.get('R') or ''}"
                for term, df, sp, ms in groups:
                    if any(m.search(txt) for m in ms):
                        ids.append(f['id']); kws.append(term)
            return uniq(ids), uniq(kws)

        demand = sum(df for _, df, _, _ in groups)
        ids, kws = by_skills(on)
        cov = (sum(df for t, df, _, _ in groups if t in kws) / demand) if demand else (1.0 if kws else 0.0)
        if kws:
            level = 'proven' if cov >= proven_share else 'partial'
        else:
            ids, kws = by_text(on)
            if ids:
                level = 'mentioned'
            else:
                kws = [t for t, df, sp, ms in groups if any(group_hit(sp, ms, s) for s in listed)]
                if kws:
                    level = 'listed only'
                else:
                    ids, kws = by_skills(off)
                    if not ids:
                        ids, kws = by_text(off)
                    level = 'off resume' if ids else 'gap'
        covered = set(kws) if level in ('proven', 'partial') else set()
        missing = [t for t, df, _, _ in sorted(groups, key=lambda g: -g[1]) if t not in covered and df > 0][:5]
        rows.append({'id': c['id'], 'label': c.get('label', c['id']), 'weight': c.get('weight', 0),
                     'df': c.get('df', 0), 'level': level, 'coverage': round(cov, 3) if level in ('proven', 'partial') else 0.0,
                     'facts': ids, 'keywords': kws, 'missing': missing,
                     'top_terms': [k['term'] for k in (c.get('keywords') or [])[:4] if k.get('df', 0) > 0]})
    return rows


def missing_tools(role, fb):
    """[(not_true term, keyword df)] for the candidate's not_true tools that appear among the role's keyword spellings."""
    nt = [x for x in ((fb.get('skills') or {}).get('not_true') or [])]
    out = []
    for c in role.get('competencies') or []:
        for k in c.get('keywords') or []:
            sp = [k['term']] + list(k.get('synonyms') or [])
            for t in nt:
                if t.lower() in {x.lower() for x in sp}:
                    out.append((t, k.get('df', 0)))
    best = {}
    for t, df in out:
        best[t] = max(df, best.get(t, 0))
    return sorted(best.items(), key=lambda x: (-x[1], x[0]))


def render(role, rows, tools, suggestions, facts_path):
    n = role.get('n_jds')
    lines = [f"# Gap report — {role.get('label', role.get('direction'))}",
             '',
             f"Built {datetime.date.today().isoformat()} from `roles/{role.get('direction')}.json` ({n} JDs, built "
             f"{role.get('built')}) and `{facts_path}`. Weight = how much this direction's JDs ask for it; df = share of JDs that mention it.",
             '',
             '| Competency | Weight | JDs | Evidence | Covered | Facts | Covered asks | Missing asks (most asked first) |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in rows:
        lines.append(f"| {r['label']} | {r['weight']:.3f} | {r['df']:.0%} | **{r['level']}** | {r['coverage']:.0%} | "
                     f"{', '.join(r['facts']) or '—'} | {', '.join(r['keywords']) or '—'} | {', '.join(r['missing']) or '—'} |")
    weak = [r for r in rows if r['level'] != 'proven']
    lines += ['', '## Where the resume cannot prove it yet', '']
    if not weak:
        lines.append('Every competency above has a fact behind it.')
    for r in weak:
        sug = suggestions.get(r['id']) or ''
        what = {'partial': f"facts cover {r['coverage']:.0%} of what JDs ask here; missing: {', '.join(r['missing'][:4])}",
                'mentioned': 'the story touches it, but no fact lists it as a skill',
                'listed only': 'on the skills line, no bullet proves it',
                'off resume': 'true, but in a fact kept off the resume',
                'gap': 'no fact says it'}[r['level']]
        lines.append(f"- **{r['label']}** ({r['weight']:.3f}, {r['df']:.0%} of JDs) — {what}."
                     + (f" Real experience that would prove it: {sug}." if sug else ''))
    lines += ['', "## Tools the JDs ask for that you confirmed you have not used", '']
    if tools:
        lines += [f"- {t} — {df:.0%} of JDs" for t, df in tools if df > 0]
    else:
        lines.append('None of the confirmed not-used tools appear in this direction\'s JDs.')
    lines += ['', '*Suggestions name kinds of real experience only. Nothing here is resume wording; a claim enters the '
              'resume only after it is a confirmed fact.*', '']
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--direction', action='append')
    g.add_argument('--all', action='store_true')
    ap.add_argument('--facts')
    ap.add_argument('--min-weight', type=float, default=0.03)
    ap.add_argument('--proven-share', type=float, default=0.5)
    ap.add_argument('--stdout', action='store_true')
    a = ap.parse_args(argv)
    import paths
    fpath = a.facts or paths.config('facts.json')
    try:
        fb = json.load(open(fpath, encoding='utf-8'))
        lex = json.load(open(os.path.join(ROLES, 'lexicon.json'), encoding='utf-8'))
    except (OSError, ValueError) as ex:
        print(f'gap_report: {ex}')
        return 2
    sugg = {k: v.get('gap_suggestion') for k, v in lex['competencies'].items()}
    have = {p for d in (ROLES, paths.data('roles')) if os.path.isdir(d) for p in os.listdir(d)}   # code + data home (JSA-377)
    names = a.direction or sorted(p[:-5] for p in have if p.endswith('.json') and p not in ('lexicon.json', 'directions.json'))
    for n in names:
        rp = paths.role_file(f'{n}.json')
        if not os.path.exists(rp):
            print(f'gap_report: no {rp} (run role_library.py --direction {n})')
            return 2
        role = json.load(open(rp, encoding='utf-8'))
        rows = assess(role, fb, a.min_weight, a.proven_share)
        md = render(role, rows, missing_tools(role, fb), sugg, 'config/facts.json' if not a.facts else fpath)
        counts = {lv: sum(1 for r in rows if r['level'] == lv) for lv in LEVELS}
        summary = ' · '.join(f'{lv} {c}' for lv, c in counts.items() if c)
        if a.stdout:
            print(md)
        else:
            out = paths.resume(datetime.date.today().strftime('%Y-%m'), f'gap_{n}.md')
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, 'w', encoding='utf-8').write(md)
            print(f'{n}: {summary} → {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
