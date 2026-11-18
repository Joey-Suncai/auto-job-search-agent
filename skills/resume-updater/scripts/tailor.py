#!/usr/bin/env python3
"""JD tailoring from an approved direction master (JSA-251, spec docs/specs/materials-resume-framework.md ④⑤).

    ~/.job-agent-venv/bin/python tailor.py --jd applications/<folder>/jd.md --direction ai_pm [--out <folder>] [--dry]

Only mechanical changes to the approved master (it is the gate — Joey 2026-11-08): no sentence is written here.
1. JD terms — every keyword cluster of roles/<direction>.json (term + synonyms) is matched in the JD (role_library
   matcher: case-insensitive whole token). score = competency weight × min(hits, 3) × 2 when a spelling is in the job
   title. The top 12 by score (all of them when fewer) are the job's terms; the JD's spelling = its most frequent
   matched spelling (ties → the longer one).
2. Truth per term — true when a resume fact (resume_ok, entry on the resume) lists a skill of the cluster, or a
   skills.true item matches; "not used" when a spelling is in skills.not_true; else not true.
3. Changes (each is in the change list):
   - swap: a true term whose JD spelling is not on the page while a variant spelling is (truth_check.is_bullet_variant:
     same words up to case / hyphens, or acronym ↔ expansion, same grammatical number) → the variant is replaced by the
     JD spelling in the bullets, bold lists and skills items;
   - skill added: a true term still not on the page whose JD spelling is a true skill (skills.true or a resume fact's
     skills) → added to the skills group holding most skills of its evidence facts (then: most spellings of the same
     competency; then the first group);
   - alternates: a reserve bullet that brings a JD term the page lacks replaces a non-core bullet of its entry (core =
     the entry's first or marked "core": true — Joey 2026-11-09) whose JD terms all stay on the page without it (the one
     proving the direction's lowest-weight competency);
   - order: core bullets first in their approved order, then the entry's other bullets and the items of each skills
     group sorted by JD-term hits (stable);
   - headline: "<exact job title> · <up to 3 true JD terms in the JD's spelling that are true skills>".
4. Checks (⑤): truth_check.check_tailored (every direction_master rule + the tailored master is the approved one
   changed only mechanically), then layout (direction_master.layout: one page, bottom 730–756, check_resume).
   Failure → exit 1 and nothing is written but keyword_map.md (the caller uses the approved master unchanged and
   queues the job with the reason).
Outputs in --out: tailored.json (master + swaps + changes), keyword_map.md (terms, weights, before / after coverage,
gaps split into "true but not phrased" and "not true"), <Prefix>_Resume_<Company>_<Title>_A-Classic.docx / .pdf.
Exit 0 ok · 1 a check failed · 2 no approved master / missing file.
"""
import argparse
import copy
import datetime
import glob
import json
import os
import re
import shutil
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
import truth_check as TC  # noqa: E402
from gap_report import group_hit, true_skills  # noqa: E402

TOP_N = 12
TRACK_DIRECTION = {'Product_Manager': 'ai_pm', 'Data_Analyst': 'data_analyst', 'Data_Engineer': 'data_engineer',
                   'AI_Agentic_Engineer': 'ai_agentic'}


def approved_master(direction, resume_dir=None):
    """(master dict, path) of the newest approved master_<direction>.json in the data home resume/<YYYY-MM>/, or (None, None)."""
    if resume_dir is None:
        import paths
        resume_dir = paths.resume()
    for p in sorted(glob.glob(os.path.join(resume_dir, '*', f'master_{direction}.json')), reverse=True):
        d = json.load(open(p, encoding='utf-8'))
        if d.get('approved') and d.get('master'):
            return d['master'], p
    return None, None


