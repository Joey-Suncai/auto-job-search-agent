#!/usr/bin/env python3
"""Build the shared role library from cached JDs (ADR-0010 / JSA-249): roles/<direction>.json per direction.

    python3 role_library.py --all                    # every direction in roles/directions.json
    python3 role_library.py --direction ai_pm        # one direction
    python3 role_library.py --all --discover         # + DeepSeek proposes JD terms the lexicon misses (cached)

Inputs: the data home's data/store/jobs.jsonl (track, title, dup_of) and data/processed/jds_gate_*.jsonl (full JD text,
later files win); roles/lexicon.json (competency → keyword groups, first term canonical) and roles/directions.json
(selector + resume choices per direction). A new direction = a selector in directions.json (20–50 JDs are enough with
--min-jds 20), then rerun. Rebuild monthly; the output records the JD ids it was built from.

How the numbers are made (no model in the counting):
- A JD is split at the first "preferred / nice to have / bonus / a plus / desired" marker: before = required part.
- keyword df = share of the direction's JDs that mention any spelling of the keyword; req_share = share of those
  mentions that fall in the required part.
- competency df = share of JDs that mention any of its keywords; score = df × (0.5 + 0.5 × req_share); weights =
  scores normalized over competencies with df ≥ 0.05 (rarer ones get weight 0).
- --discover: DeepSeek reads up to 30 sample JDs (5 per call) and lists requirement phrases; the script keeps the ones
  no lexicon term covers (multi-word or acronym / tool-like tokens only) and counts their df over all the direction's JDs itself; df ≥ 0.08 → uncovered_terms (add the
  good ones to lexicon.json, then rebuild). DeepSeek only proposes; it never sets a weight.
Exit 1 when a direction has fewer JDs than --min-jds (default 50).
"""
import argparse
import collections
import datetime
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL))
ROLES = os.path.join(SKILL, 'roles')
sys.path.insert(0, os.path.join(REPO, 'config'))

PREF = re.compile(r'\b(preferred|nice[- ]to[- ]haves?|bonus points?|bonus|a plus|pluses|desired|desirable)\b', re.I)


def term_of(t):
    return t['t'] if isinstance(t, dict) else t


def matcher(t):
    """A compiled regex for one lexicon term. Case-insensitive on word boundaries; {"t": .., "cs": true} = case-sensitive.
    Boundaries also refuse '&' and '+' next to the term so 'R' does not match 'R&D' and 'C' would not match 'C++'."""
    s = term_of(t)
    cs = isinstance(t, dict) and t.get('cs')
    pat = r'(?<![\w&+/])' + re.escape(s) + r'(?![\w&+])'
    return re.compile(pat, 0 if cs else re.I)


def split_req(text):
    """(required part, preferred part) — split at the first preferred-type marker; no marker = all required."""
    m = PREF.search(text or '')
    return (text, '') if not m else (text[:m.start()], text[m.start():])


def compile_lexicon(lex):
    """{competency id: {label, groups: [(canonical, synonyms, matchers)]}}; the lexicon's "ignore" list rides along under
    the key "_ignore" (lower-case strings) for covered()."""
    out = {}
    for cid, c in lex['competencies'].items():
        out[cid] = {'label': c.get('label', cid),
                    'groups': [(term_of(g[0]), [term_of(x) for x in g[1:]], [matcher(x) for x in g]) for g in c['keywords'] if g]}
    if lex.get('ignore'):
        out['_ignore'] = {'label': '', 'groups': [], 'words': {x.lower() for x in lex['ignore']}}
    return out


def covered(phrase, comp):
    """True when some lexicon term matches inside the phrase or the phrase is a lexicon term."""
    p = phrase.lower()
    ign = (comp.get('_ignore') or {}).get('words') or set()
    if p in ign or p.rstrip('s') in ign:
        return True
    for c in comp.values():
        for canon, syn, ms in c['groups']:
            if any(m.search(phrase) for m in ms) or p in [canon.lower()] + [s.lower() for s in syn]:
                return True
    return False


