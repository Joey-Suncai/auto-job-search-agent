#!/usr/bin/env python3
"""Check the candidate's fact base (config/facts.json, ADR-0010 / JSA-248) and that every approved bullet traces to it.

    python3 facts_check.py                       # the data home's config/facts.json + facts/bullet-bank.md
    python3 facts_check.py --facts F --bank B    # other files (tests, the fictional example)
    python3 facts_check.py --map                 # also print bullet → fact ids

Exit 0 = clean, 1 = problems (each printed as one line), 2 = a file is missing or not JSON.

What it checks
1. Schema: every entry has id / kind / org / role / dates; every fact has id (unique) / entry (exists) / A (non-empty) /
   skills / anchors (non-empty lists) / numbers (list) / source (non-empty).
2. A fact's `numbers` all appear in its own S / T / A / R text — the list cannot drift from the story.
3. Every bullet in the bank (one `## <org>` section per entry) maps to ≥ 1 fact of that entry: a fact maps when one of
   its anchors appears in the bullet (case-insensitive).
4. Every number in a bullet appears in the mapped facts (their numbers or S / T / A / R text, or a `history` entry —
   {as_of, A, R, numbers}: what was true at an earlier date). A number no mapped fact holds is a truth problem; a number
   held only by history is printed as WARN stale (true then, not now) and does not fail.
5. No bullet contains a `never` phrase of its entry or of a mapped fact (e.g. "independently" for a team project).
The same helpers (`load`, `bank_bullets`, `map_bullet`, `numbers_in`, `unsupported_numbers`, `never_hits`) are what the
later truth check (JSA-251) builds on.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, 'config'))

ENTRY_KEYS = ('id', 'kind', 'org', 'role', 'dates')
KINDS = {'education', 'experience', 'project', 'leadership'}

# a number: optional currency, digits with , or . inside, optional % / + ; ranges like 0–5 or 2017–2018 are two numbers
NUM = re.compile(r'[¥$€£]?\d[\d,]*(?:\.\d+)?[%+]?')


def norm_num(tok):
    """'1,886' → '1886', '70%' → '70', '¥10,000' → '10000', '2.169' → '2.169'. Trailing '.0' is not stripped."""
    t = re.sub(r'[¥$€£%+,]', '', tok)
    return t.rstrip('.')


def numbers_in(text):
    """The normalized numbers in a text, in order (duplicates kept)."""
    return [norm_num(m.group(0)) for m in NUM.finditer(text or '') if norm_num(m.group(0))]


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def fact_text(f):
    return ' '.join(str(f.get(k) or '') for k in ('S', 'T', 'A', 'R'))


def check_schema(fb):
    errs = []
    entries = fb.get('entries')
    facts = fb.get('facts')
    if not isinstance(entries, list) or not entries:
        return ['schema: "entries" must be a non-empty list']
    if not isinstance(facts, list) or not facts:
        return ['schema: "facts" must be a non-empty list']
    eids = set()
    for i, e in enumerate(entries):
        for k in ENTRY_KEYS:
            if not str(e.get(k) or '').strip() and not (k == 'dates' and e.get(k) == ''):
                errs.append(f'entry #{i} ({e.get("id")}): missing {k}')
        if e.get('kind') and e['kind'] not in KINDS:
            errs.append(f'entry {e.get("id")}: kind {e["kind"]!r} not one of {sorted(KINDS)}')
        if e.get('id') in eids:
            errs.append(f'entry {e.get("id")}: duplicate id')
        eids.add(e.get('id'))
    fids = set()
    for i, f in enumerate(facts):
        fid = f.get('id') or f'#{i}'
        if not f.get('id'):
            errs.append(f'fact #{i}: missing id')
        elif f['id'] in fids:
            errs.append(f'fact {fid}: duplicate id')
        fids.add(f.get('id'))
        if f.get('entry') not in eids:
            errs.append(f'fact {fid}: entry {f.get("entry")!r} does not exist')
        if not str(f.get('A') or '').strip():
            errs.append(f'fact {fid}: empty A (what he did)')
        if not str(f.get('source') or '').strip():
            errs.append(f'fact {fid}: no source')
        for k in ('skills', 'anchors'):
            if not isinstance(f.get(k), list) or not [x for x in f.get(k) or [] if str(x).strip()]:
                errs.append(f'fact {fid}: {k} must be a non-empty list')
        if not isinstance(f.get('numbers', []), list):
            errs.append(f'fact {fid}: numbers must be a list')
        else:
            have = set(numbers_in(fact_text(f)))
            for n in f.get('numbers') or []:
                for x in numbers_in(str(n)):
                    if x not in have:
                        errs.append(f'fact {fid}: number {n!r} is not in its S/T/A/R text')
    return errs


def bank_bullets(path):
    """[(section heading, bullet text)] from bullet-bank.md: '## <org>' sections, '- ' bullets (tag lines skipped)."""
    out, sec = [], None
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.rstrip('\n')
            if s.startswith('## '):
                sec = s[3:].strip()
            elif sec and s.startswith('- '):
                out.append((sec, s[2:].strip()))
    return out


def _words(s):
    return set(re.findall(r'[a-z0-9]+', s.lower())) - {'the', 'of', 'and', 'inc', 'u', 's'}


def entry_for(section, entries):
    """The entry whose org matches a bank section heading: exact (case-insensitive), else most shared words (≥ 2)."""
    for e in entries:
        if e['org'].lower() == section.lower():
            return e
    best, score = None, 1
    for e in entries:
        n = len(_words(e['org']) & _words(section))
        if n > score:
            best, score = e, n
    return best


def map_bullet(text, entry_id, facts):
    t = text.lower()
    return [f for f in facts if f.get('entry') == entry_id
            and any(str(a).lower() in t for a in f.get('anchors') or [] if str(a).strip())]


def _nums(f):
    have = set(numbers_in(fact_text(f)))
    for n in f.get('numbers') or []:
        have.update(numbers_in(str(n)))
    return have


def _hist_nums(f):
    have = set()
    for h in f.get('history') or []:
        have.update(numbers_in(f"{h.get('A') or ''} {h.get('R') or ''}"))
        for n in h.get('numbers') or []:
            have.update(numbers_in(str(n)))
    return have


def unsupported_numbers(text, mapped):
    """Bullet numbers no mapped fact holds now or in its history."""
    have = set()
    for f in mapped:
        have |= _nums(f) | _hist_nums(f)
    return [n for n in numbers_in(text) if n not in have]


def stale_numbers(text, mapped):
    """Bullet numbers held only by a mapped fact's history (true as of an earlier date, not the current value)."""
    now, old = set(), set()
    for f in mapped:
        now |= _nums(f)
        old |= _hist_nums(f)
    return [n for n in numbers_in(text) if n not in now and n in old]


