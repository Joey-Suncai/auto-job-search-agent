#!/usr/bin/env python3
"""Pre-submit gates shared by the newer runners — iCIMS, Oracle, Workable, SmartRecruiters, SuccessFactors (JSA-186).

run.py / run_form.py / run_wd.py already ran the canonical audit (canon.py) and the materials gate (materials_gate.py);
the five newer runners submitted without them and fell back to a generic library resume. Two checks, same rules for all:

  before(folder, resume, ats, log)  → problems   materials gate + "the upload is the folder's tailored resume"
                                                 (called before the browser fills anything)
  audit(result, url, log)           → (hard, warn)   canon.audit on what the page holds (every field the runner read back,
                                                 Oracle sections / iCIMS steps included); hard → the submit is blocked

    Used by runner_common.py (JSA-187): Run.opening() calls before(), Run.gate() / gate_inside() / report() call audit().
"""
import json, os

import canon
import materials_gate


def manifest_resume(folder):
    """The tailored resume file name the materials manifest recorded, or None."""
    try:
        m = json.load(open(os.path.join(folder, 'materials_manifest.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return ((m.get('resume') or {}).get('file')) or None


def tailored_problem(folder, resume):
    """None when `resume` is the folder's own tailored resume (the one in the manifest), else the problem sentence."""
    if not resume:
        return 'no resume to upload — run ds_materials.py on the folder first'
    want = manifest_resume(folder)
    if not want:
        return 'no tailored resume in materials_manifest.json — run ds_materials.py on the folder first'
    here = os.path.abspath(os.path.join(folder, want))
    if os.path.abspath(resume) != here:
        return (f'the upload would be {os.path.basename(resume)}, not the tailored resume {want} in the folder '
                '— never a default resume on a submit')
    return None


def before(folder, resume, ats, log=None, mode=materials_gate.DEFAULT_MODE):
    """Materials gate + tailored-resume check. Returns the problem sentences ([] = ok)."""
    log = log or (lambda m: None)
    probs = []
    g = materials_gate.run_gate(folder, log, mode=mode, ats=ats)
    if not g.get('ok'):
        probs.append('materials gate: ' + '; '.join(g.get('next') or g.get('problems') or ['failed'])[:240])
    t = tailored_problem(folder, resume)
    if t:
        log('materials: ' + t); probs.append('materials: ' + t)
    return probs


def fields_of(result):
    """Every read-back field of a runner result: top-level `fields`, Oracle `sections[].fields`, iCIMS `steps[].fields`."""
    out = list(result.get('fields') or [])
    for grp in (result.get('sections') or []) + (result.get('steps') or []):
        if isinstance(grp, dict):
            out += grp.get('fields') or []
    return [f for f in out if isinstance(f, dict)]


def records(result):
    """canon.audit records from what the page holds (`page`), with the field's type and required flag."""
    recs = []
    for f in fields_of(result):
        recs.append({'label': f.get('label') or f.get('key') or '', 'value': f.get('page'),
                     'type': f.get('type') or f.get('kind') or '', 'required': bool(f.get('required')),
                     'options': f.get('options') or []})
    return recs


def audit(result, url, log=None):
    """(hard, warn): canonical mismatches on the page (block the submit) and empty optional high-stakes fields (shown)."""
    log = log or (lambda m: None)
    warn = []
    hard = canon.audit(records(result), canon.tenant_of(url), warn=warn)
    for m in hard:
        log(f"canon: {m['key']} = {m['value']!r} — {m['reason']}")
    for w in warn:
        log(f"canon (warning): {w['key']} left empty on an optional field: {w['label'][:80]}")
    return hard, warn


def review(result, log=None, tag=''):
    """JSA-355: the independent last look at the key cells of the page (final_review.py); blocking problem sentences."""
    import final_review
    return final_review.problems(records(result), log, tag=tag)


def lines(hard):
    return canon.block(hard)

