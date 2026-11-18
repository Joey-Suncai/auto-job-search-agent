#!/usr/bin/env python3
"""Wording gaps → reserve bullets (JSA-262, resume-updater §5): the JD terms that are TRUE for the candidate but not
phrased on the approved direction master, collected over all the direction's JDs, then turned into reserve bullets
the user approves once — so tailor.py can bring them per job without ever writing a sentence itself.

    python3 gap_reserve.py --direction ai_pm [--top 15]            # ① the gap table (data home resume/<YYYY-MM>/)
    python3 gap_reserve.py --direction ai_pm --deny stakeholders --fact jsa.dash   # ② the user says a tag is not true
    python3 gap_reserve.py --direction ai_pm --prompt-out p.txt     # ③ writer prompt for candidate bullets
    python3 gap_reserve.py --direction ai_pm --check cands.json     # ④ check candidates (direction_master.check + gap term)
    python3 gap_reserve.py --direction ai_pm --approve cands.json --quote "批准"   # ⑤ into the master's reserve + bank

① For every JD of the direction (role library `jd_ids`, cached JD texts) the top 12 terms (tailor.jd_terms) whose truth
is "true" (tailor.truth) and that the master's page does not say in the JD's spelling: state `missing` (no spelling of
the term on the page) or `other_spelling` (a variant is there, not the JD's). Aggregated per term: JDs, share, summed
score, the JD spellings, the facts and the exact fact-skill tags that make it "true". Ranked by summed score.
② Every tag is a claim. Before a sentence is written the user confirms each top term's tags; a tag he denies is removed
from that fact's skills (`--deny TERM --fact ID`, or `--fact skills.true` for the general skills list) — the term is then
no longer "true" there. Only with the user's answer (Rule 2); the session logs it in decisions-log.md.
③ Candidates are written by Claude (a session, or the API) from the cited facts only: JSON list of
{entry_id, text, fact_ids, bold, gap} — `gap` = the term the bullet brings.
④ A candidate passes when: its entry is on the master; its text is new (not an approved bullet / reserve bullet); it
holds one spelling of its gap term (the JD's spelling preferred); and direction_master.check passes on the master with
the candidates as its reserve (fact ids of its entry, current numbers, never-phrases, pairs, STAR, bold), plus
check_bullets.check_bullet on each (verb first, no causal clause, why / problem, length, banned words).
⑤ Approved candidates (the user's yes in chat) are appended to the master's `reserve` (amendment noted in `approved`)
and to bullet-bank.md (the data home's facts/, paths.fact) under the entry's heading.
Exit 0 ok · 1 problems · 2 missing input.
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL))
ROLES = os.path.join(SKILL, 'roles')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import paths  # noqa: E402  (generated role library: data home first, JSA-377)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'config'))
import paths as _jp  # noqa: E402
BANK = _jp.fact('bullet-bank.md')   # the data home's fact file, else the repo's old place (JSA-339)
import tailor as TL  # noqa: E402
from gap_report import group_hit, true_skills  # noqa: E402
from role_library import matcher  # noqa: E402


def tags_for(spellings, fb):
    """[(fact id, skill)] whose skill matches the term — the claims that make it "true" ('skills.true' for the list)."""
    ms = [matcher(s) for s in spellings]
    on = {e['id'] for e in fb['entries'] if e.get('on_resume', True) is not False}
    out = [(f['id'], s) for f in fb['facts'] if f.get('resume_ok', True) is not False and f['entry'] in on
           for s in f.get('skills') or [] if group_hit(spellings, ms, s)]
    out += [('skills.true', s) for s in true_skills(fb) if group_hit(spellings, ms, s)]
    return out


def jd_gaps(jd, title, role, fb, page, n=TL.TOP_N):
    """The true top terms of one JD that the page does not say in the JD's spelling."""
    out = []
    for t in TL.jd_terms(jd, role, title, n):
        state, ids = TL.truth(t, fb)
        if state != 'true':
            continue
        if TL.found(t['jd_spelling'], page):
            continue
        st = 'other_spelling' if any(TL.found(s, page) for s in t['spellings']) else 'missing'
        out.append(dict(term=t['term'], jd_spelling=t['jd_spelling'], spellings=t['spellings'], competency=t['competency'],
                        score=t['score'], state=st, facts=ids))
    return out