def stats(texts, comp, min_df=0.05):
    """Competency and keyword statistics over a list of JD texts (see the module doc)."""
    n = len(texts)
    parts = [split_req(t) for t in texts]
    comps = []
    for cid, c in comp.items():
        if cid == '_ignore':
            continue
        c_req, c_any = set(), set()
        kws = []
        for canon, syn, ms in c['groups']:
            req = {i for i, (r, _) in enumerate(parts) if any(m.search(r) for m in ms)}
            pref = {i for i, (_, p) in enumerate(parts) if p and any(m.search(p) for m in ms)}
            hit = req | pref
            c_req |= req
            c_any |= hit
            kws.append({'term': canon, 'synonyms': syn, 'df': round(len(hit) / n, 3) if n else 0,
                        'req_share': round(len(req) / len(hit), 3) if hit else 0})
        df = len(c_any) / n if n else 0
        rs = len(c_req) / len(c_any) if c_any else 0
        kws.sort(key=lambda k: (-k['df'], k['term']))
        comps.append({'id': cid, 'label': c['label'], 'df': round(df, 3), 'req_share': round(rs, 3),
                      'score': df * (0.5 + 0.5 * rs) if df >= min_df else 0.0, 'keywords': kws})
    tot = sum(c['score'] for c in comps) or 1
    for c in comps:
        c['weight'] = round(c.pop('score') / tot, 4)
    comps.sort(key=lambda c: (-c['weight'], -c['df'], c['id']))
    top = [{'term': k['term'], 'competency': c['id'], 'df': k['df'], 'req_share': k['req_share'],
            'score': round(k['df'] * (0.5 + 0.5 * k['req_share']), 4)}
           for c in comps for k in c['keywords'] if k['df'] >= min_df]
    top.sort(key=lambda k: (-k['score'], k['term']))
    return comps, top[:30]


def specific(phrase):
    """A discovered phrase worth listing: two or more words, an all-caps acronym of 3+ letters (CRM, SQL), or one token
    with an inner capital or digit (SaaS, PyTorch, S3). Single plain words ('product', 'AI', 'Engineering') are too
    generic to be resume keywords."""
    w = phrase.split()
    if len(w) >= 2:
        return True
    t = w[0] if w else ''
    if t.isupper():
        return len(t) >= 3
    return any(ch.isupper() for ch in t[1:]) or any(ch.isdigit() for ch in t)


def select(jobs, texts, selector):
    """JD ids for a direction: rows with text, not duplicates, whose track is listed — or, for or_tracks_with_text,
    whose track is listed there and whose JD text has ≥ min_hits matches of its regex."""
    tracks = set(selector.get('tracks') or [])
    alt = selector.get('or_tracks_with_text') or {}
    alt_tracks = set(alt.get('tracks') or [])
    rx = re.compile(alt['regex'], re.I) if alt.get('regex') else None
    title_rx = re.compile(selector['title_regex'], re.I) if selector.get('title_regex') else None
    ids = []
    for j in jobs:
        jid = j.get('id')
        if not jid or jid not in texts or j.get('dup_of'):
            continue
        t = j.get('track')
        ok = t in tracks
        if not ok and t in alt_tracks and rx is not None:
            ok = len(rx.findall(texts[jid])) >= int(alt.get('min_hits', 1))
        if ok and title_rx is not None and not title_rx.search(j.get('title') or ''):
            ok = False
        if ok:
            ids.append(jid)
    return sorted(set(ids))


def load_corpus():
    import paths
    texts = {}
    for p in sorted(glob.glob(paths.data('processed', 'jds_gate_*.jsonl'))):
        with open(p, encoding='utf-8') as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get('id') and len(d.get('text') or '') >= 400:
                    texts[d['id']] = d['text']
    with open(paths.data('store', 'jobs.jsonl'), encoding='utf-8') as f:
        jobs = [json.loads(line) for line in f if line.strip()]
    return jobs, texts


DISCOVER_SYS = """You read job descriptions and list what they ask of the candidate: skills, tools, methods, domain
knowledge and qualifications, each as a short noun phrase of 1-4 words exactly as written in the JD (no sentences, no
company names, no benefits, no locations). Return JSON: {"terms": ["...", ...]} with the union over all JDs given."""