def parse_jd(text, folder=''):
    """(title, company) from the first '# …' line, parts split on " — ". The company is the part whose words start the
    application folder's name (<date>_<Company>_<Title>), else the last part. ('', '') when there is no heading."""
    for line in text.splitlines():
        if line.startswith('# '):
            h = line[2:].strip()
            parts = [p.strip() for p in re.split(r'\s+—\s+', h) if p.strip()]
            if len(parts) < 2:
                return h, ''
            key = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', os.path.basename(folder.rstrip('/'))).lower()
            slug = lambda x: re.sub(r'[^a-z0-9]+', '_', x.lower()).strip('_')
            ci = next((i for i, p in enumerate(parts) if key and key.startswith(slug(p)[:12])), len(parts) - 1)
            comp = parts.pop(ci)
            return ' — '.join(parts), comp
    return '', ''


def jd_terms(jd, role, title='', n=TOP_N):
    out = []
    for c in role.get('competencies') or []:
        for k in c.get('keywords') or []:
            sp = [k['term']] + list(k.get('synonyms') or [])
            counts = {s: len(matcher(s).findall(jd)) for s in sp}
            hits = sum(counts.values())
            if not hits:
                continue
            in_title = any(matcher(s).search(title or '') for s in sp)
            best = max(sp, key=lambda s: (counts[s], len(s)))
            out.append(dict(term=k['term'], jd_spelling=best, spellings=sp, competency=c['id'], hits=hits, in_title=in_title,
                            score=round(c.get('weight', 0) * min(hits, 3) * (2 if in_title else 1), 4)))
    out.sort(key=lambda x: (-x['score'], -x['hits'], x['term']))
    return out[:n]


def truth(term, fb):
    """('true', [fact ids]) · ('not used', []) · ('not true', [])."""
    sp = term['spellings']
    ms = [matcher(s) for s in sp]
    on = {e['id'] for e in fb['entries'] if e.get('on_resume', True) is not False}
    ids = [f['id'] for f in fb['facts'] if f.get('resume_ok', True) is not False and f['entry'] in on
           and any(group_hit(sp, ms, s) for s in f.get('skills') or [])]
    if ids or any(group_hit(sp, ms, s) for s in true_skills(fb)):
        return 'true', ids
    nt = {x.lower() for x in (fb.get('skills') or {}).get('not_true') or []}
    if any(s.lower() in nt for s in sp):
        return 'not used', []
    return 'not true', []


def page_text(m):
    parts = [m.get('headline', ''), m.get('summary', '')]
    parts += [', '.join(s['items']) for s in m.get('skills') or []]
    parts += [b['text'] for e in m.get('entries') or [] for b in e['bullets']]
    return '\n'.join(parts)


def found(spelling, text):
    return bool(matcher(spelling).search(text))


def hits_in(text, terms):
    return sum(1 for t in terms if any(found(s, text) for s in t['spellings']))


def _sub(text, old, new):
    return matcher(old).sub(new, text)