def aggregate(per_jd, n_jds, fb=None):
    """Rows per term over all JDs, ranked by summed score: {term, jds, share, score, spellings (JD spelling → count),
    states (state → count), facts, tags, competency}."""
    acc = {}
    for gaps in per_jd:
        for g in gaps:
            r = acc.setdefault(g['term'], dict(term=g['term'], jds=0, score=0.0, spellings=collections.Counter(),
                                                states=collections.Counter(), facts=set(), competency=g['competency'],
                                                all_spellings=g['spellings']))
            r['jds'] += 1
            r['score'] += g['score']
            r['spellings'][g['jd_spelling']] += 1
            r['states'][g['state']] += 1
            r['facts'] |= set(g['facts'])
    rows = []
    for r in acc.values():
        rows.append(dict(term=r['term'], jds=r['jds'], share=round(r['jds'] / n_jds, 4) if n_jds else 0.0,
                         score=round(r['score'], 4), spellings=dict(r['spellings'].most_common()),
                         states=dict(r['states']), facts=sorted(r['facts']), competency=r['competency'],
                         tags=tags_for(r['all_spellings'], fb) if fb else []))
    rows.sort(key=lambda x: (-x['score'], -x['jds'], x['term']))
    return rows


def deny(fb, spellings, fact_id):
    """Remove the skills of `fact_id` (or 'skills.true') that match the term; returns the removed skills."""
    ms = [matcher(s) for s in spellings]
    removed = []
    if fact_id == 'skills.true':
        for k, v in (fb.get('skills') or {}).get('true', {}).items():
            keep = [s for s in v if not group_hit(spellings, ms, s)]
            removed += [s for s in v if group_hit(spellings, ms, s)]
            fb['skills']['true'][k] = keep
        return removed
    for f in fb['facts']:
        if f['id'] == fact_id:
            removed = [s for s in f.get('skills') or [] if group_hit(spellings, ms, s)]
            f['skills'] = [s for s in f.get('skills') or [] if not group_hit(spellings, ms, s)]
    return removed


def check_candidates(master, cands, fb, direction, spellings_of):
    """Problems for candidate reserve bullets. spellings_of: term (lower) → [spellings] (from the role library)."""
    import direction_master as DM
    import check_bullets as CB
    errs = []
    ents = {e['entry_id'] for e in master.get('entries') or []}
    known = {b['text'] for e in master.get('entries') or [] for b in e['bullets']} | {r['text'] for r in master.get('reserve') or []}
    for i, c in enumerate(cands):
        tag = f'candidate {i + 1} ({c.get("entry_id")})'
        if c.get('entry_id') not in ents:
            errs.append(f'{tag}: entry_not_on_master — "{c.get("entry_id")}" has no section on the master')
        if c.get('text') in known:
            errs.append(f'{tag}: not_new — already an approved bullet')
        gap = (c.get('gap') or '').strip()
        sp = spellings_of.get(gap.lower()) or ([gap] if gap else [])
        if not gap or not any(matcher(s).search(c.get('text') or '') for s in sp):
            errs.append(f'{tag}: no_gap_term — the bullet must say its gap term ("{gap}")')
        for x in CB.check_bullet(c.get('text') or ''):   # direction_master.check runs the bullet rules on page bullets only
            errs.append(f'{tag}: {x}')
    m = dict(master)
    m['reserve'] = [{k: c.get(k) for k in ('entry_id', 'text', 'fact_ids', 'bold')} for c in cands]
    errs += DM.check(m, fb, direction)
    return errs


def spellings_map(role):
    out = {}
    for c in role.get('competencies') or []:
        for k in c.get('keywords') or []:
            sp = [k['term']] + list(k.get('synonyms') or [])
            for s in sp:
                out[s.lower()] = sp
    return out


def bank_insert(bank_text, heading, lines):
    """bank_text with `lines` added at the end of the '## <heading>' section (a new section at the end if missing)."""
    out = bank_text.rstrip('\n').split('\n')
    try:
        i = next(k for k, l in enumerate(out) if l.strip() == f'## {heading}')
    except StopIteration:
        return '\n'.join(out) + f'\n\n## {heading}\n' + '\n'.join(lines) + '\n'
    j = next((k for k in range(i + 1, len(out)) if out[k].startswith('## ')), len(out))
    while j > i + 1 and not out[j - 1].strip():
        j -= 1
    return '\n'.join(out[:j] + lines + out[j:]) + '\n'


