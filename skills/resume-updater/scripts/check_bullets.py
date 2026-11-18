#!/usr/bin/env python3
"""Check resume bullets against the bullet rules (JSA-250; Joey 2026-11-08, after studying a peer's resume):

  quantified bullet (holds a number)  = what was done + why (purpose / situation) + impact (the number)
  unquantified bullet (no number)     = the problem + how it was solved
  every bullet: an action verb is its first word (Joey 2026-11-09, as in the peer resume: never "To …, ", "Because …, ",
  "When …, " first — the purpose goes after the action as " to …"); sentence shapes vary in the middle and the end.

    python3 check_bullets.py master.json          # a direction master (entries[].bullets[].text)
    python3 check_bullets.py --text "…"           # one bullet

Rules per bullet (each failure is one problem line, exit 1):
- opener   — the bullet opens with a context phrase (2–16 words before the first comma / colon, first word in
             CONTEXT_OPENERS, e.g. "To spend …, ", "Because …, ", "When …, ", "Asked by …, "): not allowed.
- verb     — (when no opener problem) the first word is an action verb: in VERBS, or a past-tense word ending in "ed"
             (longer than 3 letters, not in NOT_VERBS).
- why      — quantified bullets only: a reason / purpose is stated after the action — a marker in WHY_MARKERS
             (" to <verb>", "so that", "so ", "enabling", "allowing", "to meet", "for ", "when ", "after ").
- problem  — unquantified bullets only: the problem is stated — a marker in PROBLEM_MARKERS
             ("when", "found", "mismatch", "disagree", "inconsistent", "scattered", "slow", "wrong", "invent",
             "without", "gap", "error", "duplicate", "unclear", "manual").
- causal   — no "because" / "since" (not before a year) / "due to" / "owing to" clause (Joey 2026-11-09): the reason is
             said as a purpose (" to …", "so …") or shown by the result.
- length   — ≤ 230 characters (≈ two lines in A-Classic; check_resume.py measures the real lines).
- banned   — no banned buzzword (same list as check_resume.py).
Shape of a bullet (for variety; all open with the verb): verb_semicolon (two clauses joined by ";") · verb_participle
(a clause ", <word>ing …" carries the result) · verb_purpose (" to <verb>" purpose after the action) · verb_plain.
Per entry: ≤ 5 bullets; outcome first (Joey 2026-11-09) — when any bullet of an entry holds a number, the first
one does too (the first bullet states what the whole experience achieved, quantified). Per page: no action verb opens more than 2 bullets, no shape
covers more than 40 % of the bullets (rounded up), and with 6 or more bullets at least 3 different shapes appear.
"""
import argparse
import json
import re
import sys

import ast
import os


def _banned():
    """check_resume.py's BANNED list, read from its source (importing it would run its checks)."""
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_resume.py'), encoding='utf-8').read()
    m = re.search(r'^BANNED = (\[.*?\])', src, re.S | re.M)
    return ast.literal_eval(m.group(1)) if m else []


BANNED = _banned()

MAX_CHARS = 230
MAX_SAME_OPENER = 3
MAX_SHAPE_SHARE = 0.4
MIN_SHAPES = 3
WHY_MARKERS = [' to ', 'so that', 'so ', 'enabling', 'allowing', 'to meet', ' for ', 'when ', 'after ']
PROBLEM_MARKERS = ['when', 'found', 'mismatch', 'disagree', 'inconsistent', 'scattered', 'slow', 'wrong', 'invent',
                   'without', 'gap', 'error', 'duplicate', 'unclear', 'manual']
CONTEXT_OPENERS = {'to', 'when', 'with', 'after', 'facing', 'because', 'as', 'for', 'given', 'asked', 'before', 'while',
                   'seeing', 'needing', 'starting', 'building', 'running', 'using', 'across', 'from', 'without'}
MAX_PER_ENTRY = 5
# causal clauses Joey does not want (2026-11-09: 「以后不要使用 because 这种句式」); 'since' before a digit is a date
CAUSAL = [r'\bbecause\b', r'\bsince\b(?!\s+\d)', r'\bdue to\b', r'\bowing to\b']
MAX_SAME_VERB = 2
VERBS = {
    'led', 'built', 'ran', 'set', 'cut', 'won', 'made', 'wrote', 'drove', 'grew', 'took', 'found', 'chose', 'held',
    'designed', 'operate', 'operates', 'run', 'runs', 'own', 'owns', 'turned', 'compared', 'benchmarked', 'engineered',
    'specified', 'organized', 'produced', 'created', 'co-built', 'defined', 'shipped', 'launched', 'analyzed', 'tested',
    'evaluated', 'audited', 'measured', 'automated', 'replaced', 'scoped', 'prioritized', 'presented', 'translated',
    'taught', 'gave', 'kept', 'brought', 'sold', 'oversaw', 'began', 'got', 'put', 'met', 'spoke', 'rebuilt', 'rewrote',
}
NOT_VERBS = {'red', 'bed', 'need', 'seed', 'feed', 'speed', 'based', 'related', 'advanced', 'detailed', 'automated-'}
RESULT_WORDS = ['so ', 'so that', 'cut', 'reduc', 'rais', 'increas', 'improv', 'enabl', 'allow', '→', 'showing',
                'showed', 'produc', 'narrow', 'result', 'saving', 'faster', 'lost certification', 'cleared',
                'drawn only', 'could compare', 'consistently', 'without', 'until']