def never_hits(text, entry, mapped):
    t = text.lower()
    phrases = list(entry.get('never') or [])
    for f in mapped:
        phrases += f.get('never') or []
    return sorted({p for p in phrases if p and re.search(r'(?<![a-z])' + re.escape(p.lower()) + r'(?![a-z])', t)})


def check_bank(fb, bank_path, warns=None):
    """(errors, mapping); stale-number notes go to `warns` (a list) when given — they never fail the check."""
    warns = [] if warns is None else warns
    errs, mapping = [], []
    entries, facts = fb['entries'], fb['facts']
    for sec, b in bank_bullets(bank_path):
        e = entry_for(sec, entries)
        short = b if len(b) <= 70 else b[:67] + '...'
        if not e:
            errs.append(f'bank section {sec!r}: no entry in facts.json matches')
            continue
        mapped = map_bullet(b, e['id'], facts)
        mapping.append((sec, b, [f['id'] for f in mapped]))
        if not mapped:
            errs.append(f'bullet maps to no fact ({e["id"]}): {short}')
            continue
        for n in unsupported_numbers(b, mapped):
            errs.append(f'bullet number {n} not in facts {[f["id"] for f in mapped]}: {short}')
        st = stale_numbers(b, mapped)
        if st:
            warns.append(f'stale (history only): {", ".join(st)} in: {short}')
        for p in never_hits(b, e, mapped):
            errs.append(f'bullet uses never-phrase {p!r}: {short}')
    return errs, mapping


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--facts', help='facts.json (default: the data home config/facts.json)')
    ap.add_argument('--bank', help='bullet-bank.md (default: the data home facts/bullet-bank.md, paths.fact)')
    ap.add_argument('--map', action='store_true', help='print bullet → fact ids')
    a = ap.parse_args(argv)
    if not a.bank:
        import paths
        a.bank = paths.fact('bullet-bank.md')
    path = a.facts
    if not path:
        import paths
        path = paths.config('facts.json')
    try:
        fb = load(path)
    except (OSError, ValueError) as ex:
        print(f'facts_check: cannot read {path}: {ex}')
        return 2
    errs = check_schema(fb)
    mapping, warns = [], []
    if not errs:
        if not os.path.exists(a.bank):
            print(f'facts_check: no bank at {a.bank}')
            return 2
        e2, mapping = check_bank(fb, a.bank, warns)
        errs += e2
    if a.map:
        for sec, b, ids in mapping:
            print(f'{",".join(ids) or "-":32} {b[:90]}')
    for w in warns:
        print('WARN', w)
    for e in errs:
        print(e)
    n_b = len(mapping)
    print(f'facts_check: {len(fb.get("facts") or [])} facts, {n_b} bullets checked, {len(errs)} problem(s), {len(warns)} stale')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