def tailor(master, fb, role, jd, title='', company=''):
    """(tailored master, terms with before / after, changes)."""
    import direction_master as DM
    t = copy.deepcopy(master)
    t['swaps'], changes = [], []
    terms = jd_terms(jd, role, title)
    pool = TC.true_pool(fb)
    before = page_text(master)
    for x in terms:
        x['truth'], x['facts'] = truth(x, fb)
        x['before'] = 'exact' if found(x['jd_spelling'], before) else ('other spelling' if any(found(s, before) for s in x['spellings']) else 'no')
    # swaps
    for x in terms:
        if x['truth'] != 'true' or x['before'] != 'other spelling':
            continue
        txt = page_text(t)
        for s in x['spellings']:
            if s == x['jd_spelling'] or not found(s, txt) or not TC.is_bullet_variant(s, x['jd_spelling']):
                continue
            if found(x['jd_spelling'], txt):
                break
            changed = False
            for e in t['entries']:
                for b in e['bullets']:
                    if found(s, b['text']):
                        b['text'] = _sub(b['text'], s, x['jd_spelling'])
                        b['bold'] = [x['jd_spelling'] if bt.lower() == s.lower() else bt for bt in b.get('bold') or []]
                        changed = True
            for g in t.get('skills') or []:
                new_items = [x['jd_spelling'] if it.lower() == s.lower() and x['jd_spelling'].lower() in pool else it for it in g['items']]
                changed |= new_items != g['items']
                g['items'] = new_items
            if not changed:   # the other spelling is only in the headline / summary, which stay as approved
                continue
            t['swaps'].append({'from': s, 'to': x['jd_spelling']})
            changes.append(f'swap: "{s}" → "{x["jd_spelling"]}" (the JD\'s spelling)')
            break
    # skills added
    for x in terms:
        if x['truth'] != 'true' or found(x['jd_spelling'], page_text(t)):
            continue
        if x['jd_spelling'].lower() not in pool:
            continue
        comp_sp = [s for y in role['competencies'] if y['id'] == x['competency'] for k in y['keywords'] for s in [k['term']] + k.get('synonyms', [])]
        groups = t.get('skills') or []
        if not groups:
            continue
        ev = {sk.lower() for f in fb['facts'] if f['id'] in x['facts'] for sk in f.get('skills') or []}
        g = max(groups, key=lambda g: (sum(1 for it in g['items'] if it.lower() in ev),
                                       sum(1 for it in g['items'] if any(it.lower() == s.lower() for s in comp_sp)), -groups.index(g)))
        g['items'].append(x['jd_spelling'])
        changes.append(f'skill added: "{x["jd_spelling"]}" → {g["label"]} (true: {", ".join(x["facts"]) or "skills.true"})')
    # alternates from the reserve: only to bring a JD term onto the page, never at the cost of one
    wt = {c['id']: c.get('weight', 0) for c in role.get('competencies') or []}
    res = t.get('reserve') or []

    def terms_of(text):
        """JD terms the text holds in any spelling, plus ('exact', term) for those it holds in the JD's spelling — a reserve
        bullet that brings only the JD's spelling of a term the page says another way (trade-offs vs. prioritized) counts."""
        out = {x['term'] for x in terms if any(found(s, text) for s in x['spellings'])}
        return out | {('exact', x['term']) for x in terms if found(x['jd_spelling'], text)}

    def label(k):
        return f'"{k[1]}" in the JD\'s spelling' if isinstance(k, tuple) else k

    for ri, r in enumerate(list(res)):
        e = next((e for e in t['entries'] if e['entry_id'] == r['entry_id']), None)
        if not e or len(e['bullets']) < 2:
            continue
        new_terms = terms_of(r['text']) - terms_of(page_text(t))
        new_terms = {k for k in new_terms if not (isinstance(k, tuple) and k[1] in new_terms)}   # a new term already counts
        if not new_terms:
            continue
        cand = []
        for i in range(1, len(e['bullets'])):
            if DM.is_core(i, e['bullets'][i]):
                continue
            rest = copy.deepcopy(t)
            rest_e = next(x for x in rest['entries'] if x['entry_id'] == e['entry_id'])
            gone = rest_e['bullets'].pop(i)
            if terms_of(gone['text']) <= terms_of(page_text(rest)):   # nothing of the JD's is lost with it
                cand.append((max([wt.get(c, 0) for c in gone.get('competencies') or []] or [0]), -i, i))
        if not cand:
            continue
        _, _, i = min(cand)
        out = e['bullets'][i]
        e['bullets'][i] = {k: v for k, v in r.items() if k != 'entry_id'}
        res[ri] = dict(out, entry_id=e['entry_id'])
        changes.append(f'alternate ({e["entry_id"]}): "{r["text"][:50]}…" in for "{out["text"][:50]}…" '
                       f'(brings {", ".join(sorted(label(k) for k in new_terms))}; nothing lost)')
    # order
    for e in t['entries']:
        head = [b for i, b in enumerate(e['bullets']) if DM.is_core(i, b)]
        rest = [b for i, b in enumerate(e['bullets']) if not DM.is_core(i, b)]
        new = sorted(rest, key=lambda b: -hits_in(b['text'], terms))
        if head + new != e['bullets']:
            changes.append(f'order ({e["entry_id"]}): core bullets first, the others sorted by JD terms')
        e['bullets'] = head + new
    for g in t.get('skills') or []:
        new = sorted(g['items'], key=lambda it: -hits_in(it, terms))
        if new != g['items']:
            changes.append(f'order (skills / {g["label"]}): JD terms first')
        g['items'] = new
    # headline
    if title:
        hl = [x['jd_spelling'] for x in terms if x['truth'] == 'true' and x['jd_spelling'].lower() in pool
              and x['jd_spelling'].lower() not in title.lower()][:3]
        t['headline'] = ' · '.join([title] + hl)
        changes.append(f'headline: "{t["headline"]}"')
    after = page_text(t)
    for x in terms:
        x['after'] = 'exact' if found(x['jd_spelling'], after) else ('other spelling' if any(found(s, after) for s in x['spellings']) else 'no')
    return t, terms, changes


