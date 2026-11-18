#!/usr/bin/env python3
"""Truth check for job-tailored materials (JSA-251, ADR-0010 ⑤): every sentence traces to the candidate's facts.

    python3 truth_check.py --tailored T.json --approved master_ai_pm.json [--direction ai_pm]   # a tailored master
    python3 truth_check.py --text cover.txt [--jd jd.md]                                         # free text (letter)

Exit 0 = clean, 1 = problems (one line each), 2 = a file is missing.

Tailored master mode (`check_tailored`) — the tailored master must be the approved direction master changed only
mechanically (spec ④: order, alternates from its reserve, term swaps inside one lexicon cluster):
- every direction_master.check() rule (fact ids, current numbers, never-phrases, pairs, STAR, skills truth, bold,
  bullet rules);
- new_sentence — a bullet whose text is neither an approved bullet / reserve bullet nor one after undoing the listed
  swaps (`swaps`: [{from, to}]); a new sentence needs the user's yes before use outside a dry run;
- swap_not_variant — a listed swap whose two spellings are not variants (same words up to case / hyphens / a plural
  "s", or an acronym and its expansion) of one lexicon cluster, or that changes the grammatical number (singular ↔
  plural breaks the sentence: "a review workflow" → "a review workflows");
- fact_ids_changed — a bullet that cites other facts than the approved bullet it came from;
- entry_moved — a bullet placed under another entry than in the approved master;
- core_dropped — a core bullet of the approved master (an entry's first, or marked "core": true) missing from its
  entry, as itself or with the listed swaps;
- summary_changed — a summary that differs from the approved one;
- headline_term — a headline term (after the job title, split on " · ") that is neither the job title, a fixed part
  of the approved headline, nor a true skill (skills.true or a resume fact's skills, case-insensitive);
- skill_added_untrue — a skills item not in skills.true / resume facts' skills (also reported by check()).

Text mode (`check_text`) — for a cover letter or any prose, sentence by sentence:
- number — a number that is in no resume fact (current or history), no entry's org / role / dates, not in the
  candidate's form answers (config/profile.json, e.g. a 12-week availability) and not in the JD text; phone
  numbers, e-mail addresses and URLs are skipped;
- never — any entry's or fact's never-phrase (whole phrase, case-insensitive), anywhere;
- pair — a sentence about a fact (one of its anchors, or a pair head holding a number such as "70%") that holds the
  pair head without its partner ("workflow");
- banned — a banned buzzword (check_resume.py list), unless the JD uses the same word (a company name).
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_bullets as CB  # noqa: E402
import facts_check as FC  # noqa: E402

ROLES = os.path.join(os.path.dirname(HERE), 'roles')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import paths  # noqa: E402  (generated role library: data home first, JSA-377)


def _load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def _words(s):
    return re.sub(r'[-‐–_/]', ' ', s.lower()).split()


def _sing(w):
    return w[:-1] if len(w) > 3 and w.endswith('s') and not w.endswith('ss') else w


def is_variant(a, b):
    """Same words up to case, hyphens and a plural "s" — or an acronym and its expansion (initials of the words)."""
    wa, wb = [_sing(w) for w in _words(a)], [_sing(w) for w in _words(b)]
    if wa == wb:
        return True
    for x, y in ((a, b), (b, a)):
        m = re.fullmatch(r'([A-Z]{2,6})s?', x.strip())
        if m and len(_words(y)) >= 2:
            init = ''.join(w[0] for w in _words(y) if w not in ('and', 'of', 'the', 'for'))
            if init == m.group(1).lower():
                return True
    return False


def clusters(direction):
    """[[spellings]] of the direction's keyword groups (term + synonyms)."""
    if not direction:
        return []
    p = paths.role_file(f'{direction}.json')
    if not os.path.exists(p):
        return []
    return [[k['term']] + list(k.get('synonyms') or []) for c in _load(p)['competencies'] for k in c['keywords']]


