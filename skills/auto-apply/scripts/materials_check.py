#!/usr/bin/env python3
"""Compare what the form asks for (requirements.json) with what was produced (materials_manifest.json).

    from materials_check import check
    problems = check(folder)     # [] = safe to fill;  each item is a sentence an agent can act on

Used by the runners as the material gate before filling (and by the manual-platform flow before submitting).
"""
import hashlib, json, os


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _entry(manifest, kind):
    return (manifest or {}).get(kind) or {}


def check_items(folder):
    """Structured problems: [{kind, required, type, msg, evidence}]. type = setup (a pipeline step is missing) ·
    missing (the form asks for something we did not produce) · mismatch (we produced it but it is not usable)."""
    rp = os.path.join(folder, 'requirements.json')
    mp = os.path.join(folder, 'materials_manifest.json')
    out = []

    def add(kind, typ, msg, r=None):
        out.append({'kind': kind, 'required': (r or {}).get('required') is not False, 'type': typ, 'msg': msg,
                    'evidence': ((r or {}).get('evidence') or '')[:120]})

    if not os.path.exists(mp):
        add('manifest', 'setup', 'materials_manifest.json missing — run ds_materials.py first')
        return out
    manifest = json.load(open(mp, encoding='utf-8'))
    if not os.path.exists(rp):
        add('requirements', 'setup', 'requirements.json missing — run materials_probe.py first')
        return out
    reqs = json.load(open(rp, encoding='utf-8')).get('requirements') or []

    for r in reqs:
        kind = r.get('kind')
        reqd = r.get('required') is not False
        if kind == 'resume':
            e = _entry(manifest, 'resume')
            f = e.get('file')
            if not f:
                add(kind, 'missing', 'resume: manifest has no resume file', r)
            elif not os.path.exists(os.path.join(folder, f)):
                add(kind, 'mismatch', 'resume: %s is missing on disk' % f, r)
            elif e.get('sha256') != sha256(os.path.join(folder, f)):
                add(kind, 'mismatch', 'resume: sha mismatch — the file changed after the manifest was written (rerun ds_materials.py)', r)
            elif str(e.get('check', 'pass')).lower() != 'pass':
                add(kind, 'mismatch', 'resume: layout/check_resume did not pass', r)
        elif kind == 'cover_letter':
            e = _entry(manifest, 'letter')
            if not reqd:
                continue
            if (e.get('decision') or '') != 'generated' or not e.get('file'):
                add(kind, 'missing', 'cover_letter: required by the form (%s) but not generated' % (r.get('evidence') or '')[:60], r)
            elif not os.path.exists(os.path.join(folder, e['file'])):
                add(kind, 'mismatch', 'cover_letter: %s is missing on disk' % e['file'], r)
            elif e.get('sha256') != sha256(os.path.join(folder, e['file'])):
                add(kind, 'mismatch', 'cover_letter: sha mismatch — regenerate it', r)
            elif str(e.get('fact_check', 'pass')).lower() != 'pass':
                add(kind, 'mismatch', 'cover_letter: fact check did not pass', r)
        elif kind == 'essay':
            p = os.path.join(folder, 'open_answers.md')
            if reqd and (not os.path.exists(p) or os.path.getsize(p) < 40):
                add(kind, 'missing', 'essay: the form has a written question (%s) and open_answers.md is empty' % (r.get('evidence') or '')[:60], r)
        elif r.get('slot') == 'extra' and kind in ('transcript', 'portfolio', 'other_file') and \
                (manifest.get('extra_files') or {}).get(r.get('selector') or ''):
            e = manifest['extra_files'][r['selector']]   # a file the candidate supplied for this slot (Greenhouse, JSA-209)
            if not os.path.exists(os.path.join(folder, e.get('file') or '')):
                add(kind, 'mismatch', '%s: %s is missing on disk' % (kind, e.get('file')), r)
            elif e.get('sha256') != sha256(os.path.join(folder, e['file'])):
                add(kind, 'mismatch', '%s: sha mismatch — the supplied file changed' % kind, r)
        elif kind == 'transcript' and _entry(manifest, 'transcript').get('file'):
            e = _entry(manifest, 'transcript')       # Joey's own official transcript, registered by materials_gate (Lever / Ashby)
            if not os.path.exists(os.path.join(folder, e['file'])):
                add(kind, 'mismatch', 'transcript: %s is missing on disk' % e['file'], r)
            elif e.get('sha256') != sha256(os.path.join(folder, e['file'])):
                add(kind, 'mismatch', 'transcript: sha mismatch — the file changed', r)
        elif kind in ('transcript', 'portfolio', 'other_file'):
            if reqd:
                add(kind, 'missing', '%s: the form asks for it (%s) — no approved file is recorded' % (kind, (r.get('evidence') or '')[:60]), r)
    return out


def check(folder):
    return [i['msg'] for i in check_items(folder)]


if __name__ == '__main__':
    import sys
    probs = check(sys.argv[1])
    print('problems', len(probs))
    for p in probs:
        print(' -', p)
    sys.exit(1 if probs else 0)
