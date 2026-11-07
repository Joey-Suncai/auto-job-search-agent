#!/usr/bin/env python3
"""The material gate — does the form's requirement set match what we actually produced? (JSA-002)

`materials_check.check_items(folder)` compares `requirements.json` (what the form asks for, with evidence) against
`materials_manifest.json` (what we produced: file + sha256 + check/fact-check result). Both runners call this
**before they start filling**, so "the form wants a letter we never wrote" stops being a chat-time judgement call.

Slice 2 (2026-10-30):
  * default mode is `block`;
  * `prepare()` writes requirements.json when it is missing — Greenhouse offline from gh_api.json, Workday seeded
    with the resume (the only file every Workday form takes) and extended page by page by `page_check()`;
  * every problem becomes a structured event for `decide.py` (requirement_appeared / material_mismatch); the run
    goes on only when every decision is `skip_if_optional`. Any other action stops the run with a queue line that
    says what to do next (generate_material → run ds_materials.py, then rerun). The runner never generates material
    mid-form and never guesses.

    from materials_gate import run_gate, page_check
    g = run_gate(folder, log, mode='block', ask=None)   # {'at','mode','ok','problems','decisions','next'}
    p = page_check(folder, page, step, log, ask=None)   # Workday: None = nothing new, else the same record shape

Modes: `off` (skip) · `warn` (log only) · `block` (default: caller stops when ok is False).
"""
import json, os, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, '..', 'scripts'))
for p in (SCRIPTS, HERE):
    if p not in sys.path:                        # materials_check / materials_probe / ds_materials · decide
        sys.path.insert(0, p)

sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077)

MODES = ('off', 'warn', 'block')
DEFAULT_MODE = 'block'
GENERATABLE = {'cover_letter', 'essay', 'resume'}   # ds_materials.py can (re)build these from approved sources
NEXT = {'generate_material': 'run scripts/ds_materials.py on the folder, then rerun the runner',
        'regenerate_material': 'rerun scripts/ds_materials.py on the folder (the file changed or failed its check), then rerun',
        'pause_for_joey': 'Joey decides: supply the file / answer, or archive the application',
        'abort': 'archive the application (the decision layer chose abort)'}


def _items(folder):
    """The structured problems; the gate itself must never break a run, so any failure becomes a setup problem."""
    try:
        from materials_check import check_items
        return list(check_items(folder) or [])
    except Exception as e:
        return [{'kind': 'gate', 'required': True, 'type': 'setup', 'evidence': '',
                 'msg': f'materials gate unavailable: {type(e).__name__}: {str(e)[:120]}'}]


def check(folder):
    """The raw problem sentences for this folder (kept for slice-1 callers and tests)."""
    return [i['msg'] for i in _items(folder)]