def split_star(text):
    """(context, rest) — context = the words before the first comma / colon when they are 2–16 words and start with a
    context opener; otherwise ('', text)."""
    t = text.strip()
    m = re.match(r'^([^,:]{1,140})[,:]\s+(.*)$', t)
    if m:
        ctx = m.group(1).split()
        if 2 <= len(ctx) <= 16 and ctx[0].lower().strip('"“') in CONTEXT_OPENERS:
            return m.group(1), m.group(2)
    return '', t


def first_verb(text):
    _, rest = split_star(text)
    w = re.match(r"[A-Za-z][A-Za-z\-']*", rest)
    return w.group(0).lower() if w else ''


def opener(text):
    ctx, _ = split_star(text)
    return ctx.split()[0].lower() if ctx else ''


def _is_verb(w):
    w = w.lower().strip(',.;:')
    return w in VERBS or (w.endswith('ed') and len(w) > 3 and w not in NOT_VERBS)


def shape(text):
    ctx, rest = split_star(text)
    if ctx:
        return 'context_first'   # not allowed (opener problem); kept so a report can name it
    if ';' in text:
        return 'verb_semicolon'
    if re.search(r',\s+[a-z]+ing\b', text):
        return 'verb_participle'
    if re.search(r'\bto\s+[a-z]+', rest[len(rest.split()[0]) if rest.split() else 0:]):
        return 'verb_purpose'
    return 'verb_plain'


def check_bullet(text):
    errs = []
    ctx, rest = split_star(text)
    if ctx:
        errs.append(f'opener: "{ctx[:40]}" — open with the action verb, not a context phrase; put the purpose after it (" to …")')
    else:
        v = first_verb(text)
        if not _is_verb(v):
            errs.append(f'verb: "{v or rest[:12]}" — the bullet must open with an action verb')
    low = ' ' + text.lower() + ' '
    if re.search(r'\d', text):
        if not any(m in low for m in WHY_MARKERS):
            errs.append('why: a quantified bullet must say why (a purpose after the action such as " to …", "so …", "enabling …")')
    else:
        if not any(m in low for m in PROBLEM_MARKERS):
            errs.append('problem: a bullet without a number must state the problem it solved (e.g. "When …", "found …", "mismatch")')
    for pat in CAUSAL:
        m = re.search(pat, text, re.I)
        if m:
            errs.append(f'causal: "{m.group(0)}" — no because-style clause; say the purpose (" to …", "so …") or the result instead')
            break
    if len(text) > MAX_CHARS:
        errs.append(f'length: {len(text)} characters > {MAX_CHARS}')
    for w in BANNED:
        if re.search(rf'\b{re.escape(w)}\b', low):
            errs.append(f'banned: {w}')
    return errs


def check_master(m):
    """Problems for a master dict {entries: [{name, bullets: [{text}]}]} — per bullet, per entry, per page."""
    out = []
    verbs, openers, shapes = {}, {}, {}
    for e in m.get('entries') or []:
        bl = e.get('bullets') or []
        if len(bl) > MAX_PER_ENTRY:
            out.append(f'{e.get("name")}: {len(bl)} bullets > {MAX_PER_ENTRY}')
        texts = [b['text'] if isinstance(b, dict) else b for b in bl]
        if len(texts) >= 2 and not re.search(r'\d', texts[0]) and any(re.search(r'\d', t) for t in texts[1:]):
            out.append(f'{e.get("name")}: outcome_first — the first bullet must state the overall result with a number '
                       f'(a later bullet has one) — {texts[0][:70]}')
        for b in bl:
            t = b['text'] if isinstance(b, dict) else b
            for x in check_bullet(t):
                out.append(f'{e.get("name")}: {x} — {t[:70]}')
            v = first_verb(t)
            verbs[v] = verbs.get(v, 0) + 1
            o = opener(t)
            openers[o] = openers.get(o, 0) + 1
            sh = shape(t)
            shapes[sh] = shapes.get(sh, 0) + 1
    for v, n in sorted(verbs.items()):
        if v and n > MAX_SAME_VERB:
            out.append(f'page: "{v}" opens {n} bullets (> {MAX_SAME_VERB}; vary the verbs)')
    total = sum(shapes.values())
    if total:
        import math
        cap = math.ceil(MAX_SHAPE_SHARE * total)
        for sh, n in sorted(shapes.items()):
            if n > cap:
                out.append(f'page: shape "{sh}" covers {n} of {total} bullets (> {cap}; use different sentence shapes)')
        if total >= 6 and len(shapes) < MIN_SHAPES:
            out.append(f'page: only {len(shapes)} sentence shape(s) across {total} bullets (need {MIN_SHAPES}+)')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('master', nargs='?')
    ap.add_argument('--text')
    a = ap.parse_args(argv)
    if a.text:
        errs = check_bullet(a.text)
    elif a.master:
        errs = check_master(json.load(open(a.master, encoding='utf-8')))
    else:
        ap.error('give a master.json or --text')
    for e in errs:
        print(e)
    print(f'check_bullets: {len(errs)} problem(s)')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