def report(direction, rows, n_jds, top, mpath):
    L = [f'# Wording gaps → reserve — {direction} ({datetime.date.today()})', '',
         f'True JD terms the approved master (`{mpath}`) does not say in the JD\'s spelling, over {n_jds} JDs of the '
         'direction (top 12 terms per JD). Every tag below is a claim: confirm it with the user before a sentence is '
         'written (`--deny TERM --fact ID` removes a wrong one).', '',
         '| # | Term (JD spellings) | JDs | Share | Score | State | Tags that make it true |', '| --- | --- | --- | --- | --- | --- | --- |']
    for i, r in enumerate(rows[:top], 1):
        sp = ', '.join(f'{k} ×{v}' for k, v in r['spellings'].items())
        st = ', '.join(f'{k} {v}' for k, v in r['states'].items())
        tg = '; '.join(f'{f}: "{s}"' for f, s in r['tags'])
        L.append(f'| {i} | **{r["term"]}** ({sp}) | {r["jds"]} | {r["share"]:.0%} | {r["score"]} | {st} | {tg} |')
    L += ['', 'Next: ask the user per term whether each tag is true → `--deny` the wrong ones → `--prompt-out` → write '
          'candidates → `--check` → show them → `--approve` with his quote.']
    return '\n'.join(L) + '\n'


WRITER = """Write reserve bullets for the candidate's approved {direction} master resume. Each bullet brings ONE wording
gap — a JD term that is true for the candidate (his facts show it) but that his resume does not say yet.

Rules (a checker rejects a bullet that breaks one):
- Use only the cited facts below; cite their ids (one entry per bullet). Every number must be a cited fact's current
  number. Respect "ownership", "must_keep", "never" and "pairs".
- The bullet says its gap term, in the JD spelling given.
- First word an action verb; no "because" / "since" / "due to"; with a number: what + why + impact, without: problem +
  how; ≤ 220 characters; 1–2 bold terms written exactly as in the text; no banned words: {banned}.
- Do not repeat an existing bullet (listed below); say something the page does not.
Return a JSON list: [{{"entry_id", "text", "fact_ids", "bold", "gap"}}], one or two bullets per gap term.

Gap terms (term · JD spelling · facts whose tags make it true):
{gaps}

Existing bullets:
{bullets}

Facts:
{facts}
"""


def writer_prompt(direction, rows, master, fb, top):
    import check_bullets as CB
    F = {f['id']: f for f in fb['facts']}
    gl, ids = [], set()
    for r in rows[:top]:
        sp = next(iter(r['spellings']), r['term'])
        fids = sorted({f for f, _ in r['tags'] if f in F})
        ids |= set(fids)
        gl.append(f'- {r["term"]} · "{sp}" · {", ".join(fids) or "(skills list only)"}')
    bl = [f'- [{e["entry_id"]}] {b["text"]}' for e in master['entries'] for b in e['bullets']]
    bl += [f'- [{r["entry_id"]}, reserve] {r["text"]}' for r in master.get('reserve') or []]
    keep = ('id', 'entry', 'S', 'T', 'A', 'R', 'numbers', 'skills', 'ownership', 'must_keep', 'never', 'pairs')
    facts = json.dumps([{k: F[i].get(k) for k in keep if F[i].get(k) is not None} for i in sorted(ids)], ensure_ascii=False, indent=1)
    return WRITER.format(direction=direction, banned=', '.join(CB.BANNED), gaps='\n'.join(gl), bullets='\n'.join(bl), facts=facts)


def page_of(master, fb):
    """The master's page text as a reader sees it: tailor.page_text + the entry headings (org / project names, roles) —
    "Machine Learning Prediction of …" says "machine learning"."""
    E = {e['id']: e for e in fb['entries']}
    heads = [' '.join(str((E.get(e['entry_id']) or {}).get(k) or '') for k in ('org', 'role')) for e in master.get('entries') or []]
    return TL.page_text(master) + '\n' + '\n'.join(heads)