def _plural(x):
    w = _words(x)
    return bool(w) and (w[-1].endswith('s') and not w[-1].endswith('ss') or bool(re.fullmatch(r'[A-Z]{2,6}s', x.strip())))


def is_bullet_variant(a, b):
    """A swap allowed inside a sentence: a variant (is_variant) that keeps the grammatical number ("workflow" →
    "workflows" would break "a review workflow")."""
    return is_variant(a, b) and _plural(a) == _plural(b)


def same_cluster(a, b, cl):
    la, lb = a.lower(), b.lower()
    return any(la in {x.lower() for x in g} and lb in {x.lower() for x in g} for g in cl)


def true_pool(fb):
    pool = set()
    for v in (fb.get('skills') or {}).get('true', {}).values():
        pool |= {x.lower() for x in v}
    for f in fb['facts']:
        if f.get('resume_ok', True) is not False:
            pool |= {x.lower() for x in f.get('skills') or []}
    return pool


def _undo(text, swaps):
    for s in swaps:
        text = re.sub(re.escape(s['to']), s['from'], text, flags=re.I)
    return text


def check_tailored(t, approved, fb, direction=None, title=None):
    """Problems for a tailored master `t` against the approved master `approved` (both master dicts)."""
    import direction_master as DM
    errs = list(DM.check(t, fb, direction))
    cl = clusters(direction)
    swaps = t.get('swaps') or []
    for s in swaps:
        if not (is_bullet_variant(s.get('from', ''), s.get('to', '')) and (same_cluster(s['from'], s['to'], cl) or not cl)):
            errs.append(f'swap_not_variant — "{s.get("from")}" → "{s.get("to")}" is not a same-number spelling variant within one keyword cluster')
    src = {}
    for e in approved.get('entries') or []:
        for b in e['bullets']:
            src[b['text']] = (e['entry_id'], sorted(b.get('fact_ids') or []))
    for r in approved.get('reserve') or []:
        src[r['text']] = (r['entry_id'], sorted(r.get('fact_ids') or []))
    for e in t.get('entries') or []:
        for b in e.get('bullets') or []:
            base = b['text'] if b['text'] in src else _undo(b['text'], swaps)
            if base not in src:
                errs.append(f'{e.get("entry_id")}: new_sentence — not an approved bullet (needs the user\'s yes) — {b["text"][:70]}')
                continue
            eid, ids = src[base]
            if eid != e.get('entry_id'):
                errs.append(f'{e.get("entry_id")}: entry_moved — approved under {eid} — {b["text"][:60]}')
            if sorted(b.get('fact_ids') or []) != ids:
                errs.append(f'{e.get("entry_id")}: fact_ids_changed — {sorted(b.get("fact_ids") or [])} vs approved {ids} — {b["text"][:50]}')
    have = {e.get('entry_id'): {b['text'] for b in e.get('bullets') or []} | {_undo(b['text'], swaps) for b in e.get('bullets') or []}
            for e in t.get('entries') or []}
    for e in approved.get('entries') or []:
        for i, b in enumerate(e['bullets']):
            if DM.is_core(i, b) and b['text'] not in have.get(e['entry_id'], set()):
                errs.append(f'{e["entry_id"]}: core_dropped — a core bullet of the approved master is missing — {b["text"][:60]}')
    if (t.get('summary') or '') != (approved.get('summary') or '') and _undo(t.get('summary') or '', swaps) != (approved.get('summary') or ''):
        errs.append('summary_changed — the summary differs from the approved master (needs the user\'s yes)')
    pool = true_pool(fb)
    fixed = {p.strip().lower() for p in (approved.get('headline') or '').split('·')}
    parts = [p.strip() for p in (t.get('headline') or '').split('·') if p.strip()]
    for i, p in enumerate(parts):
        if i == 0 and (title is None or p.lower() == title.lower()):
            continue
        if p.lower() in fixed or p.lower() in pool or (title and p.lower() == title.lower()):
            continue
        if re.fullmatch(r'(Summer|Fall|Spring|Winter) 20\d\d', p):
            continue
        errs.append(f'headline_term — "{p}" is not a true skill or part of the approved headline')
    for s in t.get('skills') or []:
        for it in s.get('items') or []:
            if it.lower() not in pool:
                errs.append(f'skill_added_untrue — "{it}"')
    return errs