def coverage(terms, key):
    if not terms:
        return 0, 0, 0
    ex = sum(1 for x in terms if x[key] == 'exact')
    cov = sum(1 for x in terms if x[key] != 'no')
    return ex, cov, len(terms)


def keyword_map(terms, changes, company, title, direction, mpath, errs=None):
    b, a = coverage(terms, 'before'), coverage(terms, 'after')
    L = [f'# Keyword map — {company}, {title}', '',
         f'Tailored from the approved `{direction}` master (`{mpath}`) on {datetime.date.today().isoformat()} — mechanical '
         'changes only (tailor.py, JSA-251).', '',
         f'**Coverage of the top {b[2]} JD terms:** before {b[1]}/{b[2]} on the page ({b[0]} in the JD\'s exact spelling) → '
         f'after {a[1]}/{a[2]} ({a[0]} exact).', '',
         '| JD term (JD spelling) | Weight | Hits | True? | Facts | Before | After |', '| --- | --- | --- | --- | --- | --- | --- |']
    for x in terms:
        L.append(f"| {x['term']} ({x['jd_spelling']}) | {x['score']} | {x['hits']}{' · title' if x['in_title'] else ''} | "
                 f"{x['truth']} | {', '.join(x['facts']) or '—'} | {x['before']} | {x['after']} |")
    unph = [x for x in terms if x['truth'] == 'true' and x['after'] != 'exact']
    nott = [x for x in terms if x['truth'] != 'true']
    L += ['', '## Gaps — true but not phrased (the resume can say it only in approved wording)', '']
    L += [f"- **{x['jd_spelling']}** — true ({', '.join(x['facts']) or 'skills.true'}); the page " +
          ('uses another spelling' if x['after'] == 'other spelling' else 'does not say it') +
          '; a new sentence needs Joey\'s yes.' for x in unph] or ['- none']
    L += ['', '## Gaps — not true (never added)', '']
    L += [f"- **{x['jd_spelling']}** — {'confirmed not used' if x['truth'] == 'not used' else 'no fact shows it'}" for x in nott] or ['- none']
    L += ['', '## Changes', ''] + ([f'{i}. {c}' for i, c in enumerate(changes, 1)] or ['(none — the approved master as is)'])
    if errs:
        L += ['', '## Check failures (the approved master is used unchanged)', ''] + [f'- {e}' for e in errs]
    return '\n'.join(L) + '\n'


def order_of(role):
    so = role.get('section_order') or []
    return ['projects', 'exp'] if ('Projects' in so and 'Experience' in so and so.index('Projects') < so.index('Experience')) else ['exp', 'projects']