def collect(direction, fb, master, role):
    sys.path.insert(0, HERE)
    from role_library import load_corpus
    jobs, texts = load_corpus()
    J = {j['id']: j for j in jobs if j.get('id')}
    page = page_of(master, fb)
    per = []
    for jid in role.get('jd_ids') or []:
        if jid in texts:
            per.append(jd_gaps(texts[jid], (J.get(jid) or {}).get('title') or '', role, fb, page))
    return aggregate(per, len(per), fb), len(per)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--direction', required=True)
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--facts')
    ap.add_argument('--master')
    ap.add_argument('--deny', help='term whose tag the user denied')
    ap.add_argument('--fact', help='with --deny: the fact id (or skills.true)')
    ap.add_argument('--prompt-out')
    ap.add_argument('--check')
    ap.add_argument('--approve')
    ap.add_argument('--quote', help='with --approve: the user\'s words')
    ap.add_argument('--stdout', action='store_true')
    a = ap.parse_args(argv)
    import paths
    fpath = a.facts or paths.config('facts.json')
    try:
        fb = json.load(open(fpath, encoding='utf-8'))
        role = json.load(open(paths.role_file(f'{a.direction}.json'), encoding='utf-8'))
    except OSError as ex:
        print(f'gap_reserve: {ex}')
        return 2
    if a.master:
        d = json.load(open(a.master, encoding='utf-8'))
        master, mpath = (d.get('master') if d.get('approved') else None), a.master
    else:
        master, mpath = TL.approved_master(a.direction)
    if not master:
        print(f'gap_reserve: no approved {a.direction} master')
        return 2
    smap = spellings_map(role)

    if a.deny:
        if not a.fact:
            ap.error('--deny needs --fact')
        sp = smap.get(a.deny.lower()) or [a.deny]
        removed = deny(fb, sp, a.fact)
        if not removed:
            print(f'gap_reserve: {a.fact} has no skill matching "{a.deny}"')
            return 1
        json.dump(fb, open(fpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'gap_reserve: removed {removed} from {a.fact} (log the user\'s answer in decisions-log.md)')
        return 0

    if a.check or a.approve:
        cands = json.load(open(a.check or a.approve, encoding='utf-8'))
        errs = check_candidates(master, cands, fb, a.direction, smap)
        for e in errs:
            print(e)
        print(f'gap_reserve: {len(cands)} candidate(s), {len(errs)} problem(s)')
        if errs or a.check:
            return 1 if errs else 0
        if not a.quote:
            ap.error('--approve needs --quote (the user\'s words)')
        d = json.load(open(mpath, encoding='utf-8'))
        d['master'].setdefault('reserve', [])
        for c in cands:
            d['master']['reserve'].append({k: c.get(k) for k in ('entry_id', 'text', 'fact_ids', 'bold')})
        today = str(datetime.date.today())
        d['approved'].setdefault('reserve_added', []).append(
            {'date': today, 'quote': a.quote, 'texts': [c['text'] for c in cands], 'gaps': [c.get('gap') for c in cands]})
        json.dump(d, open(mpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        E = {e['id']: e for e in fb['entries']}
        bank = open(BANK, encoding='utf-8').read()
        for c in cands:
            e = E.get(c['entry_id']) or {}
            head = e.get('name') or e.get('org') or c['entry_id']
            bold = ', '.join(c.get('bold') or []) or '—'
            bank = bank_insert(bank, head, [f'- {c["text"]}  ',
                                            f'  *used in: {a.direction} master reserve (approved {today}, gap "{c.get("gap")}") · '
                                            f'facts: {", ".join(c.get("fact_ids") or [])} · bold: {bold}*'])
        open(BANK, 'w', encoding='utf-8').write(bank)
        print(f'gap_reserve: {len(cands)} bullet(s) added to {mpath} reserve and bullet-bank.md')
        return 0

    rows, n = collect(a.direction, fb, master, role)
    if a.prompt_out:
        open(a.prompt_out, 'w', encoding='utf-8').write(writer_prompt(a.direction, rows, master, fb, a.top))
        print(f'gap_reserve: prompt → {a.prompt_out}')
        return 0
    md = report(a.direction, rows, n, a.top, mpath)
    if a.stdout:
        print(md)
        return 0
    out = os.path.join(paths.resume(), datetime.date.today().strftime('%Y-%m'))
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, f'gap_reserve_{a.direction}.md'), 'w', encoding='utf-8').write(md)
    json.dump(rows[:a.top], open(os.path.join(out, f'gap_reserve_{a.direction}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