def discover(ids, texts, comp, cache_path, usage):
    sample = ids[::max(1, len(ids) // 30)][:30]
    key = hashlib.sha1(','.join(sample).encode()).hexdigest()[:16]
    cache = {}
    if os.path.exists(cache_path):
        try:
            cache = json.load(open(cache_path, encoding='utf-8'))
        except ValueError:
            cache = {}
    if key in cache:
        phrases = cache[key]
    else:
        sys.path.insert(0, os.path.join(REPO, 'skills', 'auto-apply', 'runner'))
        import ladder
        phrases = []
        for i in range(0, len(sample), 5):
            block = '\n\n'.join(f'JD {k + 1}:\n{texts[j][:3000]}' for k, j in enumerate(sample[i:i + 5]))
            res = ladder.ask_deepseek(block, usage, system=DISCOVER_SYS)
            phrases += [str(x).strip() for x in res.get('terms') or [] if str(x).strip()]
        cache[key] = phrases
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
    seen, out = set(), []
    corpus = [texts[j] for j in ids]
    for p in phrases:
        k = p.lower()
        if k in seen or len(k) < 2 or len(k.split()) > 4 or not specific(p) or covered(p, comp):
            continue
        seen.add(k)
        m = matcher(p)
        df = sum(1 for t in corpus if m.search(t)) / len(corpus)
        if df >= 0.08:
            out.append({'term': p, 'df': round(df, 3)})
    out.sort(key=lambda x: (-x['df'], x['term']))
    return out[:30]


def build(name, d, jobs, texts, comp, min_jds, do_discover):
    ids = select(jobs, texts, d['selector'])
    if len(ids) < min_jds:
        return None, f'{name}: only {len(ids)} JDs (need {min_jds})'
    comps, top = stats([texts[j] for j in ids], comp)
    angles = d.get('angles') or {}
    for c in comps:
        c['angle'] = angles.get(c['id'], '')
    by_id = {j['id']: j for j in jobs}
    out = {'direction': name, 'label': d.get('label', name), 'built': datetime.date.today().isoformat(),
           'n_jds': len(ids), 'levels': dict(collections.Counter(by_id[j].get('level') or '?' for j in ids)),
           'tracks': dict(collections.Counter(by_id[j].get('track') or '?' for j in ids)),
           'template': d.get('template'), 'section_order': d.get('section_order'), 'headline_pattern': d.get('headline_pattern'),
           'competencies': comps, 'top_keywords': top, 'uncovered_terms': [], 'jd_ids': ids}
    if do_discover:
        import paths
        usage = {'calls': 0, 'prompt': 0, 'out': 0}
        out['uncovered_terms'] = discover(ids, texts, comp, paths.data('processed', 'role_discover_cache.json'), usage)
        out['discover_usage'] = usage
    return out, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--direction', action='append')
    g.add_argument('--all', action='store_true')
    ap.add_argument('--discover', action='store_true')
    ap.add_argument('--min-jds', type=int, default=50)
    ap.add_argument('--out-dir', default=None, help='default: <data home>/data/roles (JSA-377)')
    a = ap.parse_args(argv)
    import paths
    a.out_dir = a.out_dir or paths.data('roles')
    os.makedirs(a.out_dir, exist_ok=True)
    lex = json.load(open(os.path.join(ROLES, 'lexicon.json'), encoding='utf-8'))
    dirs = json.load(open(os.path.join(ROLES, 'directions.json'), encoding='utf-8'))['directions']
    names = list(dirs) if a.all else a.direction
    unknown = [n for n in names if n not in dirs]
    if unknown:
        print(f'role_library: unknown direction(s) {unknown}; known: {sorted(dirs)}')
        return 2
    comp = compile_lexicon(lex)
    jobs, texts = load_corpus()
    rc = 0
    for n in names:
        out, err = build(n, dirs[n], jobs, texts, comp, a.min_jds, a.discover)
        if err:
            print(err)
            rc = 1
            continue
        path = os.path.join(a.out_dir, f'{n}.json')
        json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        top = ', '.join(f"{c['label']} {c['weight']:.2f}" for c in out['competencies'][:6])
        extra = f" · uncovered {len(out['uncovered_terms'])}" if a.discover else ''
        print(f'{n}: {out["n_jds"]} JDs → {os.path.relpath(path, REPO)} · top: {top}{extra}')
    return rc


if __name__ == '__main__':
    sys.exit(main())