def run(jd, direction, fb, role, master, mpath, title, company, out_docx=None):
    """Tailor + check (+ layout when out_docx). → dict(ok, errs, tailored, swaps, terms, changes, res, keyword_map).
    res = direction_master.layout result (docx / pdf in a temp folder, cfg, bottom, extra, master) or None."""
    t, terms, changes = tailor(master, fb, role, jd, title, company)
    errs = TC.check_tailored(t, master, fb, direction, title)
    res = None
    if not errs and out_docx:
        import direction_master as DM
        res, lerr = DM.layout(t, fb, out_docx, order_of(role), {c['id']: c['weight'] for c in role['competencies']})
        if lerr:
            errs.append('layout: ' + lerr)
        else:
            for k in ('extra', 'dropped'):
                if res.get(k):
                    changes.append(f'layout {k}: {res[k]}')
    return dict(ok=not errs, errs=errs, tailored=(res['master'] if res else t), swaps=t['swaps'], terms=terms, changes=changes,
                res=res, keyword_map=keyword_map(terms, changes, company, title, direction, mpath, errs))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--jd', required=True)
    ap.add_argument('--direction', required=True)
    ap.add_argument('--title')
    ap.add_argument('--company')
    ap.add_argument('--out', help='output folder (default: the JD\'s folder)')
    ap.add_argument('--facts')
    ap.add_argument('--master', help='approved master json (default: newest approved in the data home)')
    ap.add_argument('--dry', action='store_true', help='keyword map and checks only, no layout')
    a = ap.parse_args(argv)
    import paths
    try:
        jd = open(a.jd, encoding='utf-8').read()
        fb = json.load(open(a.facts or paths.config('facts.json'), encoding='utf-8'))
        role = json.load(open(paths.role_file(f'{a.direction}.json'), encoding='utf-8'))
    except OSError as ex:
        print(f'tailor: {ex}')
        return 2
    if a.master:
        d = json.load(open(a.master, encoding='utf-8'))
        master, mpath = (d.get('master') if d.get('approved') else None), a.master
    else:
        master, mpath = approved_master(a.direction)
    if not master:
        print(f'tailor: no approved {a.direction} master (direction_master.py, then the user\'s approval)')
        return 2
    t0, c0 = parse_jd(jd, os.path.dirname(os.path.abspath(a.jd)))
    title, company = a.title or t0, a.company or c0
    out = a.out or os.path.dirname(os.path.abspath(a.jd))
    os.makedirs(out, exist_ok=True)
    out_docx = None
    if not a.dry:
        import tempfile
        sys.path.insert(0, os.path.join(REPO, 'skills', 'auto-apply', 'scripts'))
        import ds_materials as D
        name = f"{D.FILE_PREFIX}_Resume_{re.sub(r'[^A-Za-z0-9]+', '_', company + '_' + title).strip('_')[:80]}_A-Classic"
        out_docx = os.path.join(tempfile.mkdtemp(prefix='tailor_'), name + '.docx')
    r = run(jd, a.direction, fb, role, master, mpath, title, company, out_docx)
    open(os.path.join(out, 'keyword_map.md'), 'w', encoding='utf-8').write(r['keyword_map'])
    if not r['ok']:
        for e in r['errs']:
            print(e)
        print(f'tailor: {len(r["errs"])} check failure(s) — use the approved master unchanged; see keyword_map.md')
        return 1
    rec = dict(tailored=dict(r['tailored'], swaps=r['swaps']), changes=r['changes'], terms=r['terms'], direction=a.direction,
               approved=mpath, built=datetime.date.today().isoformat())
    res = r['res']
    if res:
        for k in ('docx', 'pdf'):
            dst = os.path.join(out, os.path.basename(res[k]))
            shutil.copyfile(res[k], dst)
            rec[k] = dst
        rec['bottom'] = res['bottom']
    json.dump(rec, open(os.path.join(out, 'tailored.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    b, af = coverage(r['terms'], 'before'), coverage(r['terms'], 'after')
    print(f'tailor: {company} — {title} · terms {len(r["terms"])} · on the page {b[1]}→{af[1]} (exact {b[0]}→{af[0]}) · '
          f'{len(r["changes"])} change(s)' + (f' · bottom {res["bottom"]} → {rec["pdf"]}' if res else ' (dry)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