def prepare(folder, log=None, ats=None):
    """Write requirements.json if it is missing. Returns how it was produced ('existing', 'gh_api', 'workday_seed', None)."""
    log = log or (lambda m: None)
    rp = os.path.join(folder, 'requirements.json')
    if os.path.exists(rp):
        try:
            data = json.load(open(rp, encoding='utf-8'))
        except ValueError:
            data = None
        stale = bool(data and data.get('source') == 'gh_api' and int(data.get('version') or 1) < 2
                     and os.path.exists(os.path.join(folder, 'gh_api.json')))
        if not stale:
            if data:
                register_transcript(folder, data.get('requirements') or [], log)
                register_extra_files(folder, data.get('requirements') or [], log)
            return 'existing'
        os.remove(rp)                            # file slots classified before JSA-209 (Viking 10-31: supplement read as resume)
        log('materials: requirements.json from an older gh_api probe — re-probed (file slots by slot_kind)')
    if os.path.exists(os.path.join(folder, 'gh_api.json')):
        try:
            import materials_probe
            _, data = materials_probe.probe(folder)
            log(f"materials: requirements.json from gh_api.json ({len(data['requirements'])} requirement(s))")
            register_transcript(folder, data['requirements'], log)      # Greenhouse transcript slot (Walleye 2026-10-31)
            register_extra_files(folder, data['requirements'], log)     # files Joey supplied for extra slots (JSA-209)
            return 'gh_api'
        except BaseException as e:               # probe() raises SystemExit when there is nothing to read
            log(f'materials: offline probe failed: {type(e).__name__} {str(e)[:80]}')
            return None
    if ats in ('lever', 'ashby') and os.path.exists(os.path.join(folder, 'plan.json')):
        import materials_probe
        plan = json.load(open(os.path.join(folder, 'plan.json'), encoding='utf-8'))
        reqs = [{'kind': materials_probe.classify(f['label'], 'input_file'), 'required': bool(f.get('required')),
                 'evidence': f"{f['label'][:100]} (file)", 'selector': f.get('sel', ''), 'source': ats + '_form'}
                for f in plan.get('fields', []) if f.get('type') == 'file']
        json.dump({'ats': ats, 'source': ats + '_form', 'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'requirements': reqs},
                  open(rp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        log(f"materials: requirements.json from the {ats} form ({len(reqs)} file field(s))")
        register_transcript(folder, reqs, log)
        return ats + '_form'
    if ats == 'workday':
        json.dump({'ats': 'workday', 'source': 'workday_seed', 'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'requirements': [{'kind': 'resume', 'required': True, 'evidence': 'every Workday application takes a resume',
                                     'selector': '', 'source': 'workday_seed'}]},
                  open(rp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        log('materials: requirements.json seeded for Workday (resume); later pages are probed one by one')
        return 'workday_seed'
    if ats in SEED_ATS:                          # JSA-186: the newer runners read the form live — seed resume + letter
        json.dump({'ats': ats, 'source': ats + '_seed', 'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'requirements': [{'kind': 'resume', 'required': True, 'evidence': f'every {ats} application takes a resume',
                                     'selector': '', 'source': ats + '_seed'},
                                    {'kind': 'cover_letter', 'required': False, 'source': ats + '_seed', 'selector': '',
                                     'evidence': 'a cover letter for every application (Joey 2026-11-05); uploaded where a slot exists'}]},
                  open(rp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        log(f'materials: requirements.json seeded for {ats} (resume + optional cover letter)')
        return ats + '_seed'
    return None


SEED_ATS = ('icims', 'oracle', 'workable', 'smartrecruiters', 'successfactors')


TRANSCRIPT = jsa_profile.repo_path('transcript.path') or ''          # the user's official transcript (profile transcript.path)
TRANSCRIPT_NAME = jsa_profile.get('transcript.file_name') or 'Transcript.pdf'
TRANSCRIPT_LABEL = jsa_profile.get('transcript.label') or 'official transcript'


def register_transcript(folder, reqs, log=None):
    """A form that asks for a transcript gets the user's official transcript (profile transcript.path; Joey's supplied by him
    2026-10-27): copied into the folder and recorded in materials_manifest.json with its sha256."""
    if not any(r['kind'] == 'transcript' for r in reqs) or not TRANSCRIPT or not os.path.exists(TRANSCRIPT):
        return None
    import hashlib, shutil
    dst = os.path.join(folder, TRANSCRIPT_NAME)
    if not os.path.exists(dst):
        shutil.copyfile(TRANSCRIPT, dst)
    mp = os.path.join(folder, 'materials_manifest.json')
    m = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) else {}
    m['transcript'] = {'file': os.path.basename(dst), 'sha256': hashlib.sha256(open(dst, 'rb').read()).hexdigest(),
                       'source': jsa_profile.get('transcript.path'), 'approved': 'candidate profile: official transcript supplied by the candidate'}
    json.dump(m, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    (log or (lambda x: None))(f'materials: transcript registered ({TRANSCRIPT_LABEL})')
    return dst


def supplied_file(folder, answers, key):
    """answers[key] when it is the name of a file directly in the folder (Joey's own file for a slot), else None."""
    v = (answers or {}).get(key)
    if not isinstance(v, str) or not v or v != os.path.basename(v) or v in ('.', '..'):
        return None
    try:
        return v if v in os.listdir(folder) and os.path.isfile(os.path.join(folder, v)) else None   # exact name
    except OSError:
        return None


def register_extra_files(folder, reqs, log=None):
    """Greenhouse extra file slots (JSA-209): a file the candidate supplied for a slot — answers.json maps the slot's field
    name to a file in the folder — is recorded in materials_manifest.json → extra_files[<field name>] with its sha256,
    so the gate accepts it. Nothing else counts as the slot's file (the runner never guesses a document)."""
    extra = [r for r in reqs if r.get('slot') == 'extra' and r.get('selector')]
    if not extra:
        return {}
    import hashlib
    try:
        answers = json.load(open(os.path.join(folder, 'answers.json'), encoding='utf-8'))
    except (OSError, ValueError):
        answers = {}
    have = {}
    for r in extra:
        name = supplied_file(folder, answers, r['selector'])
        if name:
            have[r['selector']] = {'file': name, 'sha256': hashlib.sha256(open(os.path.join(folder, name), 'rb').read()).hexdigest(),
                                   'approved': 'answers.json (supplied by the candidate)'}
    mp = os.path.join(folder, 'materials_manifest.json')
    if have and os.path.exists(mp):
        m = json.load(open(mp, encoding='utf-8'))
        if m.get('extra_files') != have:
            m['extra_files'] = have
            json.dump(m, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            (log or (lambda x: None))('materials: supplied file(s) registered for ' + ', '.join(have))
    return have


def _event(item, page=''):
    if item['type'] == 'missing':
        name = 'requirement_appeared'
    elif item['type'] == 'mismatch':
        name = 'material_mismatch'
    else:
        return None
    return {'event': name, 'kind': item['kind'], 'required': bool(item.get('required', True)),
            'generatable': item['kind'] in GENERATABLE, 'page': page, 'evidence': item.get('evidence') or item['msg'][:120]}


def resolve(folder, items, log, ask=None, page=''):
    """Route every problem through decide.py. Returns (ok, decisions, next_steps)."""
    from decide import decide
    decisions, nexts, ok = [], [], True
    for it in items:
        ev = _event(it, page)
        if ev is None:                           # a pipeline step is missing: not a decision, just stop
            decisions.append({'kind': it['kind'], 'action': 'stop', 'reason': it['msg'], 'source': 'setup'})
            nexts.append(it['msg']); ok = False
            continue
        d = decide(ev, folder, ask=ask)
        decisions.append(dict(d, kind=it['kind'], event=ev['event']))
        log(f"  decide {ev['event']} {it['kind']} → {d['action']} ({d['source']}: {d['reason'][:80]})")
        if d['action'] != 'skip_if_optional':
            ok = False
            nexts.append(f"{it['kind']}: {NEXT.get(d['action'], d['action'])}")
    return ok, decisions, nexts


def run_gate(folder, log=None, mode=DEFAULT_MODE, ask=None, ats=None):
    """Check the folder's requirements against its manifest. Returns {'at','mode','ok','problems','decisions','next'}."""
    log = log or (lambda m: None)
    mode = mode if mode in MODES else DEFAULT_MODE
    record = {'at': datetime.now().isoformat(timespec='seconds'), 'mode': mode, 'ok': True, 'problems': [],
              'decisions': [], 'next': []}
    if mode == 'off':
        return record
    prepare(folder, log, ats)
    items = _items(folder)
    record['problems'] = [i['msg'] for i in items]
    if not items:
        log('materials gate: ok')
        return record
    log(f'materials gate: {len(items)} problem(s) [{mode}]')
    for i in items:
        log(f"  - {i['msg']}")
    if mode == 'warn':
        record['ok'] = False
        return record
    record['ok'], record['decisions'], record['next'] = resolve(folder, items, log, ask)
    return record


PAGE_FILES_JS = """() => [...document.querySelectorAll('input[type=file]')].map(el => {
  const box = el.closest('[data-automation-id^="formField-"], [data-automation-id*="ection"], fieldset') || el.parentElement;
  return {label: ((box && box.innerText) || el.name || '').trim().slice(0, 160), id: el.getAttribute('data-automation-id') || el.name || el.id || ''};
})"""


def page_check(folder, page, step, log=None, ask=None, mode=DEFAULT_MODE):
    """Workday: file inputs on this page that ask for something other than the resume (cover letter, transcript,
    portfolio, or a second file slot) are new requirements → appended to requirements.json → the gate runs on them.
    The runner already uploads the resume to the page's file input, so a lone resume/generic slot is not new.
    Returns None when nothing new appeared, else the run_gate record for the new items."""
    if mode == 'off':
        return None
    log = log or (lambda m: None)
    try:
        slots = page.evaluate(PAGE_FILES_JS) or []
    except Exception:
        return None
    import materials_probe
    rp = os.path.join(folder, 'requirements.json')
    data = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {'ats': 'workday', 'requirements': []}
    known = {(r.get('kind'), r.get('page', '')) for r in data['requirements']} | {(r.get('kind'), '') for r in data['requirements']}
    new = []
    for n, s in enumerate(slots):
        kind = materials_probe.classify(s.get('label'), 'input_file')
        if kind in ('resume', 'unknown') or (kind == 'other_file' and n == 0):
            continue                             # the slot the runner fills with the resume
        if (kind, step) in known or (kind, '') in known:
            continue
        new.append({'kind': kind, 'required': True, 'evidence': f"{step}: {s.get('label', '')[:100]}",
                    'selector': s.get('id', ''), 'source': 'live_form', 'page': step})
    if not new:
        return None
    data['requirements'] += new
    data['checked_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    json.dump(data, open(rp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log(f"materials: page \"{step}\" asks for {', '.join(r['kind'] for r in new)} — added to requirements.json")
    items = [i for i in _items(folder) if i['kind'] in {r['kind'] for r in new}]
    rec = {'at': datetime.now().isoformat(timespec='seconds'), 'mode': mode, 'ok': True, 'problems': [i['msg'] for i in items],
           'decisions': [], 'next': []}
    if items and mode == 'block':
        rec['ok'], rec['decisions'], rec['next'] = resolve(folder, items, log, ask, page=step)
    elif items:
        rec['ok'] = False
    return rec


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Check one application folder: requirements.json vs materials_manifest.json')
    ap.add_argument('folder')
    ap.add_argument('--mode', choices=MODES, default=DEFAULT_MODE)
    ap.add_argument('--ats', choices=('greenhouse', 'workday'))
    a = ap.parse_args()
    g = run_gate(a.folder, print, a.mode, ats=a.ats)
    print('ok' if g['ok'] else 'problems', len(g['problems']))
    for n in g['next']:
        print('next:', n)
    raise SystemExit(0 if g['ok'] else 1)