SKIP = re.compile(r'\S+@\S+|https?://\S+|\b[\w.-]+\.(?:com|edu|org|io)\S*|\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}')


def check_text(text, fb, jd='', profile=''):
    """profile = the candidate's form answers (config/profile.json as text): availability, dates … count as facts."""
    errs = []
    allowed = set()
    for f in fb['facts']:
        if f.get('resume_ok', True) is not False:
            allowed |= FC._nums(f) | FC._hist_nums(f)
    for e in fb['entries']:
        allowed |= set(FC.numbers_in(' '.join(str(e.get(k) or '') for k in ('org', 'role', 'dates'))))
    allowed |= set(FC.numbers_in(jd or '')) | set(FC.numbers_in(profile or ''))
    never = sorted({p for e in fb['entries'] for p in e.get('never') or []} | {p for f in fb['facts'] for p in f.get('never') or []})
    pairs = [(a, b, f) for f in fb['facts'] for a, b in f.get('pairs') or []]
    body = SKIP.sub(' ', text)
    for s in re.split(r'(?<=[.!?])\s+|\n+', body):
        s = s.strip()
        if not s:
            continue
        low = s.lower()
        for n in FC.numbers_in(s):
            if n not in allowed:
                errs.append(f'number {n} is in no fact — {s[:70]}')
        for p in never:
            if re.search(r'(?<![a-z])' + re.escape(p.lower()) + r'(?![a-z])', low):
                errs.append(f'never-phrase "{p}" — {s[:70]}')
        for a, b, f in pairs:   # only for a sentence about that fact (one of its anchors or its pair head with a number)
            about = any(str(x).lower() in low for x in f.get('anchors') or []) or (re.search(r'\d', a) and a.lower() in low)
            if about and a.lower() in low and b.lower() not in low:
                errs.append(f'pair: "{a}" needs "{b}" (fact {f["id"]}) — {s[:70]}')
        for w in CB.BANNED:   # a banned word that the JD itself uses (a company name such as "a Lever employer") is not flagged
            if re.search(rf'\b{re.escape(w)}\b', low) and not re.search(rf'\b{re.escape(w)}\b', (jd or '').lower()):
                errs.append(f'banned: {w} — {s[:60]}')
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--tailored')
    ap.add_argument('--approved')
    ap.add_argument('--direction')
    ap.add_argument('--title')
    ap.add_argument('--text')
    ap.add_argument('--jd')
    ap.add_argument('--facts')
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), 'config'))
    try:
        if a.facts:
            fb = _load(a.facts)
        else:
            import paths
            fb = _load(paths.config('facts.json'))
        if a.text:
            jd = open(a.jd, encoding='utf-8').read() if a.jd else ''
            try:
                import paths
                prof = open(paths.config('profile.json'), encoding='utf-8').read()
            except Exception:
                prof = ''
            errs = check_text(open(a.text, encoding='utf-8').read(), fb, jd, prof)
        elif a.tailored and a.approved:
            t, ap_ = _load(a.tailored), _load(a.approved)
            t = t.get('tailored') or t.get('master') or t
            ap_ = ap_.get('master') or ap_
            errs = check_tailored(t, ap_, fb, a.direction, a.title)
        else:
            ap.error('give --tailored + --approved, or --text')
    except OSError as ex:
        print(f'truth_check: {ex}')
        return 2
    for e in errs:
        print(e)
    print(f'truth_check: {len(errs)} problem(s)')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
