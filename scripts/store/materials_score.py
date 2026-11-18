#!/usr/bin/env python3
"""materials_score.json — one record per application folder: how well the materials fit the JD (JSA-194, spec step 9).

Pure part (tested, scripts/test_materials_score.py): `score(manifest, tailored, step_a, letter_text)` →
    {track, direction, coverage: {before, after, total, exact_after, share}, gaps_not_true: [terms], gaps_phrasing: [terms],
     bullet_ids: [...], letter: {words, fact_check, banned_hits, stories}, flags: [...], score: 0-100}
- coverage comes from tailor.py's terms (tailored.json): `after` = JD terms on the page (any spelling), `share = after / total`.
- gaps_not_true = JD terms no fact shows ("not true", never added) — what the skill-gap list counts (a term he confirmed NOT having
  — "not used" — is left out: the list must not ask him about it again);
  gaps_phrasing = true terms the page words differently.
- score = round(100 × share) minus 10 per flag (letter fact check not pass, banned phrase in the letter, resume check not pass), floor 0.
Note: manifest resume.check / letter.fact_check are written 'pass' by ds_materials (the build fails before a manifest otherwise), so only the
banned-phrase scan is an independent letter check. Nothing here writes a sentence or asserts a fact about the user.

    python3 scripts/store/materials_score.py --folder <app folder name>     # write one
    python3 scripts/store/materials_score.py --all                          # backfill every folder that has materials
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'config'))
BANNED = ["leverage", "spearhead", "synergy", "passionate", "results-driven", "cutting-edge", "go-getter", "detail-oriented",
          "team player", "utilize", "seamlessly", "robust", "i am writing to express", "great fit", "fast-paced", "perfect fit"]


def banned_hits(text):
    low = (text or '').lower()
    return sorted({b for b in BANNED if re.search(r'\b' + re.escape(b), low)})


def _coverage(terms):
    total = len(terms)
    after = sum(1 for t in terms if t.get('after') in ('exact', 'other spelling'))
    before = sum(1 for t in terms if t.get('before') in ('exact', 'other spelling'))
    exact = sum(1 for t in terms if t.get('after') == 'exact')
    return {'before': before, 'after': after, 'total': total, 'exact_after': exact, 'share': round(after / total, 3) if total else 0.0}


def score(manifest, tailored, step_a, letter_text='', track_by=''):
    manifest, tailored, step_a = manifest or {}, tailored or {}, step_a or {}
    terms = tailored.get('terms') or []
    cov = _coverage(terms)
    res = manifest.get('resume') or {}
    let = manifest.get('letter') or {}
    hits = banned_hits(letter_text)
    flags = []
    if res and res.get('check') != 'pass':
        flags.append('resume check not pass')
    if let and let.get('fact_check') != 'pass':
        flags.append('letter fact check not pass')
    if hits:
        flags.append('banned phrase in the letter: ' + ', '.join(hits))
    if not terms:
        flags.append('no JD terms recorded (resume not built by tailor.py)')
    # the bullets on the page: fact ids of the tailored master's bullets (the approved master, JSA-251); folders built by the
    # legacy bank pick list their bank bullet IDs instead
    bullets = []
    for e in (tailored.get('tailored') or {}).get('entries') or []:
        for b in e.get('bullets') or []:
            bullets.append(f"{e.get('entry_id')}:" + '+'.join(b.get('fact_ids') or []))
    if not bullets:
        r = (step_a.get('data') or {}).get('resume') or {}
        for part in ('exp', 'projects'):
            for ids in (r.get(part) or {}).values():
                bullets += [x for x in ids if isinstance(x, str)]
    sc = max(0, round(100 * cov['share']) - 10 * len([f for f in flags if not f.startswith('no JD terms')]))
    return {'track': manifest.get('track'), 'direction': tailored.get('direction'), 'company': manifest.get('company'),
            'title': manifest.get('title'), 'coverage': cov,
            'gaps_not_true': [t['jd_spelling'] or t['term'] for t in terms if t.get('truth') == 'not true'],
            'gaps_phrasing': [t['jd_spelling'] or t['term'] for t in terms if t.get('truth') == 'true' and t.get('after') != 'exact'],
            'bullet_ids': bullets,
            'letter': {'words': let.get('words'), 'fact_check': let.get('fact_check'), 'banned_hits': hits, 'stories': let.get('stories') or []},
            'track_by': track_by, 'flags': flags, 'score': sc if terms else None}


def _load(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return None


def write_folder(folder_path):
    """Impure: read the folder's files, write materials_score.json; returns the record or None (no manifest)."""
    man = _load(os.path.join(folder_path, 'materials_manifest.json'))
    if not man:
        return None
    letter = ''
    try:
        letter = open(os.path.join(folder_path, 'cover.txt'), encoding='utf-8').read()
    except OSError:
        pass
    st = _load(os.path.join(folder_path, 'ds_status.json')) or {}
    rec = score(man, _load(os.path.join(folder_path, 'tailored.json')), _load(os.path.join(folder_path, 'ds_step_a.json')), letter, st.get('track_by') or '')
    rec['folder'] = os.path.basename(folder_path.rstrip('/'))
    rec['generated_at'] = man.get('generated_at')
    json.dump(rec, open(os.path.join(folder_path, 'materials_score.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return rec


def _commit(files, subject):
    """JSA-412: the writer commits its own files (best effort, never fails the run)."""
    try:
        import data_git
        data_git.commit_paths([f for f in files if os.path.exists(f)], subject)
    except Exception:  # noqa: BLE001
        pass


def main():
    import paths
    ap = argparse.ArgumentParser(); ap.add_argument('--folder'); ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    if a.folder:
        r = write_folder(paths.apps(a.folder)); _commit([os.path.join(paths.apps(a.folder), 'materials_score.json')], f'data: materials_score {a.folder}'); print('materials_score:', 'no manifest' if r is None else f"{a.folder}: score {r['score']}, flags {r['flags']}")
        return 0 if r else 2
    base = paths.apps()
    n = 0
    for f in sorted(os.listdir(base)):
        if os.path.isdir(os.path.join(base, f)) and write_folder(os.path.join(base, f)):
            n += 1
    print(f'materials_score: {n} folder(s) written')
    _commit([os.path.join(base, f, 'materials_score.json') for f in os.listdir(base)], f'data: materials_score ({n} folder(s))')
    return 0


if __name__ == '__main__':
    sys.exit(main())
